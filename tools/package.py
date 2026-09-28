#!/usr/bin/env python3
"""Build clean artifacts from the explicit publication manifest."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'dist');a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    m=json.loads((ROOT/'PUBLICATION_MANIFEST.json').read_text())
    entries=m['files']+[{'path':'PUBLICATION_MANIFEST.json'}]
    zpath=out/'KINTSUGI_JARVIS_PORTFOLIO_1_0.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for e in sorted(entries,key=lambda e:e['path']):
            p=ROOT/e['path'];b=p.read_bytes()
            if 'sha256' in e and hashlib.sha256(b).hexdigest()!=e['sha256']:raise ValueError('Hash mismatch: '+e['path'])
            info=zipfile.ZipInfo(e['path'],date_time=(2026,9,28,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,b)
    skill=out/'KINTSUGI_SPARK_CALIBRATION_SKILL.zip'
    with zipfile.ZipFile(skill,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted((ROOT/'skills/kintsugi-jarvis-core').glob('*')):
            if p.is_file():z.write(p,p.name)
    (out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (zpath,skill)))
    print((out/'SHA256SUMS.txt').read_text(),end='')
if __name__=='__main__':main()
