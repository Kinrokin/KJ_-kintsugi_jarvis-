"""Package consistency only, not publisher authentication. No network use."""
from pathlib import Path,PurePosixPath
import hashlib
import json
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]

def verify(root:Path)->dict:
    manifest=json.loads((root/'MANIFEST.json').read_text())
    expected={}
    for entry in manifest['files']:
        rel=entry['path'];pp=PurePosixPath(rel)
        if pp.is_absolute() or '..' in pp.parts or '\\' in rel or rel != pp.as_posix() or rel in expected:
            raise ValueError('unsafe or duplicate manifest path')
        expected[rel]=entry
    actual=set()
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('symlink in package')
        if p.is_file() and p != root/'MANIFEST.json':
            if '__pycache__' in p.parts and p.suffix=='.pyc':continue
            actual.add(p.relative_to(root).as_posix())
    if actual!=set(expected):raise ValueError('missing or unexpected package files')
    for rel,entry in expected.items():
        raw=(root/rel).read_bytes()
        if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
            raise ValueError('file mismatch: '+rel)
    return {'result':'PASS','manifested_files':len(expected),'publisher_authentication':False}

if __name__=='__main__':
    try:
        print(json.dumps(verify(ROOT),indent=2))
    except (OSError,ValueError,KeyError) as exc:
        print('MANIFEST_VERIFICATION_FAILED: '+str(exc),file=sys.stderr);raise SystemExit(1)
