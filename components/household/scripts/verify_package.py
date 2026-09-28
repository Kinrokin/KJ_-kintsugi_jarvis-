#!/usr/bin/env python3
"""Verify file membership, sizes and hashes. This is integrity, not publisher identity."""
import argparse,hashlib,json,sys
from pathlib import Path

def verify(root,expected_manifest=None):
    root=Path(root).resolve();mp=root/'MANIFEST.json'
    if not mp.is_file() or mp.is_symlink():raise ValueError('Manifest absent or symlinked')
    blob=mp.read_bytes();mh=hashlib.sha256(blob).hexdigest()
    if expected_manifest and mh!=expected_manifest:raise ValueError('Manifest differs from separately retained digest')
    manifest=json.loads(blob);seen=set();fail=[]
    for f in manifest['files']:
        rel=f['path'];p=Path(rel)
        if p.is_absolute() or '..' in p.parts or '\\' in rel or ':' in rel or rel in seen:raise ValueError('Unsafe/duplicate manifest path')
        seen.add(rel);full=root/p
        if full.is_symlink() or not full.is_file() or not full.resolve().is_relative_to(root):fail.append(rel+':missing_or_escape');continue
        b=full.read_bytes()
        if len(b)!=f['bytes'] or hashlib.sha256(b).hexdigest()!=f['sha256']:fail.append(rel+':mismatch')
    extras=[]
    for p in root.rglob('*'):
        rel=p.relative_to(root).as_posix()
        if p.is_symlink():extras.append(rel+':symlink')
        elif p.is_file() and rel!='MANIFEST.json' and '__pycache__' not in p.parts and rel not in seen:extras.append(rel)
    return {'valid':not fail and not extras,'checked_files':len(seen),'failures':fail,'unexpected_files':extras,'manifest_sha256':mh,
            'authenticity':'Not digitally signed. A co-replaced archive and manifest can pass; retain the external digest independently.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',nargs='?',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--expected-manifest');a=p.parse_args()
    try:r=verify(a.root,a.expected_manifest);print(json.dumps(r,indent=2));sys.exit(0 if r['valid'] else 2)
    except (ValueError,OSError,KeyError) as e:print('FAILED:',str(e));sys.exit(2)
