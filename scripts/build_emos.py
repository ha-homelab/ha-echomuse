#!/usr/bin/env python3
"""Build a private emOS image offline; never connect to or flash a device.

The reference must be an independently verified backup from the target Dot.
The system partition must belong to the same donor slot as that reference.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

SOURCE_COMMIT = "e119433c0845dfe80f4b1ec44c9e8e8028adbb07"
PAYLOAD_SHA256 = "5c2c4e02f17bfa3c5e9a83e189b64a41025f16b8bfe43f4e6accd430621b06b8"
EMOS_VERSION = "emos-v0.10"
SBIN_FILES = ("busybox", "em-wifi", "wpa_cli", "wpa_supplicant")
MAX_INPUT_BYTES = 64 * 1024 * 1024


class PreparationError(Exception):
    """A failed precondition; no device has been written."""


def system_partition(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value) or not 1 <= int(value) <= 127:
        raise argparse.ArgumentTypeError(
            "system partition must be a verified mmcblk0 partition number (1–127)"
        )
    return int(value)


def git(source: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "-c", "core.fsmonitor=false", *args],
            check=True, text=True, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        # A Git error can include a configured remote URL. Do not echo its output.
        raise PreparationError("cannot inspect the local upstream Git checkout") from exc
    return result.stdout.strip()


def validate_source(source: Path) -> Path:
    """Require the exact upstream commit and no modified tracked files."""
    if not source.is_dir():
        raise PreparationError("source directory does not exist")
    root = Path(git(source, "rev-parse", "--show-toplevel")).resolve()
    if root != source.resolve():
        raise PreparationError("source-dir must be the root of the upstream checkout")
    if git(source, "rev-parse", "--verify", "HEAD") != SOURCE_COMMIT:
        raise PreparationError(f"upstream source must be pinned to {SOURCE_COMMIT}")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise PreparationError("upstream checkout has modified tracked files")
    relative = "controller/em_emos_build.py"
    path = source / relative
    if not path.is_file() or path.is_symlink():
        raise PreparationError("pinned upstream image builder is not a regular file")
    # Also compare the executed module to Git's committed blob: status alone
    # can omit a tracked file marked assume-unchanged or skip-worktree.
    committed = git(source, "rev-parse", f"HEAD:{relative}")
    present = git(source, "hash-object", "--no-filters", "--", relative)
    if present != committed:
        raise PreparationError("upstream image builder differs from its committed blob")
    return path


def read_verified(path: Path, expected: str, label: str) -> bytes:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise PreparationError(f"{label} SHA-256 must contain exactly 64 hexadecimal characters")
    if not path.is_file():
        raise PreparationError(f"{label} must be an existing regular file")
    if not 0 < path.stat().st_size <= MAX_INPUT_BYTES:
        raise PreparationError(f"{label} size is empty or exceeds the 64 MiB safety limit")
    # Bound the read too, in case the file grows between stat() and read().
    with path.open("rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise PreparationError(f"{label} exceeds the 64 MiB safety limit")
    if hashlib.sha256(data).hexdigest() != expected.lower():
        raise PreparationError(f"{label} SHA-256 mismatch")
    return data


def boot_image_from_escrow(escrow: bytes) -> tuple[bytes, dict]:
    """Bound the image as the pinned wizard does; classify every trailing byte.

    Android's page-aligned kernel/ramdisk/second sizes bound the image passed
    to the upstream packer. Full partition reads can also contain a detached
    X.509 certificate and zero fill. Keep the full escrow unchanged and record
    its trailer; reject unknown nonzero bytes rather than silently discarding
    them. Parsing the certificate does not authenticate its signature.
    """
    if len(escrow) < 2048 or escrow[:8] != b"ANDROID!":
        raise PreparationError("reference is not a complete Android boot image header")
    kernel_size = struct.unpack_from("<I", escrow, 8)[0]
    ramdisk_size = struct.unpack_from("<I", escrow, 16)[0]
    second_size = struct.unpack_from("<I", escrow, 24)[0]
    page = struct.unpack_from("<I", escrow, 36)[0]
    header_version = struct.unpack_from("<I", escrow, 40)[0]
    if page != 2048 or header_version != 0:
        raise PreparationError("reference must use the pinned packer's 2048-byte Android v0 layout")
    if not kernel_size or not ramdisk_size or second_size:
        raise PreparationError("reference needs kernel and ramdisk and no second-stage region")
    aligned = lambda size: ((size + page - 1) // page) * page
    end = page + aligned(kernel_size) + aligned(ramdisk_size)
    if end > len(escrow):
        raise PreparationError("reference is truncated before the header-declared image end")
    image, tail = escrow[:end], escrow[end:]
    certificate = b""
    padding = tail
    trailer_kind = "zero-padding" if tail else "none"
    if any(tail):
        # A definite-length, canonical DER SEQUENCE is the outer Certificate.
        if len(tail) < 2 or tail[0] != 0x30:
            raise PreparationError("reference has an unrecognized nonzero trailer")
        length = tail[1]
        header_len = 2
        if length & 0x80:
            count = length & 0x7f
            if not 1 <= count <= 4 or len(tail) < 2 + count or tail[2] == 0:
                raise PreparationError("reference has an invalid DER trailer length")
            length = int.from_bytes(tail[2:2 + count], "big")
            header_len += count
            if length < 128:
                raise PreparationError("reference has a noncanonical DER trailer length")
        certificate_size = header_len + length
        if certificate_size > 16 * 1024 or certificate_size > len(tail):
            raise PreparationError("reference certificate trailer is truncated or exceeds 16 KiB")
        certificate, padding = tail[:certificate_size], tail[certificate_size:]
        if any(padding):
            raise PreparationError("reference has unknown nonzero bytes after its certificate trailer")
        try:
            parsed = subprocess.run(
                ["openssl", "x509", "-inform", "DER", "-outform", "DER"],
                input=certificate, capture_output=True, check=True, timeout=10,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise PreparationError("OpenSSL could not parse the reference's detached X.509 certificate") from exc
        if parsed.stdout != certificate:
            raise PreparationError("reference certificate is not canonical X.509 DER")
        trailer_kind = "x509-der-and-zero-padding" if padding else "x509-der"
    return image, {
        "escrow_size": len(escrow),
        "bounded_reference_size": len(image),
        "bounded_reference_sha256": hashlib.sha256(image).hexdigest(),
        "reference_trailer": {
            "kind": trailer_kind,
            "size": len(tail),
            "sha256": hashlib.sha256(tail).hexdigest(),
            "certificate_size": len(certificate),
            "certificate_sha256": hashlib.sha256(certificate).hexdigest() if certificate else None,
            "zero_padding_size": len(padding),
            "certificate_signature_verified": False,
        },
    }


def receipt_path(output: Path) -> Path:
    return output.with_suffix(output.suffix + ".json")


def require_new_outputs(output: Path) -> None:
    for path in (output, receipt_path(output)):
        # lexists catches dangling symlinks as well as ordinary files.
        if os.path.lexists(path):
            raise PreparationError("output image or receipt already exists; refusing overwrite")


def load_builder(path: Path):
    spec = importlib.util.spec_from_file_location("pinned_em_emos_build", path)
    if spec is None or spec.loader is None:
        raise PreparationError("cannot load the verified upstream image builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(args: argparse.Namespace) -> tuple[bytes, dict]:
    require_new_outputs(args.output)
    # Validate programmatic callers too, not only argparse callers.
    if type(args.system_part) is not int or not 1 <= args.system_part <= 127:
        raise PreparationError("system partition must be a verified number from 1 to 127")
    source_path = validate_source(args.source_dir)
    escrow = read_verified(args.reference, args.reference_sha256, "reference")
    payload = read_verified(args.payload, PAYLOAD_SHA256, "payload")
    reference, reference_metadata = boot_image_from_escrow(escrow)
    builder = load_builder(source_path)
    try:
        bundle = builder.read_payload_bundle(payload)
        if bundle.get("version") != EMOS_VERSION:
            raise PreparationError("payload manifest has an unexpected emOS version")
        files = bundle["files"]
        missing = sorted(set((*SBIN_FILES, "init32")) - files.keys())
        if missing:
            raise PreparationError("payload is missing required ARM32 init or networking tools")
        arch = builder.reference_kernel_arch(reference)
        if arch != "arm":
            raise PreparationError("reference kernel must be ARM32 for this FireOS 6 migration")
        problems = builder.init_binary_problems(files["init32"], arch)
        if problems:
            raise PreparationError("payload init does not match the reference kernel")
        result = builder.build_emos_image(
            reference, files["init32"], EMOS_VERSION,
            sbin={name: files[name] for name in SBIN_FILES},
            system_part=args.system_part,
        )
    except builder.BuildError as exc:
        raise PreparationError(f"upstream image validation failed: {exc}") from exc
    except (KeyError, TypeError, ValueError, struct.error) as exc:
        raise PreparationError("upstream builder could not parse or assemble the supplied inputs") from exc
    image = result.pop("image")
    if not isinstance(image, bytes) or not image or len(image) > len(escrow):
        raise PreparationError("built image is empty or exceeds the escrowed partition size")
    digest = hashlib.sha256(image).hexdigest()
    if digest != result.get("sha256") or len(image) != result.get("size"):
        raise PreparationError("upstream builder returned inconsistent image metadata")
    result.update({
        "prepared_only": True,
        "device_write_performed": False,
        "source_commit": SOURCE_COMMIT,
        "emos_version": EMOS_VERSION,
        "payload_sha256": PAYLOAD_SHA256,
        "reference_sha256": hashlib.sha256(escrow).hexdigest(),
        "kernel_arch": arch,
        "system_part": args.system_part,
        "topology_verified_by_builder": False,
        **reference_metadata,
    })
    return image, result


def write_outputs(output: Path, image: bytes, receipt: dict) -> None:
    """Create private artifacts exclusively; never overwrite existing files."""
    require_new_outputs(output)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    created = []
    try:
        for path, data in (
            (output, image),
            (receipt_path(output), (json.dumps(receipt, indent=2) + "\n").encode()),
        ):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
    except OSError:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source-dir", type=Path, required=True)
    cli.add_argument("--payload", type=Path, required=True)
    cli.add_argument("--reference", type=Path, required=True)
    cli.add_argument("--reference-sha256", required=True)
    cli.add_argument("--system-part", type=system_partition, required=True)
    cli.add_argument("--output", type=Path, required=True)
    return cli


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        image, receipt = prepare(args)
        write_outputs(args.output, image, receipt)
    except (PreparationError, OSError) as exc:
        print(f"Image preparation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: receipt[key] for key in (
        "prepared_only", "size", "sha256", "kernel_arch", "system_part"
    )}))
    print("Image prepared locally. No device was contacted or flashed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
