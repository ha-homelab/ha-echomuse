"""Import existing, consented recordings and Russian synthesis; preserve splits.

Outputs contain personal voice features and must remain in ignored private/.
No recording, network access, or deployment is performed by this program.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import threading

import numpy as np
from scipy.signal import resample, fftconvolve
import soundfile as sf

from oww_features import Features, windows
from feature_provenance import PreparationCache, atomic_write, digest, source_bytes


def import_sources(legacy):
    rows = []
    alignment = {}
    alignment_root = legacy / "private/mac-owner-training-20261003/train-asr-v1"
    for path in alignment_root.glob("train-privet_myshka-*.json"):
        item = json.loads(path.read_text())
        alignment[item["id"]] = max(segment["end"] for segment in item["segments"])
    recordings = legacy / "private/mac-wakeword-recordings"
    for meta in sorted(recordings.glob("takes/*/metadata.json")):
        m = json.loads(meta.read_text())
        if not m["selected"]:
            continue
        p = recordings / m["path"]
        assert digest(p) == m["sha256"], p
        rows.append(dict(id=m["id"], path=str(p.resolve()), label=m["intended_labels"]["privet_myshka"],
                         split=m["split"], kind="owner", text=m["intended_text"],
                         session=m["session_id"], sha256=m["sha256"],
                         speech_end=alignment.get(m["id"])))
    synthesis = legacy / "private/wakeword-training/data-generation"
    for line in (synthesis / "manifest-full.jsonl").read_text().splitlines():
        m = json.loads(line)
        p = synthesis / m["path"]
        assert digest(p) == m["sha256"], p
        rows.append(dict(id=m["source_id"], path=str(p.resolve()), label=m["label"],
                         split=m["split"], kind="synthetic", text=m["text"],
                         session=m["voice"], sha256=m["sha256"]))
    seen = {}
    for row in rows:
        old = seen.setdefault(row["sha256"], row["split"])
        assert old == row["split"], "Source duplicated across splits"
    return rows


def augment(audio, rng):
    # Pitch and duration vary together; this is resampling augmentation, not
    # an assertion that we captured another speaker or a real room.
    rate = rng.uniform(.9, 1.1)
    audio = resample(audio, max(1, int(len(audio) / rate))).astype(np.float32)
    if rng.random() < .7:
        rir = np.zeros(int(rng.uniform(.08, .35)*16000), np.float32)
        rir[0] = 1
        for _ in range(8):
            i = int(rng.integers(160, len(rir)))
            rir[i] += rng.uniform(-.2, .3) * np.exp(-i/2500)
        audio = fftconvolve(audio, rir).astype(np.float32)
    # Preserve both low-level and ordinary speech; avoid peak normalization.
    rms = np.sqrt(np.mean(audio**2)+1e-12)
    target = 10**(rng.uniform(-46, -20)/20)
    audio *= min(target/rms, 10)
    if rng.random() < .65:
        noise = rng.normal(size=len(audio)).astype(np.float32)
        noise *= np.sqrt(np.mean(audio**2)+1e-12) / 10**(rng.uniform(15, 35)/20)
        audio += noise
    return np.clip(audio, -.98, .98), rate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--legacy", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--split", choices=["train", "val", "test"], required=True)
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    manifest = args.work / "sources.json"
    if manifest.exists():
        rows = json.loads(manifest.read_text())
    else:
        rows = import_sources(args.legacy)
        manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    rows = [r for r in rows if r["split"] == args.split]
    cache = PreparationCache(args.work, args.split, rows, args.assets,
                             [Path(__file__), Path(__file__).with_name("oww_features.py"),
                              Path(__file__).with_name("feature_provenance.py")])
    if cache.reused:
        print(f"{args.split}: verified complete feature cache; no files changed", flush=True)
        return
    destination = cache.destination
    local = threading.local()

    def run(row):
        path = destination / (row["id"]+".npz")
        raw = source_bytes(row)
        if not hasattr(local, "extractor"):
            local.extractor = Features(args.assets)
        audio, sr = sf.read(io.BytesIO(raw), dtype="float32")
        assert sr == 16000 and audio.ndim == 1
        rng = np.random.default_rng(int(hashlib.sha256(row["id"].encode()).hexdigest()[:8], 16))
        repeats = (40 if row["kind"] == "owner" else 2) if args.split == "train" else 1
        arrays = []
        for index in range(repeats):
            x, rate = augment(audio.copy(), rng) if index else (audio, 1)
            lead = 25600
            # Round to complete frames; tail keeps every late score in validation.
            x = np.pad(x, (lead, 25600))
            x = np.pad(x, (0, (-len(x)) % 1280))
            emb = local.extractor.embeddings(np.rint(x*32767).astype(np.int16))
            frames = windows(emb)
            if args.split != "train":
                arrays.append(frames)
            elif row["label"]:
                # Estimate end from unpadded energy without throwing away onset.
                if row["kind"] == "owner":
                    if not row.get("speech_end"):
                        raise ValueError("Human positives require speech-end alignment; never label room-noise tails positive")
                    end = lead + int(row["speech_end"]*16000/rate)
                else:
                    active = np.flatnonzero(np.abs(x) > max(.0001, np.max(np.abs(x))*.035))
                    end = int(active[-1]) if len(active) else lead+len(audio)
                center = round(end/1280)-16
                ids = np.clip(np.array([center-1, center, center+1, center+2]),0,len(frames)-1)
                arrays.append(frames[ids])
            else:
                arrays.append(frames[::3])
        atomic_write(path, lambda stream: np.savez_compressed(
            stream, x=np.concatenate(arrays).astype(np.float16), label=row["label"]))

    print(dict(Counter((r["kind"], r["label"]) for r in rows)), flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, _ in enumerate(pool.map(run, rows), 1):
            if i % 200 == 0 or i == len(rows):
                print(f"{args.split}: {i}/{len(rows)}", flush=True)
    cache.finish()


if __name__ == "__main__":
    main()
