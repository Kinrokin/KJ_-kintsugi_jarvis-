#!/usr/bin/env python3
"""Reproduce the public edition with temporary fixtures and no live providers."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
ROOT=Path(__file__).resolve().parents[1]
def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'local-evidence')
    args=parser.parse_args();out=args.out.resolve()
    try:
        ZoneInfo('America/Chicago')
    except ZoneInfoNotFoundError:
        print('IANA timezone data is missing. Install/enable it only through your approved environment. No automatic install.',file=sys.stderr)
        return 2
    out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    # No deployment settings, provider tokens, paid services or user schedules are used.
    for key in ('OPENAI_API_KEY','GOOGLE_APPLICATION_CREDENTIALS','GITHUB_TOKEN','GH_TOKEN'):
        env.pop(key,None)
    plan=[
      ('household-tests','components/household',['scripts/run_tests.py','--out',str(out/'household')]),
      ('bridge-tests','components/bridge',['scripts/run_tests.py','--json',str(out/'bridge/results.json')]),
      ('household-cli','components/household',['scripts/cli_smoke.py','--out',str(out/'household/CLI_RESULTS.json')]),
      ('household-workflows','components/household',['scripts/demo_workflows.py','--out',str(out/'household/WORKFLOW_RESULTS.json')]),
      ('bridge-demo','components/bridge',['-m','kintsugi_bridge','demo']),
      ('publication-checks','.', ['tools/check_publication.py']),
    ]
    runs=[]
    for name,folder,cmd in plan:
        t=time.monotonic()
        try:
            p=subprocess.run([sys.executable,*cmd],cwd=ROOT/folder,env=env,
                             capture_output=True,text=True,timeout=180)
            code=p.returncode;text=p.stdout+p.stderr
        except subprocess.TimeoutExpired:
            code=124;text='TIMEOUT: stopped waiting after 180 seconds.\n'
        # Normalize sandbox path without fabricating successful output.
        text=text.replace(str(ROOT),'<REPOSITORY>')
        (out/(name+'.log')).write_text(text,encoding='utf-8')
        runs.append({'name':name,'command':['python',*['<OUTPUT>/'+str(x).split(str(out)+'/',1)[1] if str(x).startswith(str(out)+'/') else x for x in cmd]],'cwd':folder,'returncode':code,'seconds':round(time.monotonic()-t,3)})
        print(name+(': PASS' if code==0 else ': FAIL'))
        if code:print(text[-3000:],file=sys.stderr)
    h=json.loads((out/'household/TEST_RESULTS.json').read_text()) if (out/'household/TEST_RESULTS.json').exists() else {}
    b=json.loads((out/'bridge/results.json').read_text()) if (out/'bridge/results.json').exists() else {}
    summary={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'REPRODUCED_LOCAL_SYNTHETIC_PUBLICATION','python':platform.python_version(),'platform':platform.platform(),
      'household':{k:h.get(k) for k in ('tests','failures','errors','skips','generated_iterations')},
      'bridge':{k:b.get(k) for k in ('tests','failures','errors','skipped','loop_cases_within_tests')},
      'runs':runs,'all_passed':all(x['returncode']==0 for x in runs),'live_accounts_accessed':False,'live_notifications_sent':False,'independent_audit':False}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return 0 if summary['all_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
