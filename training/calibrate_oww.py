"""Move a frozen decision threshold to 0.5 without retraining the classifier.

EchoMuse clamps configuration thresholds above 0.975. A model selected at a
higher threshold must not be deployed unchanged. Subtract logit(threshold)
before the final sigmoid and verify every reference decision matches.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper

from oww_features import windows, session
from train_oww import validation_data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--reference-splits", nargs="+", choices=["val", "test", "background"],
                   default=["val", "test", "background"],
                   help="Parity references; use val background when final recordings stay outside the manifest")
    args = p.parse_args()
    source = args.work/args.candidate
    freeze = json.loads((source/"freeze.json").read_text())
    original = source/"privet_myshka_20261016.onnx"
    if hashlib.sha256(original.read_bytes()).hexdigest() != freeze["sha256"]:
        raise RuntimeError("Frozen original changed")
    if hashlib.sha256((args.work/"sources.json").read_bytes()).hexdigest() != freeze["source_manifest_sha256"]:
        raise RuntimeError("Source manifest changed after selection")
    out = source/"release"
    out.mkdir(exist_ok=False)
    model = onnx.load(original)
    producers = {output:node for node in model.graph.node for output in node.output}
    sigmoid = producers[model.graph.output[0].name]
    if sigmoid.op_type != "Sigmoid":
        raise RuntimeError("Expected final sigmoid")
    threshold = freeze["threshold"]
    shift = math.log(threshold/(1-threshold))
    # An explicit logit offset also supports confirmed heads whose logits end
    # in Min rather than a single Gemm. Never shift a shared bias twice.
    offset_name, logit_name = "calibration_logit_offset", "calibrated_logits"
    used = {x.name for x in model.graph.initializer}
    used.update(x for node in model.graph.node for x in list(node.input)+list(node.output))
    if offset_name in used or logit_name in used:
        raise RuntimeError("Model already contains calibration names")
    model.graph.initializer.append(numpy_helper.from_array(np.array(-shift, np.float32), offset_name))
    offset = onnx.helper.make_node("Add", [sigmoid.input[0], offset_name], [logit_name])
    index = list(model.graph.node).index(sigmoid)
    sigmoid.input[0] = logit_name
    model.graph.node.insert(index, offset)
    props = {prop.key:prop.value for prop in model.metadata_props}
    props.update(recommended_threshold="0.5", original_threshold=str(threshold),
                 score_calibration="final logits minus logit(original_threshold)")
    onnx.helper.set_model_props(model,props)
    onnx.checker.check_model(model)
    target = out/f"privet_myshka_{freeze['sha256'][:12]}_cal.onnx"
    onnx.save(model,target)
    old,new = session(original),session(target)
    comparison = {}
    for split in dict.fromkeys(args.reference_splits):
        features = (windows(np.load(args.work/"negative-validation.npy",mmap_mode="r")) if split == "background"
                    else validation_data(args.work,split)[2])
        differences = 0
        for offset in range(0,len(features),2048):
            x = np.array(features[offset:offset+2048],np.float32)
            a = old.run(None,{"input":x})[0].reshape(-1)
            b = new.run(None,{"input":x})[0].reshape(-1)
            differences += int(np.count_nonzero((a>=threshold)!=(b>=.5)))
        comparison[split] = {"windows":len(features),"decision_differences":differences}
    if any(x["decision_differences"] for x in comparison.values()):
        raise RuntimeError(f"Decision parity failed: {comparison}")
    receipt = {"model":target.name,"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
               "source_sha256":freeze["sha256"],"threshold":.5,"original_threshold":threshold,
               "logit_shift":shift,"comparison":comparison}
    (out/"calibration.json").write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))


if __name__ == "__main__":
    main()
