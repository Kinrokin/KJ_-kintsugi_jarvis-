#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jarvis.runtime import load_config,atomic_private
from jarvis.service_plan import plans
from jarvis.common import Refused
p=argparse.ArgumentParser(description='Writes setup plans only. Does not install or start any task/service.')
p.add_argument('--config',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
try:
    c=load_config(a.config);v=plans(a.config,c['home'])
    if a.out.exists() and any(a.out.iterdir()):raise Refused('Plan directory must be new/empty; no overwrites')
    a.out.mkdir(parents=True,exist_ok=True)
    atomic_private(a.out/'WINDOWS_AUTOSTART.ps1',v['windows_powershell'])
    atomic_private(a.out/(v['name'].lower()+'.service'),v['systemd_user_unit'])
    atomic_private(a.out/'PLAN.json',json.dumps({k:v[k] for k in ('name','applied')},indent=2))
    print(json.dumps({'directory':str(a.out),'name':v['name'],'installed':False,'running':False,'review':'docs/OPERATIONS_AND_AUTOSTART.md'},indent=2))
except (Refused,OSError) as e:print(str(e),file=sys.stderr);sys.exit(1)
