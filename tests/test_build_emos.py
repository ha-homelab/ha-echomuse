"""Safety gates around an offline image builder; no device access or downloads."""

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest import mock


MODULE = Path(__file__).resolve().parents[1] / "scripts/build_emos.py"
SPEC = importlib.util.spec_from_file_location("build_emos", MODULE)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def reference_fixture() -> bytes:
    data = bytearray(3 * 2048)
    data[:8] = b"ANDROID!"
    struct.pack_into("<I", data, 8, 16)  # kernel size
    struct.pack_into("<I", data, 16, 16)  # ramdisk size
    struct.pack_into("<I", data, 36, 2048)
    return bytes(data)


class ImageGatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = self.root / "reference.img"
        self.reference.write_bytes(reference_fixture())
        self.payload = self.root / "payload.zip"
        self.payload.write_bytes(b"unit test payload")
        self.args = argparse.Namespace(
            source_dir=self.root / "source",
            payload=self.payload,
            reference=self.reference,
            reference_sha256=hashlib.sha256(self.reference.read_bytes()).hexdigest(),
            system_part=13,
            output=self.root / "output" / "prepared.img",
        )

    def no_artifacts(self):
        self.assertFalse(self.args.output.exists())
        self.assertFalse(build.receipt_path(self.args.output).exists())

    def test_corrupt_reference_stops_before_loading_code(self):
        self.reference.write_bytes(self.reference.read_bytes() + b"corruption")
        with mock.patch.object(build, "validate_source"), mock.patch.object(build, "load_builder") as load:
            with self.assertRaisesRegex(build.PreparationError, "reference SHA-256 mismatch"):
                build.prepare(self.args)
        load.assert_not_called()
        self.no_artifacts()

    def test_corrupt_payload_stops_before_loading_code(self):
        with mock.patch.object(build, "validate_source"), mock.patch.object(build, "load_builder") as load:
            with self.assertRaisesRegex(build.PreparationError, "payload SHA-256 mismatch"):
                build.prepare(self.args)
        load.assert_not_called()
        self.no_artifacts()

    def test_hash_is_required_not_inferred_from_changed_reference(self):
        for invalid in ("", "abc", "g" * 64):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(build.PreparationError, "64 hexadecimal"):
                    build.read_verified(self.reference, invalid, "reference")

    def test_invalid_topology_number_is_rejected_before_source_lookup(self):
        for value in (0, -1, 128, True, "13"):
            with self.subTest(value=value), mock.patch.object(build, "validate_source") as source:
                self.args.system_part = value
                with self.assertRaisesRegex(build.PreparationError, "system partition"):
                    build.prepare(self.args)
                source.assert_not_called()
        for value in ("0", "128", "-1", "/dev/block/mmcblk0p13", "13.0"):
            with self.subTest(cli_value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    build.system_partition(value)
        self.no_artifacts()

    def test_existing_image_and_receipt_are_never_replaced(self):
        self.args.output.parent.mkdir()
        for existing in (self.args.output, build.receipt_path(self.args.output)):
            with self.subTest(existing=existing.name):
                existing.write_bytes(b"keep this backup")
                with self.assertRaisesRegex(build.PreparationError, "refusing overwrite"):
                    build.write_outputs(self.args.output, b"new image", {})
                self.assertEqual(existing.read_bytes(), b"keep this backup")
                existing.unlink()

    def test_dangling_output_symlink_is_also_an_existing_output(self):
        self.args.output.parent.mkdir()
        self.args.output.symlink_to(self.root / "absent")
        with self.assertRaisesRegex(build.PreparationError, "refusing overwrite"):
            build.require_new_outputs(self.args.output)
        self.assertTrue(self.args.output.is_symlink())

    def test_exclusive_write_handles_a_receipt_creation_race(self):
        self.args.output.parent.mkdir()
        original_open = os.open
        receipt = build.receipt_path(self.args.output)

        def race(path, flags, mode):
            if Path(path) == receipt:
                receipt.write_bytes(b"another writer")
            return original_open(path, flags, mode)

        with mock.patch.object(build.os, "open", side_effect=race):
            with self.assertRaises(FileExistsError):
                build.write_outputs(self.args.output, b"image", {})
        self.assertFalse(self.args.output.exists())
        self.assertEqual(receipt.read_bytes(), b"another writer")

    def test_output_files_are_private_even_with_permissive_umask(self):
        old = os.umask(0)
        try:
            build.write_outputs(self.args.output, b"image", {"prepared_only": True})
        finally:
            os.umask(old)
        for path in (self.args.output, build.receipt_path(self.args.output)):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_wrong_architecture_is_not_silently_given_a_32bit_init(self):
        upstream = mock.Mock()
        upstream.BuildError = type("BuildError", (Exception,), {})
        upstream.read_payload_bundle.return_value = {
            "version": build.EMOS_VERSION,
            "files": {name: b"data" for name in (*build.SBIN_FILES, "init32")},
        }
        upstream.reference_kernel_arch.return_value = "arm64"
        payload_hash = hashlib.sha256(self.payload.read_bytes()).hexdigest()
        with mock.patch.object(build, "validate_source"), \
             mock.patch.object(build, "load_builder", return_value=upstream), \
             mock.patch.object(build, "PAYLOAD_SHA256", payload_hash):
            with self.assertRaisesRegex(build.PreparationError, "ARM32"):
                build.prepare(self.args)
        upstream.build_emos_image.assert_not_called()
        self.no_artifacts()


class PartitionBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Disposable self-signed fixture. No private key is stored in the repo.
        with tempfile.TemporaryDirectory() as temp:
            cls.certificate = subprocess.check_output([
                "openssl", "req", "-x509", "-newkey", "rsa:1024", "-nodes",
                "-keyout", str(Path(temp) / "fixture.key"), "-outform", "DER",
                "-days", "1", "-subj", "/CN=offline-builder-test",
            ], stderr=subprocess.DEVNULL)

    def test_zero_padding_is_bounded_and_full_escrow_is_preserved(self):
        image = reference_fixture()
        escrow = image + bytes(2048)
        bounded, metadata = build.boot_image_from_escrow(escrow)
        self.assertEqual(bounded, image)
        self.assertEqual(escrow, image + bytes(2048))
        self.assertEqual(metadata["escrow_size"], len(escrow))
        self.assertEqual(metadata["reference_trailer"]["zero_padding_size"], 2048)
        self.assertEqual(metadata["bounded_reference_sha256"], hashlib.sha256(image).hexdigest())

    def test_detached_certificate_and_padding_are_classified(self):
        image = reference_fixture()
        escrow = image + self.certificate + bytes(2048)
        bounded, metadata = build.boot_image_from_escrow(escrow)
        self.assertEqual(bounded, image)
        trailer = metadata["reference_trailer"]
        self.assertEqual(trailer["kind"], "x509-der-and-zero-padding")
        self.assertEqual(trailer["certificate_size"], len(self.certificate))
        self.assertEqual(trailer["certificate_sha256"], hashlib.sha256(self.certificate).hexdigest())
        self.assertFalse(trailer["certificate_signature_verified"])

    def test_unknown_trailer_is_not_discarded(self):
        for tail in (b"unknown trailer", bytes(10) + b"unknown", self.certificate + b"unexpected"):
            with self.subTest(tail_size=len(tail)):
                with self.assertRaisesRegex(build.PreparationError, "nonzero"):
                    build.boot_image_from_escrow(reference_fixture() + tail)

    def test_der_sequence_must_actually_parse_as_x509(self):
        with self.assertRaisesRegex(build.PreparationError, "OpenSSL could not parse"):
            build.boot_image_from_escrow(reference_fixture() + b"\x30\x03\x02\x01\x01")

    def test_header_cannot_hide_truncated_regions_or_a_second_stage(self):
        for offset, value, error in ((8, 100000, "truncated"), (16, 0, "kernel and ramdisk"),
                                     (24, 1, "second-stage"), (36, 4096, "layout"),
                                     (40, 1, "layout")):
            data = bytearray(reference_fixture())
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset):
                with self.assertRaisesRegex(build.PreparationError, error):
                    build.boot_image_from_escrow(bytes(data))

    def test_missing_openssl_is_an_explicit_refusal(self):
        with mock.patch.object(build.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(build.PreparationError, "OpenSSL could not parse"):
                build.boot_image_from_escrow(reference_fixture() + self.certificate)


class SourceGatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        self.module = self.root / "controller/em_emos_build.py"
        self.module.parent.mkdir()
        self.module.write_text("# fixture, never executed\n")
        self.run_git("add", "controller/em_emos_build.py")
        self.run_git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                     "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                     "commit", "--quiet", "-m", "fixture")
        self.commit = self.run_git("rev-parse", "HEAD")

    def run_git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def test_wrong_commit_is_refused(self):
        with self.assertRaisesRegex(build.PreparationError, "pinned to"):
            build.validate_source(self.root)

    def test_modified_tracked_file_is_refused(self):
        self.module.write_text("raise RuntimeError('changed')\n")
        with mock.patch.object(build, "SOURCE_COMMIT", self.commit):
            with self.assertRaisesRegex(build.PreparationError, "modified tracked"):
                build.validate_source(self.root)

    def test_assume_unchanged_does_not_hide_modified_executable_source(self):
        self.run_git("update-index", "--assume-unchanged", "controller/em_emos_build.py")
        self.module.write_text("raise RuntimeError('hidden change')\n")
        with mock.patch.object(build, "SOURCE_COMMIT", self.commit):
            with self.assertRaisesRegex(build.PreparationError, "committed blob"):
                build.validate_source(self.root)

    def test_subdirectory_is_not_accepted_as_checkout_root(self):
        with mock.patch.object(build, "SOURCE_COMMIT", self.commit):
            with self.assertRaisesRegex(build.PreparationError, "root of the upstream"):
                build.validate_source(self.module.parent)

    def test_clean_commit_is_accepted_and_untracked_notes_are_not_executed(self):
        (self.root / "private-note.txt").write_text("not source code\n")
        with mock.patch.object(build, "SOURCE_COMMIT", self.commit):
            self.assertEqual(build.validate_source(self.root), self.module)


if __name__ == "__main__":
    unittest.main()
