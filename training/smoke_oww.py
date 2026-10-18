"""Verify training/checkpoint/export compatibility using synthetic features only."""
from pathlib import Path
import tempfile

import numpy as np
import onnx
import torch

from train_oww import Classifier, export_classifier, predict
from oww_features import session


def main():
    torch.set_num_threads(2)
    torch.manual_seed(20261018)
    rng = np.random.default_rng(20261018)
    features = rng.normal(size=(8, 16, 96)).astype(np.float32)
    model = Classifier(width=32, dropout=0)
    initial = {key: value.clone() for key, value in model.state_dict().items()}
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
    labels = torch.arange(8).remainder(2).float().reshape(-1, 1)
    for _ in range(3):
        optimizer.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy(model(torch.from_numpy(features)), labels)
        loss.backward()
        optimizer.step()
    assert torch.isfinite(loss), "Non-finite training loss"
    assert any(not torch.equal(value, initial[key]) for key, value in model.state_dict().items())
    model.eval()
    with tempfile.TemporaryDirectory(prefix="echomuse-synthetic-") as directory:
        checkpoint = Path(directory) / "weights.pt"
        target = Path(directory) / "classifier.onnx"
        torch.save(model.state_dict(), checkpoint)
        restored = Classifier(width=32, dropout=0).eval()
        restored.load_state_dict(torch.load(checkpoint, weights_only=True, map_location="cpu"))
        np.testing.assert_array_equal(predict(model, features), predict(restored, features))
        export_classifier(restored, torch.zeros(1, 16, 96), target)
        graph = onnx.load(str(target))
        onnx.checker.check_model(graph)
        assert [(item.domain, item.version) for item in graph.opset_import] == [("", 17)]
        runtime = session(target)
        worst_delta = 0.0
        for count in (1, 3, 8):
            sample = features[:count]
            expected = predict(restored, sample)
            actual = runtime.run(None, {"input": sample})[0].reshape(-1)
            assert actual.shape == (count,)
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-5)
            np.testing.assert_array_equal(actual >= .5, expected >= .5)
            worst_delta = max(worst_delta, float(np.max(np.abs(actual - expected))))
    print(f"Synthetic training, checkpoint and dynamic-batch ONNX parity passed; max delta={worst_delta:.3g}")


if __name__ == "__main__":
    main()
