"""Freeze a validation-selected model before opening the final test set."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--minimum-owner-recall", type=float, default=1.0)
    p.add_argument("--note", default="")
    args = p.parse_args()
    if not 0 < args.minimum_owner_recall <= 1:
        p.error("Recall must be in (0, 1]")
    if args.minimum_owner_recall < 1 and not args.note.strip():
        p.error("A lower owner-recall target requires an explicit recorded note")
    out = args.work/args.candidate
    manifest_hash = hashlib.sha256((args.work/"sources.json").read_bytes()).hexdigest()
    recipe = json.loads((out/"recipe.json").read_text())
    if not recipe.get("source_manifest_sha256"):
        raise SystemExit("Training recipe has no source manifest hash; do not freeze this candidate")
    if recipe["source_manifest_sha256"] != manifest_hash:
        raise SystemExit("Source manifest changed since training; do not freeze this candidate")
    report = json.loads((out/"selected.json").read_text())
    owner,synthetic = report["owner_positive"],report["synthetic_positive"]
    passed = (owner["triggered"]/owner["total"] >= args.minimum_owner_recall
              and synthetic["triggered"]/synthetic["total"] >= .9
              and report["owner_negative"]["triggered"] == 0
              and report["synthetic_negative"]["triggered"] == 0
              and report["background_events_per_hour"] <= .3)
    if not passed:
        raise SystemExit("Validation gates failed; model must not proceed to deployment")
    model = out/"privet_myshka_20261016.onnx"
    freeze = {"sha256":hashlib.sha256(model.read_bytes()).hexdigest(),
              "threshold":report["threshold"],"validation_step":report["step"],
              "source_manifest_sha256":manifest_hash,
              "minimum_owner_recall":args.minimum_owner_recall,"note":args.note,
              "live_acoustic_acceptance":False}
    with (out/"freeze.json").open("x") as stream:
        json.dump(freeze,stream,indent=2)
    print(json.dumps(freeze,indent=2))


if __name__ == "__main__":
    main()
