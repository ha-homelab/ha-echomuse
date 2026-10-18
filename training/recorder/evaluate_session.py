#!/usr/bin/env python3
"""Evaluate a completed, independent final recording batch after freezing.

A positive-only batch measures recall, not false-wake rate. Reuse the separate
negative/audio regression gates before deciding whether to deploy a model.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oww_features import Features, windows, session
from import_session import import_session


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--session-dir',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True)
    args=p.parse_args()
    freeze=json.loads((args.candidate/'freeze.json').read_text())
    model=args.candidate/'privet_myshka_20261016.onnx'
    if hashlib.sha256(model.read_bytes()).hexdigest()!=freeze['sha256']:
        raise ValueError('Frozen model changed')
    prior_path=args.candidate.parent/'sources.json'
    if hashlib.sha256(prior_path.read_bytes()).hexdigest()!=freeze['source_manifest_sha256']:
        raise ValueError('Training/validation manifest changed')
    prior=json.loads(prior_path.read_text())
    receipt=json.loads((args.session_dir/'session.json').read_text())
    if receipt['split']!='test':
        raise ValueError('This is not a final-test session')
    rows=import_session(args.session_dir,prior)[len(prior):]
    output=args.candidate/'recorded-final-test.json'
    if output.exists():
        raise ValueError('Final recorded test is immutable')
    features=Features(args.assets);runtime=session(model)
    scores=[]
    for row in rows:
        x,sr=sf.read(row['path'],dtype='int16')
        if sr!=16000 or x.ndim!=1:raise ValueError('Invalid source audio')
        # Same 1.6 s padding and 80 ms frame alignment as prepare_oww.py.
        pcm=np.pad(x,(25600,25600))
        pcm=np.pad(pcm,(0,(-len(pcm))%1280))
        windows_=windows(features.embeddings(pcm))
        maximum=float(runtime.run(None,{'input':np.asarray(windows_,np.float32)})[0].max())
        scores.append({'id':row['id'],'sha256':row['sha256'],'max_score':maximum,
                       'detected':maximum>=freeze['threshold']})
    report={'model_sha256':freeze['sha256'],'threshold':freeze['threshold'],
            'source_session':receipt['id'],'positive_only':True,'total':len(scores),
            'detected':sum(r['detected'] for r in scores),'clips':scores}
    with output.open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='clips'}))

if __name__=='__main__':main()
