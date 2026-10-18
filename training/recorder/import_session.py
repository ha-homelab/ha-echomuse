#!/usr/bin/env python3
"""Add a completed attended Dot session to a new private training manifest.

Preserves session splits and participant labels. Does not infer speech timing,
train a model, rewrite an existing manifest, or copy audio into the repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import wave


def import_session(directory, rows):
    receipt=json.loads((directory/'session.json').read_text())
    if receipt['state']!='complete' or len(receipt['takes'])!=receipt['count']:
        raise ValueError('Only a completed batch can be imported')
    split=receipt['split']
    if split not in ('train','val','test'):
        raise ValueError('Unknown split')
    existing_ids={r['id'] for r in rows}
    hashes={r['sha256']:r['split'] for r in rows}
    result=list(rows)
    for take in receipt['takes']:
        path=directory/f"{take['number']:02d}.wav"
        raw=path.read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        if sha!=take['sha256'] or take['split']!=split:
            raise ValueError('Recording changed or split mismatch')
        if take['stop_reason']!='button' or take['gaps'] or take['label']!='positive':
            raise ValueError('Not an intact, manually finished positive take')
        if take['phrase']!='Привет, Мышка':
            raise ValueError('Unexpected phrase')
        with wave.open(str(path),'rb') as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):
                raise ValueError('Unsupported WAV format')
            duration=w.getnframes()/16000
        ident=f"echo-{receipt['id']}-{take['number']:02d}"
        if ident in existing_ids or sha in hashes:
            raise ValueError('Duplicate source; do not reuse sessions across splits')
        existing_ids.add(ident);hashes[sha]=split
        result.append({'id':ident,'path':str(path.resolve()),'sha256':sha,
                       'split':split,'kind':'owner','label':1,'text':take['phrase'],
                       'session':receipt['id'],'source':take['source'],
                       'ready_offset_seconds':take['ready_offset_seconds'],
                       'duration_seconds':duration,'speech_end':None})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-manifest',type=Path,required=True)
    p.add_argument('--session-dir',type=Path,action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    rows=json.loads(a.base_manifest.read_text())
    for directory in a.session_dir:
        rows=import_session(directory,rows)
    a.output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with a.output.open('x') as f:
        a.output.chmod(0o600)
        json.dump(rows,f,ensure_ascii=False,indent=2)
    print('New private manifest written. Align training speech before preparing features.')

if __name__=='__main__':main()
