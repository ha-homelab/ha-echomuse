"""Evaluate a frozen candidate against held-out clips, speech and synthetic noise."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from oww_features import Features, windows, session
from train_oww import validation_data, summarize, events


def infer(runtime, x):
    return np.concatenate([runtime.run(None, {"input":np.array(x[i:i+2048], np.float32)})[0].reshape(-1)
                           for i in range(0,len(x),2048)])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--candidate", default="candidate-1")
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--legacy", type=Path, required=True)
    p.add_argument("--controls-only", action="store_true",
                   help="Evaluate noise/continuous-speech controls; use a separate fresh recording session for final positives")
    args = p.parse_args()
    out = args.work/args.candidate
    freeze = json.loads((out/"freeze.json").read_text())
    model = out/"privet_myshka_20261016.onnx"
    if hashlib.sha256(model.read_bytes()).hexdigest() != freeze["sha256"]:
        raise RuntimeError("Frozen candidate changed")
    if hashlib.sha256((args.work/"sources.json").read_bytes()).hexdigest() != freeze["source_manifest_sha256"]:
        raise RuntimeError("Source manifest changed after selection")
    report_path = out/("controls.json" if args.controls_only else "test.json")
    if report_path.exists():
        raise RuntimeError("Final test is immutable; use a new independent test for another selection")
    threshold = freeze["threshold"]
    runtime = session(model)
    if args.controls_only:
        report = {"threshold":threshold, "controls_only":True}
    else:
        rows, offsets, features = validation_data(args.work,"test")
        report = summarize(rows,offsets,infer(runtime,features),None,threshold)
    extractor = Features(args.assets)
    controls = {}
    rng = np.random.default_rng(80917)
    t = np.arange(16000*30)/16000
    for name,pcm in {
        "digital_silence":np.zeros(len(t)),
        "low_white_noise":rng.normal(0,20,len(t)),
        "moderate_white_noise":rng.normal(0,300,len(t)),
        "mains_hum":300*np.sin(2*np.pi*60*t)+100*np.sin(2*np.pi*120*t),
        "pinkish_noise":np.convolve(rng.normal(0,500,len(t)),np.ones(20)/20,mode="same"),
    }.items():
        scores = infer(runtime,windows(extractor.embeddings(pcm)))
        controls[name] = {"seconds":30,"events":events(scores,threshold),"max_score":float(scores.max())}
    report["synthetic_controls"] = controls
    # Continuous held-out speech: overlap aligned to 80 ms keeps the complete
    # 1.96-second receptive field. Discard warmup outputs of later blocks.
    speech = args.legacy/"private/wakeword-training/librispeech"
    items = [json.loads(s) for s in (speech/"test_clean_continuous_at_least_1h.jsonl").read_text().splitlines()]
    audio = []
    for item in items:
        x,sr = sf.read(speech/item["path"],dtype="int16")
        if sr != 16000 or x.ndim != 1:
            raise ValueError("Speech format mismatch")
        audio.append(x)
    audio = np.concatenate(audio)
    scores = []
    block,overlap = 16000*24,1280*32
    for start in range(0,len(audio),block):
        left=max(0,start-overlap)
        part=windows(extractor.embeddings(audio[left:start+block]))
        if start:
            # Window 0 ends at left+1.28 s; first new score ends start+0.08 s.
            part=part[overlap//1280-15:]
        scores.append(infer(runtime,part))
        if start//block % 20 == 0:
            print(f"Speech checked: {min(start+block,len(audio))/16000:.0f}s",flush=True)
    scores=np.concatenate(scores)
    report["continuous_speech"]={"seconds":len(audio)/16000,"events":events(scores,threshold),
                                 "max_score":float(scores.max()),"sources":len(items)}
    report["model_sha256"]=freeze["sha256"]
    report_path.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != "clips"}),flush=True)


if __name__ == "__main__":
    main()
