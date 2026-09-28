#!/usr/bin/env python3
"""Run two existing end-to-end synthetic demos; no server or account required."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
for folder,args in [('household',['scripts/demo_workflows.py']),('bridge',['-m','kintsugi_bridge','demo'])]:
    print('\n=== '+folder.upper()+' / SYNTHETIC DATA ONLY ===',flush=True)
    subprocess.run([sys.executable,*args],cwd=ROOT/'components'/folder,
      env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),check=True,timeout=60)
