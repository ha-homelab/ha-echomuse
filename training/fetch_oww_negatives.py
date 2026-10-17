"""Fetch a bounded training subset and the separate openWakeWord validation set.

The source feature dataset is CC BY-NC-SA 4.0, not the repository code license:
https://huggingface.co/datasets/davidscripka/openwakeword_features
No personal recordings are uploaded. Run only into an ignored private directory.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np

REVISION = "985bf1b47e7f19c07741af82bfe32d5a9dc56096"
BASE = f"https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/{REVISION}/"
TRAIN = "openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
VALIDATION = "validation_set_features.npy"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--expand", action="store_true", help="Add 900,000 non-overlapping training windows")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    pattern = "negative-train-extra-*.npy" if args.expand else "negative-*.npy"
    if list(args.work.glob(pattern)):
        raise SystemExit("Refusing to overwrite existing negative data")

    def fetch(item):
        index, start = item
        count = 90000 if args.expand else 10000
        first = 128 + start*3072
        last = first + count*3072-1
        query = f"expand={index}" if args.expand else f"block={index}"
        req = urllib.request.Request(BASE+TRAIN+"?"+query,
                                     headers={"Range":f"bytes={first}-{last}"})
        with urllib.request.urlopen(req,timeout=120) as response:
            if response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {first}-{last}/"):
                raise RuntimeError("Server did not honor requested byte range")
            data = response.read(count*3072+1)
        if len(data) != count*3072:
            raise RuntimeError("Incomplete or oversized training block")
        suffix = f"extra-{index}" if args.expand else str(index)
        np.save(args.work/f"negative-train-{suffix}.npy",np.frombuffer(data,dtype="<f2").reshape(count,16,96))
        return {"index":index,"start_row":start,"rows":count,"sha256":hashlib.sha256(data).hexdigest()}

    with ThreadPoolExecutor(max_workers=3) as pool:
        offset = 30000 if args.expand else 20000
        rows = list(pool.map(fetch,enumerate([offset+i*550000 for i in range(10)])))
    if args.expand:
        (args.work/"expanded-negative-provenance.json").write_text(json.dumps(rows,indent=2))
        print("Added 900,000 disjoint training windows; validation unchanged.")
        return
    destination = args.work/"negative-validation.npy"
    partial = destination.with_suffix(".partial")
    with urllib.request.urlopen(BASE+VALIDATION+"?full=1",timeout=120) as response, partial.open("xb") as stream:
        for block in iter(lambda:response.read(1024*1024),b""):
            stream.write(block)
    data = np.load(partial,mmap_mode="r")
    if data.shape != (481345,96) or data.dtype != np.dtype("float32"):
        raise RuntimeError("Unexpected validation shape or dtype")
    del data
    partial.rename(destination)
    provenance = {"repository":"davidscripka/openwakeword_features","revision":REVISION,
                  "training_blocks":rows,"validation_sha256":hashlib.sha256(destination.read_bytes()).hexdigest()}
    (args.work/"negative-provenance.json").write_text(json.dumps(provenance,indent=2))
    print("Downloaded 100,000 training windows and separate validation features.")


if __name__ == "__main__":
    main()
