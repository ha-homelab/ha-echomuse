#!/usr/bin/env python3
"""Install a reviewed recorder overlay via an existing kubectl context.

Run patch_controller.py first. This changes only one deployment's pod template.
The prior deployment is saved privately for review/rollback.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

IMAGE = 'ghcr.io/wilbowes/echomuse-controller:2.26.0@sha256:3e28ccba1102b0ef1c10d3821c937730afc1fb78e5f6f3811f3860079fc0008b'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--overlay',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--namespace',default='echomuse')
    p.add_argument('--deployment',default='echomuse-controller')
    p.add_argument('--container',default='controller')
    p.add_argument('--ssh-host')
    p.add_argument('--replace-existing', action='store_true')
    args=p.parse_args()
    prefix=['ssh','-o','BatchMode=yes',args.ssh_host,'sudo','-n','k3s','kubectl'] if args.ssh_host else ['kubectl']
    def kubectl(*cmd,data=None):
        r=subprocess.run(prefix+['-n',args.namespace]+list(cmd),input=json.dumps(data) if data is not None else None,text=True,capture_output=True,check=True)
        return r.stdout
    current=json.loads(kubectl('get','deployment',args.deployment,'-o','json'))
    containers=current['spec']['template']['spec']['containers']
    index=next(i for i,c in enumerate(containers) if c['name']==args.container)
    if containers[index]['image']!=IMAGE:
        raise SystemExit('Refusing an unreviewed controller image')
    args.receipt.mkdir(parents=True,exist_ok=True,mode=0o700)
    receipt=args.receipt/'deployment-before.private.json'
    with receipt.open('x') as f:json.dump(current,f,indent=2)
    receipt.chmod(0o600)
    files={n:(args.overlay/n).read_text() for n in ('em_controller.py','em_api.py','em_training.py')}
    for name,source in files.items():compile(source,name,'exec')
    digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    name='echomuse-recorder-'+digest
    kubectl('create','-f','-',data={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name},'immutable':True,'data':files})
    spec=current['spec']['template']['spec']
    volume={'name':'training-recorder','configMap':{'name':name}}
    if any(v['name']==volume['name'] for v in spec.get('volumes',[])) and not args.replace_existing:
        raise SystemExit('Recorder overlay already installed; use --replace-existing after reviewing the update')
    previous_volumes=[v for v in spec.get('volumes',[]) if v['name']!=volume['name']]
    previous_mounts=[v for v in containers[index].get('volumeMounts',[]) if v['name']!=volume['name']]
    mounts=previous_mounts+[
        {'name':volume['name'],'mountPath':'/app/'+n,'subPath':n,'readOnly':True} for n in files]
    patch=[{'op':'test','path':'/metadata/resourceVersion','value':current['metadata']['resourceVersion']},
           {'op':'add','path':'/spec/template/spec/volumes','value':previous_volumes+[volume]},
           {'op':'add','path':f'/spec/template/spec/containers/{index}/volumeMounts','value':mounts}]
    # Send a Patch object through a temporary remote/local file's stdin: -p on
    # ssh would otherwise require shell quoting JSON. kubectl accepts --patch-file.
    kubectl('patch','deployment',args.deployment,'--type=json','--patch-file=/dev/stdin',data=patch)
    (args.receipt/'overlay.private.json').write_text(json.dumps({'configmap':name,'digest':digest},indent=2))
    print('Recorder overlay installed; wait for rollout readiness before using it.')

if __name__=='__main__':main()
