#!/usr/bin/env python3
"""Verify intended publication bytes; not a publisher-authentication mechanism."""
from pathlib import Path,PurePosixPath
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    data=json.loads((ROOT/'PUBLICATION_MANIFEST.json').read_text())
    seen=set();bad=[]
    for item in data['files']:
        rel=item['path'];p=PurePosixPath(rel);f=ROOT/rel
        if p.is_absolute() or '..' in p.parts or '\\' in rel or rel in seen or f.is_symlink():
            raise ValueError('Unsafe/duplicate manifest path: '+rel)
        seen.add(rel)
        if not f.is_file() or not f.resolve().is_relative_to(ROOT):bad.append(rel);continue
        b=f.read_bytes()
        if len(b)!=item['bytes'] or hashlib.sha256(b).hexdigest()!=item['sha256']:bad.append(rel)
    print(json.dumps({'files_checked':len(seen),'mismatches':bad,'valid':not bad,'scope':'Manifest-listed publication files; runtime/output/git files not certified.','publisher_authenticated':False},indent=2))
    return bool(bad)
if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError) as exc:print(str(exc),file=sys.stderr);raise SystemExit(2)
