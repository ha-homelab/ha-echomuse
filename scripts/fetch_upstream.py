#!/usr/bin/env python3
"""Download pinned EchoMuse release artifacts into private storage; never execute them."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 128 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
ALLOWED_HOSTS = frozenset({
    "github.com", "release-assets.githubusercontent.com",
    "objects.githubusercontent.com", "github-releases.githubusercontent.com",
})


class FetchError(Exception):
    """An artifact failed validation or could not be downloaded safely."""


def validate_url(url: str, *, initial: bool = False) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS
                 and parsed.port in (None, 443) and not parsed.username
                 and not parsed.password and not parsed.fragment)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise FetchError("download URL must use HTTPS on an allowed GitHub release host")
    if initial and (parsed.hostname != "github.com" or not parsed.path.startswith(
            "/wilbowes/EchoMuse/releases/download/") or parsed.query):
        raise FetchError("artifact must originate from an EchoMuse GitHub release")


class ReleaseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_artifacts(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as stream:
            artifacts = json.load(stream)["artifacts"]
        if not isinstance(artifacts, dict) or not artifacts:
            raise ValueError
        for name, artifact in artifacts.items():
            if not isinstance(name, str) or not isinstance(artifact, dict):
                raise ValueError
            filename = artifact["filename"]
            if (not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", filename)
                    or filename in (".", "..")):
                raise ValueError
            if type(artifact["bytes"]) is not int or not 0 < artifact["bytes"] <= MAX_BYTES:
                raise ValueError
            if not re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]):
                raise ValueError
            validate_url(artifact["url"], initial=True)
        if len({a["filename"] for a in artifacts.values()}) != len(artifacts):
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise FetchError("invalid or unreadable upstream lock file") from exc
    return artifacts


def verify_existing(path: Path, artifact: dict) -> bool:
    if not os.path.lexists(path):
        return False
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size != artifact["bytes"]:
        raise FetchError("existing artifact does not match the lock; refusing overwrite")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            total += len(chunk)
            if total > artifact["bytes"]:
                raise FetchError("existing artifact grew during verification")
            digest.update(chunk)
    if total != artifact["bytes"] or digest.hexdigest() != artifact["sha256"]:
        raise FetchError("existing artifact does not match the lock; refusing overwrite")
    os.chmod(path, 0o600)
    return True


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise FetchError("destination directory must not be a symlink")
    if not path.exists():
        private_directory(path.parent)
        path.mkdir(mode=0o700)
    if not path.is_dir():
        raise FetchError("destination must be a directory")
    # Change only the requested destination; existing ancestors are untouched.


def client_context(*, strict=False, cafile=None):
    """Keep platform trust and optionally require 128-bit transport security.

    OpenSSL security level 3 rejects RSA/DH keys below 3072 bits (including
    marginal keys rounded by level 2), short EC keys and static RSA exchange.
    Preserve a stronger system policy and its existing cipher selection.
    """
    context = ssl.create_default_context(cafile=cafile)
    context.minimum_version = max(context.minimum_version, ssl.TLSVersion.TLSv1_2)
    if strict:
        if ssl.OPENSSL_VERSION_INFO < (3, 0, 0):
            raise RuntimeError("Strict TLS requires OpenSSL 3 or newer")
        if context.security_level < 3:
            suites = ":".join(
                cipher["name"]
                for cipher in context.get_ciphers()
                if cipher["protocol"] != "TLSv1.3"
            )
            context.set_ciphers(f"{suites}:@SECLEVEL=3")
    return context


def fetch(artifact: dict, destination: Path, *, opener=None, strict_tls=False) -> Path:
    validate_url(artifact["url"], initial=True)
    private_directory(destination)
    os.chmod(destination, 0o700)
    output = destination / artifact["filename"]
    if verify_existing(output, artifact):
        return output
    opener = opener or urllib.request.build_opener(
        ReleaseRedirects(), urllib.request.HTTPSHandler(context=client_context(strict=strict_tls)))
    temporary = None
    try:
        fd, name = tempfile.mkstemp(prefix=".download-", suffix=".partial", dir=destination)
        temporary = Path(name)
        digest = hashlib.sha256()
        total = 0
        deadline = time.monotonic() + 180
        request = urllib.request.Request(artifact["url"], headers={
            "User-Agent": "ha-echomuse-pinned-fetch/1", "Accept-Encoding": "identity",
        })
        with os.fdopen(fd, "wb") as target, opener.open(request, timeout=20) as response:
            validate_url(response.geturl())
            if response.status != 200:
                raise FetchError("release server did not return a complete artifact")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or int(length) != artifact["bytes"]):
                raise FetchError("server content length does not match the lock")
            while chunk := response.read(CHUNK_BYTES):
                total += len(chunk)
                if total > artifact["bytes"]:
                    raise FetchError("download exceeds the pinned size")
                if time.monotonic() > deadline:
                    raise FetchError("download exceeded its time limit")
                digest.update(chunk)
                target.write(chunk)
            if total != artifact["bytes"] or digest.hexdigest() != artifact["sha256"]:
                raise FetchError("download size or SHA-256 does not match the lock")
            target.flush()
            os.fsync(target.fileno())
        # Hard-link creation is atomic and refuses an existing destination,
        # including one created by a different process during this download.
        os.link(temporary, output)
        return output
    except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
        raise FetchError("download failed; existing artifacts were not overwritten") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("artifacts", nargs="*", help="artifact names; defaults to all locked artifacts")
    cli.add_argument("--lock", type=Path, default=ROOT / "upstream-lock.json")
    cli.add_argument("--destination", type=Path, default=ROOT / "private/artifacts")
    cli.add_argument("--strict-tls", action="store_true",
                     help="Require OpenSSL 3 and a 128-bit minimum transport security profile")
    args = cli.parse_args(argv)
    try:
        artifacts = load_artifacts(args.lock)
        selected = args.artifacts or list(artifacts)
        if any(name not in artifacts for name in selected):
            raise FetchError("unknown artifact name")
        for name in selected:
            result = fetch(artifacts[name], args.destination, strict_tls=args.strict_tls)
            print(f"Verified {name}: {result.name} ({artifacts[name]['bytes']} bytes)")
    except FetchError as exc:
        print(f"Artifact fetch failed: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("Artifact fetch failed: cannot access private destination storage", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
