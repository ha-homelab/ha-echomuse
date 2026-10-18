"""Train a private Russian openWakeWord classifier and select on validation only.

Source clips and all their augmentations retain their original partition.
The model and extracted voice features are private artifacts, not repository files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import onnx
import torch
from torch import nn

from oww_features import windows, session


class Classifier(nn.Module):
    def __init__(self, width=128, dropout=.1):
        super().__init__()
        self.layers = nn.Sequential(nn.Flatten(), nn.Linear(1536, width), nn.LayerNorm(width),
                                    nn.ReLU(), nn.Dropout(dropout), nn.Linear(width, width), nn.LayerNorm(width),
                                    nn.ReLU(), nn.Dropout(dropout), nn.Linear(width, 1))

    def forward(self, x):
        return torch.sigmoid(self.layers(x))


def densify_negatives(x):
    """Recover skipped 80 ms windows only across exactly overlapping frames.

    The preparation stage stores every third negative window. All intermediate
    embeddings are still present in the 16-frame windows. Exact equality avoids
    interpolating across source/augmentation boundaries.
    """
    same = np.all(x[:-1,3:,:] == x[1:,:-3,:], axis=(1,2))
    a,b=x[:-1][same],x[1:][same]
    one=np.concatenate([a[:,1:],b[:,-3:-2]],axis=1)
    two=np.concatenate([a[:,2:],b[:,-3:-1]],axis=1)
    return np.concatenate([x,one,two])


def predict(model, features):
    scores = []
    with torch.inference_mode():
        for i in range(0, len(features), 2048):
            x = torch.from_numpy(np.array(features[i:i+2048], dtype=np.float32))
            scores.append(model(x).numpy().reshape(-1))
    return np.concatenate(scores) if scores else np.empty(0)


def events(scores, threshold):
    """Device's 1.5-second refractory at an 80 ms score cadence."""
    last = -100
    count = 0
    for index in np.flatnonzero(scores >= threshold):
        if index-last >= 19:
            count += 1
            last = index
    return count


def validation_data(work, split):
    rows = [r for r in json.loads((work/"sources.json").read_text()) if r["split"] == split]
    offsets, parts, total = [], [], 0
    for row in rows:
        part = np.load(work/f"features-{split}"/(row["id"]+".npz"))["x"]
        offsets.append((total, total+len(part)))
        total += len(part)
        parts.append(part)
    return rows, offsets, np.concatenate(parts)


def summarize(rows, offsets, scores, background, threshold):
    maxima = np.array([scores[a:b].max() for a,b in offsets])
    report = {"threshold": float(threshold), "clips": []}
    for kind in ("owner", "synthetic"):
        for label in (0, 1):
            keep = np.array([r["kind"] == kind and r["label"] == label for r in rows])
            report[f"{kind}_{'positive' if label else 'negative'}"] = {
                "total": int(keep.sum()), "triggered": int((maxima[keep] >= threshold).sum()),
                "min_score": float(maxima[keep].min()), "max_score": float(maxima[keep].max())}
    report["clips"] = [dict(id=r["id"], kind=r["kind"], label=r["label"], score=float(s))
                       for r,s in zip(rows,maxima)]
    if background is not None:
        report["background_hours"] = len(background)*.08/3600
        report["background_events"] = events(background, threshold)
        report["background_events_per_hour"] = report["background_events"]/report["background_hours"]
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--candidate", default="candidate-1")
    p.add_argument("--steps", type=int, default=4000)
    p.add_argument("--seed", type=int, default=20261016)
    p.add_argument("--negative-weight", type=float, default=50)
    p.add_argument("--learning-rate", type=float, default=.0002)
    p.add_argument("--width", type=int, default=128)
    p.add_argument("--dropout", type=float, default=.1)
    p.add_argument("--selection-owner-recall", type=float, default=.875,
                   help="Minimum owner recall for ranking validation candidates; does not relax freeze gates")
    p.add_argument("--owner-extra", type=Path)
    p.add_argument("--owner-aligned", type=Path)
    p.add_argument("--initialize-from", type=Path,
                   help="Private raw classifier checkpoint to fine-tune (before score calibration)")
    p.add_argument("--completed-phrase-only", action="store_true",
                   help="Keep only the last two of each four aligned positive windows, after phrase completion")
    args = p.parse_args()
    if not 0 < args.selection_owner_recall <= 1:
        p.error("Selection owner recall must be in (0, 1]")
    manifest_hash = hashlib.sha256((args.work/"sources.json").read_bytes()).hexdigest()
    for split in ("train", "val"):
        receipt = json.loads((args.work/f"prepare-{split}.json").read_text())
        if receipt["source_manifest_sha256"] != manifest_hash:
            raise RuntimeError("Prepared features do not match the source manifest")
        if len(list((args.work/f"features-{split}").glob("*.npz"))) != receipt["sources"]:
            raise RuntimeError("Incomplete feature preparation")
    output = args.work/args.candidate
    output.mkdir(exist_ok=False)
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    model = Classifier(args.width,args.dropout)
    if args.initialize_from:
        model.load_state_dict(torch.load(args.initialize_from, weights_only=True, map_location="cpu"))
    opt = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=.01)
    recipe = {k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}
    recipe["source_manifest_sha256"] = manifest_hash
    if args.initialize_from:
        recipe["initial_checkpoint_sha256"] = hashlib.sha256(args.initialize_from.read_bytes()).hexdigest()
    (output/"recipe.json").write_text(json.dumps(recipe,indent=2))
    parts = {0: [], 1: []}
    source_rows = {r["id"]:r for r in json.loads((args.work/"sources.json").read_text()) if r["split"] == "train"}
    owner_ids = {r["id"] for r in source_rows.values() if r["kind"] == "owner"}
    owner_positive_ids = {r["id"] for r in source_rows.values() if r["kind"] == "owner" and r["label"]}
    if args.owner_aligned:
        if {path.stem for path in args.owner_aligned.glob("*.npz")} != owner_positive_ids:
            raise RuntimeError("Aligned data must contain exactly the training owner positives")
    elif any(not source_rows[key].get("speech_end") for key in owner_positive_ids):
        raise RuntimeError("Legacy owner features have no safe alignment; supply --owner-aligned")
    owner_parts = []
    paths = list((args.work/"features-train").glob("*.npz"))
    if args.owner_extra:
        paths += list(args.owner_extra.glob("*.npz"))
    if args.owner_aligned:
        paths += list(args.owner_aligned.glob("*.npz"))
    for path in sorted(paths):
        data = np.load(path)
        label = int(data["label"])
        if path.stem not in source_rows or source_rows[path.stem]["label"] != label:
            raise RuntimeError("Unexpected source or held-out data in training features")
        if (args.owner_aligned and label == 1 and path.stem in owner_ids
                and path.parent != args.owner_aligned):
            continue
        features = data["x"]
        if label == 1 and args.completed_phrase_only:
            if len(features) % 4:
                raise RuntimeError("Completed-phrase selection requires four-window alignment groups")
            # Preparation emits center-1, center, center+1, center+2, where
            # center is rounded speech end. The final two windows end at least
            # 40 ms after that estimate; the first can end before the suffix.
            features = features.reshape(-1, 4, 16, 96)[:, 2:].reshape(-1, 16, 96)
        parts[label].append(densify_negatives(features) if label == 0 else features)
        if int(data["label"]) == 1 and path.stem in owner_ids:
            owner_parts.append(features)
    hard = np.concatenate(parts[0])
    positive = np.concatenate(parts[1])
    owner_positive = np.concatenate(owner_parts)
    del parts
    general = np.concatenate([np.load(p) for p in sorted(args.work.glob("negative-train-*.npy"))])
    rows, offsets, val = validation_data(args.work, "val")
    background = windows(np.load(args.work/"negative-validation.npy", mmap_mode="r"))
    print(json.dumps({"positive_windows":len(positive),"hard_negative_windows":len(hard),
                      "general_negative_windows":len(general)}),flush=True)
    best = None
    mined = np.arange(len(general))
    mined_hard = np.arange(len(hard))
    started = time.monotonic()
    for step in range(1, args.steps+1):
        model.train()
        x = np.concatenate([positive[rng.integers(len(positive),size=32)],
                            owner_positive[rng.integers(len(owner_positive),size=32)],
                            hard[rng.integers(len(hard),size=64)],
                            hard[rng.choice(mined_hard,size=64)],
                            general[rng.integers(len(general),size=192)],
                            general[rng.choice(mined,size=128)]],axis=0).astype(np.float32)
        y = torch.zeros((len(x),1)); y[:64] = 1
        logits = model.layers(torch.from_numpy(x))
        weight = torch.ones_like(y)*(1+(args.negative_weight-1)*step/args.steps)
        weight[:64] = 1
        loss = nn.functional.binary_cross_entropy_with_logits(logits,y,weight=weight)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 1000 != 0:
            continue
        model.eval()
        vs = predict(model,val)
        bs = predict(model,background)
        gs = predict(model,general)
        mined = np.argpartition(gs,-5000)[-5000:]
        hs = predict(model,hard)
        mined_hard = np.argpartition(hs,-min(5000,len(hs)))[-5000:]
        possibilities = []
        for threshold in [.5,.6,.7,.8,.85,.9,.93,.95,.97,.98,.99,.995,.999]:
            report = summarize(rows,offsets,vs,bs,threshold)
            op,sp = report["owner_positive"],report["synthetic_positive"]
            false = report["owner_negative"]["triggered"]+report["synthetic_negative"]["triggered"]
            passed = (false == 0 and report["background_events_per_hour"] <= .3
                      and op["triggered"] == op["total"] and sp["triggered"]/sp["total"] >= .9)
            # Noise gate first, then owner recall and synthetic recall; fixed
            # threshold grid avoids presenting a fitted cutoff as universal.
            usable = (op["triggered"]/op["total"] >= args.selection_owner_recall
                      and sp["triggered"]/sp["total"] >= .9)
            rank = (passed, usable, -false-report["background_events_per_hour"],
                    op["triggered"]/op["total"], sp["triggered"]/sp["total"], -threshold)
            possibilities.append((rank, report))
        rank,report = max(possibilities,key=lambda x:x[0])
        report["step"] = step
        (output/f"validation-{step}.json").write_text(json.dumps(report,indent=2))
        if best is None or rank > best:
            best = rank
            torch.save(model.state_dict(),output/"selected.pt")
            (output/"selected.json").write_text(json.dumps(report,indent=2))
        compact = {k:v for k,v in report.items() if k != "clips"}
        compact.update(loss=float(loss.detach()), elapsed=round(time.monotonic()-started,1))
        print(json.dumps(compact),flush=True)
    model.load_state_dict(torch.load(output/"selected.pt",weights_only=True))
    model.eval()
    report = json.loads((output/"selected.json").read_text())
    target = output/"privet_myshka_20261016.onnx"
    example = torch.zeros((1,16,96))
    torch.onnx.export(model,example,str(target),input_names=["input"],output_names=["score"],
                      dynamic_axes={"input":{0:"batch"},"score":{0:"batch"}},opset_version=17)
    artifact = onnx.load(str(target))
    onnx.helper.set_model_props(artifact, {"wake_word":"Привет, Мышка","language":"ru",
        "recommended_threshold":str(report["threshold"]),"training":"personal-local-20261016",
        "license":"CC-BY-NC-SA-4.0; private personal voice model"})
    onnx.checker.check_model(artifact)
    onnx.save(artifact,str(target))
    sess = session(target)
    sample = np.array(val[:200],np.float32)
    onnx_scores = sess.run(None,{"input":sample})[0].reshape(-1)
    delta = float(np.max(np.abs(onnx_scores-predict(model,sample))))
    assert delta < 1e-5, delta
    (output/"export.json").write_text(json.dumps({"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
        "bytes":target.stat().st_size,"max_pytorch_onnx_delta":delta,"validation":{
            k:v for k,v in report.items() if k != "clips"}},indent=2))
    print("Exported",str(target),flush=True)


if __name__ == "__main__":
    main()
