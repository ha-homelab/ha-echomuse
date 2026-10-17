"""Feature-cache integrity tests use temporary bytes, never private recordings."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "feature_provenance", ROOT / "training/feature_provenance.py")
provenance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provenance)


class FeatureProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.assets = self.work / "assets"
        self.assets.mkdir()
        for name in ("melspectrogram.onnx", "embedding_model.onnx"):
            (self.assets / name).write_bytes(b"fake model")
        self.source = self.work / "source.wav"
        self.source.write_bytes(b"fake recorded audio")
        self.recipe = self.work / "preparation.py"
        self.recipe.write_text("# initial preparation recipe")
        self.rows = [{"id": "clip-1", "path": str(self.source), "split": "train",
                      "sha256": provenance.digest(self.source), "speech_end": 1.0}]
        self.manifest = self.work / "sources.json"
        self.manifest.write_text(json.dumps(self.rows))

    def cache(self):
        return provenance.PreparationCache(
            self.work, "train", self.rows, self.assets, [self.recipe])

    def complete(self):
        cache = self.cache()
        target = cache.destination / "clip-1.npz"
        provenance.atomic_write(target, lambda stream: stream.write(b"fake features"))
        receipt = cache.finish()
        return cache, target, receipt

    def test_verified_cache_reuses_only_unchanged_sources_inputs_and_outputs(self):
        cache, target, receipt = self.complete()
        self.assertEqual(receipt["outputs"], {target.name: provenance.digest(target)})
        original = cache.receipt_path.read_bytes()
        reused = self.cache()
        self.assertTrue(reused.reused)
        self.assertEqual(cache.receipt_path.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "must not be rewritten"):
            reused.finish()

    def test_changed_manifest_assets_and_preparation_reject_existing_cache(self):
        self.complete()
        for path in (self.manifest, self.assets / "embedding_model.onnx", self.recipe):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, "fresh work directory"):
                    self.cache()
                path.write_bytes(original)

    def test_changed_or_missing_source_cannot_reuse_cache(self):
        self.complete()
        self.source.write_bytes(b"changed audio")
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()

    def test_generation_reads_only_the_hashed_source_bytes(self):
        self.assertEqual(provenance.source_bytes(self.rows[0]), self.source.read_bytes())
        self.source.write_bytes(b"different audio")
        with self.assertRaisesRegex(ValueError, "Source recording changed"):
            provenance.source_bytes(self.rows[0])

    def test_changed_missing_or_extra_features_cannot_reuse_cache(self):
        cache, target, _ = self.complete()
        original = target.read_bytes()
        target.write_bytes(b"modified features")
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()
        target.unlink()
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()
        target.write_bytes(original)
        (cache.destination / ".unfinished.partial").write_bytes(b"partial")
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()

    def test_interrupted_and_legacy_cache_require_fresh_directory(self):
        cache = self.cache()
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()
        (cache.destination / "clip-1.npz").write_bytes(b"old features")
        cache.receipt_path.write_text(json.dumps({
            "split": "train", "sources": 1,
            "source_manifest_sha256": provenance.digest(self.manifest)}))
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()

    def test_failed_atomic_write_leaves_no_partial_output_or_receipt(self):
        cache = self.cache()
        target = cache.destination / "clip-1.npz"

        def interrupted(stream):
            stream.write(b"partial features")
            raise OSError("simulated disk failure")

        with self.assertRaisesRegex(OSError, "simulated"):
            provenance.atomic_write(target, interrupted)
        self.assertFalse(target.exists())
        self.assertEqual(list(cache.destination.iterdir()), [])
        self.assertFalse(cache.receipt_path.exists())
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()

    def test_inputs_changed_during_generation_do_not_receive_receipt(self):
        cache = self.cache()
        (cache.destination / "clip-1.npz").write_bytes(b"features")
        self.manifest.write_text(self.manifest.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            cache.finish()
        self.assertFalse(cache.receipt_path.exists())

    def test_source_changed_during_generation_does_not_receive_receipt(self):
        cache = self.cache()
        (cache.destination / "clip-1.npz").write_bytes(b"features")
        self.source.write_bytes(b"changed while preparing")
        with self.assertRaisesRegex(ValueError, "Source recording changed"):
            cache.finish()
        self.assertFalse(cache.receipt_path.exists())

    def test_rows_must_match_the_hashed_manifest(self):
        self.manifest.write_text(json.dumps([{**self.rows[0], "speech_end": 2.0}]))
        with self.assertRaisesRegex(ValueError, "fresh work directory"):
            self.cache()


class FreezeProvenanceTests(unittest.TestCase):
    def test_missing_or_wrong_recipe_manifest_hash_fails_before_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "sources.json").write_text("[]")
            candidate = work / "candidate"
            candidate.mkdir()
            for recipe, expected in (({}, "no source manifest hash"),
                                     ({"source_manifest_sha256": "wrong"}, "changed since training")):
                with self.subTest(recipe=recipe):
                    (candidate / "recipe.json").write_text(json.dumps(recipe))
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "training/freeze_oww.py"),
                         "--work", str(work), "--candidate", "candidate"],
                        capture_output=True, text=True, check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(expected, result.stderr)
                    self.assertFalse((candidate / "freeze.json").exists())


if __name__ == "__main__":
    unittest.main()
