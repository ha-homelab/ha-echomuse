"""Prepare owner positives with speech-end alignment, preserving participant labels.

Quiet recordings often contain a room-noise tail. Peak-relative energy alone
can label that tail positive. Existing local ASR timestamps are used ONLY for
alignment; ASR text never replaces the participant's intended phrase.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import threading

import numpy as np
from scipy.signal import resample
import soundfile as sf

from oww_features import Features, windows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--alignments", type=Path)
    p.add_argument("--negative-only", action="store_true", help="Prepare wide-gain owner negatives; no ASR timestamps needed")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    align = {}
    if not args.negative_only and args.alignments is None:
        p.error("Positive clips require --alignments")
    for path in args.alignments.glob("train-privet_myshka-*.json") if args.alignments else []:
        row = json.loads(path.read_text())
        align[row["id"]] = max(s["end"] for s in row["segments"])
    rows = [r for r in json.loads((args.work/"sources.json").read_text())
            if r["kind"] == "owner" and r["split"] == "train" and bool(r["label"]) != args.negative_only]
    destination = args.work/("features-owner-wide" if args.negative_only else "features-owner-aligned")
    destination.mkdir(exist_ok=False)
    local = threading.local()

    def run(row):
        if not hasattr(local, "features"):
            local.features = Features(args.assets)
        source = Path(row["path"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Source recording changed")
        audio,sr = sf.read(source,dtype="float32")
        if sr != 16000 or audio.ndim != 1:
            raise ValueError("Invalid recording or speech-end alignment")
        if not args.negative_only and not 0 < align[row["id"]] <= len(audio)/sr+.1:
            raise ValueError("Invalid speech-end alignment")
        rng = np.random.default_rng(int(hashlib.sha256(row["id"].encode()).hexdigest()[:8],16)+(5000 if args.negative_only else 8070))
        parts = []
        for index in range(60 if args.negative_only else 100):
            rate = rng.uniform(.77,1.3) if args.negative_only else (1 if index == 0 else rng.uniform(.8,1.25))
            x = resample(audio,int(len(audio)/rate)).astype(np.float32)
            x *= 10**(rng.uniform(-10,10)/20) if args.negative_only else (1 if index == 0 else 10**(rng.uniform(-8,12)/20))
            x = np.pad(x,(25600,25600))
            x = np.pad(x,(0,(-len(x))%1280))
            frame = windows(local.features.embeddings(np.clip(np.rint(x*32767),-32768,32767).astype(np.int16)))
            if args.negative_only:
                parts.append(frame[::3])
            else:
                end = round(min(len(audio)/sr,align[row["id"]])*16000/rate)
                center = round((end+25600)/1280)-16
                parts.append(frame[np.clip([center-1,center,center+1,center+2],0,len(frame)-1)])
        np.savez_compressed(destination/(row["id"]+".npz"),x=np.concatenate(parts).astype(np.float16),label=row["label"])
        return {"id":row["id"],"end_seconds":align.get(row["id"]),"sha256":row["sha256"]}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run,rows))
    receipt = "owner-wide-negatives.json" if args.negative_only else "owner-alignment.json"
    (args.work/receipt).write_text(json.dumps({
        "method":"Existing local ASR timestamps only; participant labels unchanged", "rows":results},indent=2))
    print(f"Prepared {len(results)} owner training sources; holdouts untouched.")


if __name__ == "__main__":
    main()
