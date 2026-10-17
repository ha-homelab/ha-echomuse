"""Export an experimental wake head that checks two overlapping views.

The second view shifts the 16 embeddings by one frame and repeats the oldest
embedding at its boundary. It approximates a preceding view; it is NOT access
to an actual seventeenth embedding or a firmware consecutive-frame counter.
Selection still uses validation only. Fresh final recordings remain required.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import torch
from torch import nn

from evaluate_oww import infer
from oww_features import session, windows
from train_oww import Classifier, validation_data, summarize


class ConfirmedClassifier(nn.Module):
    def __init__(self, classifier):
        super().__init__()
        self.classifier = classifier

    def forward(self, x):
        preceding = torch.cat((x[:, :1, :], x[:, :-1, :]), dim=1)
        current = self.classifier.layers(x)
        earlier = self.classifier.layers(preceding)
        return torch.sigmoid(torch.minimum(current, earlier))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--source-candidate', required=True)
    p.add_argument('--candidate', required=True)
    p.add_argument('--threshold', type=float, required=True,
                   help='Operating point selected using development data only')
    a = p.parse_args()
    if not 0 < a.threshold < 1:
        p.error('Threshold must be in (0, 1)')
    source = a.work/a.source_candidate
    recipe = json.loads((source/'recipe.json').read_text())
    manifest_hash = hashlib.sha256((a.work/'sources.json').read_bytes()).hexdigest()
    if recipe.get('source_manifest_sha256') != manifest_hash:
        raise ValueError('Source checkpoint belongs to a different manifest')
    checkpoint = source/'selected.pt'
    base = Classifier(recipe['width'], recipe['dropout'])
    base.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cpu'))
    torch.set_num_threads(2)
    model = ConfirmedClassifier(base).eval()
    output = a.work/a.candidate
    output.mkdir(exist_ok=False)
    target = output/'privet_myshka_20261016.onnx'
    torch.onnx.export(model, torch.zeros((1, 16, 96)), str(target),
                      input_names=['input'], output_names=['score'],
                      dynamic_axes={'input': {0: 'batch'}, 'score': {0: 'batch'}},
                      opset_version=17)
    artifact = onnx.load(str(target))
    onnx.helper.set_model_props(artifact, {
        'wake_word': 'Привет, Мышка', 'language': 'ru',
        'recommended_threshold': str(a.threshold),
        'confirmation': 'minimum of current and one-frame shifted views; repeated oldest embedding',
        'license': 'CC-BY-NC-SA-4.0; private personal voice model',
    })
    onnx.checker.check_model(artifact)
    onnx.save(artifact, str(target))
    runtime = session(target)
    original = session(source/'privet_myshka_20261016.onnx')
    rows, offsets, val = validation_data(a.work, 'val')
    background = windows(np.load(a.work/'negative-validation.npy', mmap_mode='r'))
    scores = []
    comparisons = {}
    for name, features in [('val', val), ('background', background)]:
        values = infer(runtime, features)
        max_error = 0.0
        differences = 0
        for i in range(0, len(features), 2048):
            x = np.array(features[i:i+2048], np.float32)
            shifted = np.concatenate((x[:, :1], x[:, :-1]), axis=1)
            reference = np.minimum(infer(original, x), infer(original, shifted))
            actual = values[i:i+len(x)]
            max_error = max(max_error, float(np.max(np.abs(reference-actual))))
            differences += int(np.count_nonzero((reference >= a.threshold) != (actual >= a.threshold)))
        if max_error > 1e-5 or differences:
            raise RuntimeError(f'Confirmation export parity failed for {name}')
        comparisons[name] = {'windows': len(values), 'max_error': max_error,
                             'decision_differences': differences}
        scores.append(values)
    report = summarize(rows, offsets, scores[0], scores[1], a.threshold)
    report['step'] = json.loads((source/'selected.json').read_text())['step']
    (output/'selected.json').write_text(json.dumps(report, indent=2))
    (output/'recipe.json').write_text(json.dumps({
        'source_manifest_sha256': manifest_hash,
        'source_checkpoint': str(checkpoint),
        'source_checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        'method': 'minimum of current and one-frame shifted views; repeated oldest embedding',
        'threshold': a.threshold, 'fresh_final_required': True,
    }, indent=2))
    exported = {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'bytes': target.stat().st_size, 'confirmation_parity': comparisons,
                'validation': {k: v for k, v in report.items() if k != 'clips'}}
    (output/'export.json').write_text(json.dumps(exported, indent=2))
    print(json.dumps(exported, indent=2))


if __name__ == '__main__':
    main()
