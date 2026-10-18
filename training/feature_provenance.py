"""Standard-library provenance and atomic writes for private feature caches."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_bytes(row):
    """Return precisely the source bytes whose manifest hash was checked."""
    raw = Path(row["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Source recording changed: " + row["id"])
    return raw


def atomic_write(path, writer):
    """Publish a complete file, keeping partial output out of the cache."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix="." + path.name + ".",
                                         suffix=".partial", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class PreparationCache:
    """Reuse only a complete cache tied to unchanged inputs and outputs.

    An interrupted run has no completion receipt. It is intentionally not
    resumed: use a fresh work directory instead of blessing partial features.
    """
    def __init__(self, work, split, rows, assets, preparation_files):
        self.work, self.split, self.rows = Path(work), split, rows
        self.assets = Path(assets)
        self.preparation_files = tuple(Path(p) for p in preparation_files)
        self.destination = self.work / f"features-{split}"
        self.receipt_path = self.work / f"prepare-{split}.json"
        self.names = set()
        for row in rows:
            ident = row["id"]
            if (not isinstance(ident, str) or not ident or ident in (".", "..")
                    or "/" in ident or "\\" in ident or ident + ".npz" in self.names):
                raise ValueError("Invalid or duplicate source identifier")
            self.names.add(ident + ".npz")
        self.identity = self._identity()
        self.reused = False
        if self.destination.exists() or self.receipt_path.exists():
            try:
                receipt = json.loads(self.receipt_path.read_text())
                if any(receipt.get(k) != v for k, v in self.identity.items()):
                    raise ValueError("Inputs or preparation code differ")
                if set(receipt["outputs"]) != self.names:
                    raise ValueError("Feature inventory differs")
                self._verify_sources()
                if self._output_hashes() != receipt["outputs"]:
                    raise ValueError("Feature content differs")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise ValueError("Feature cache is stale, incomplete or unverifiable; "
                                 "use a fresh work directory") from exc
            self.reused = True
        else:
            self.destination.mkdir(mode=0o700)

    def _identity(self):
        manifest = (self.work / "sources.json").read_bytes()
        if [row for row in json.loads(manifest) if row["split"] == self.split] != self.rows:
            raise ValueError("Source manifest rows changed; use a fresh work directory")
        return {"format_version": 1, "split": self.split, "sources": len(self.rows),
                "source_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "assets": {n: digest(self.assets / n) for n in
                           ("melspectrogram.onnx", "embedding_model.onnx")},
                "preparation": {p.name: digest(p) for p in self.preparation_files}}

    def _verify_sources(self):
        for row in self.rows:
            if digest(row["path"]) != row["sha256"]:
                raise ValueError("Source recording changed: " + row["id"])

    def _output_hashes(self):
        if {p.name for p in self.destination.iterdir()} != self.names:
            raise ValueError("Incomplete or unexpected feature files")
        return {name: digest(self.destination / name) for name in sorted(self.names)}

    def finish(self):
        if self.reused:
            raise ValueError("A verified cache must not be rewritten")
        if self._identity() != self.identity:
            raise ValueError("Preparation inputs changed; use a fresh work directory")
        self._verify_sources()
        receipt = {**self.identity, "outputs": self._output_hashes()}
        raw = json.dumps(receipt, indent=2).encode()
        atomic_write(self.receipt_path, lambda stream: stream.write(raw))
        return receipt
