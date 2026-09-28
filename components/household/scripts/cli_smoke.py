#!/usr/bin/env python3
"""Exercise real CLI subprocesses in temporary local state. Synthetic inputs only."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out');args=ap.parse_args();results=[]
    with tempfile.TemporaryDirectory() as tmp:
        t=Path(tmp);state=t/'house'
        def call(*a):
            p=subprocess.run([sys.executable,'-m','jarvis.cli','--state',str(state),*a],cwd=ROOT,capture_output=True,text=True,timeout=10,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            if p.returncode:raise RuntimeError('CLI failed: '+' '.join(a)+'\n'+p.stderr)
            value=json.loads(p.stdout);results.append({'command':a[0],'status':'PASS'});return value
        call('doctor');call('init');call('routine',str(ROOT/'examples/routine_morning.json'));call('tick')
        c=call('capture','Synthetic thought for a local smoke test')
        cp=t/'command.json';cp.write_text(json.dumps({'command_id':'smoke-make-task','op':'make_task','object_id':c['id']}));call('command',str(cp))
        call('email',str(ROOT/'examples/email_claim.json'),'--mailbox','synthetic','--message-id','smoke-email')
        s=call('status');assert len(s['obligations'])==2
        d=json.loads((ROOT/'config/POLICY_PROBE_DIGEST.json').read_text());call('policy-probe',str(ROOT/d['file']),'--sha256',d['sha256'])
        call('backup',str(t/'backup.sqlite3'));call('measure','review_seconds','12')
        now=datetime.now(timezone.utc);day=now.date().isoformat()
        f={'as_of':now.isoformat(),'balance_source':'source_reported','coverage_complete':True,'obligations_complete':True,'currency':'USD','cash_cents':100000,'protected_floor_cents':20000,'horizon_start':day,'horizon_end':(now+timedelta(days=7)).date().isoformat(),'events':[],'purchase':{'date':day,'amount_cents':10000}}
        fp=t/'forecast.json';fp.write_text(json.dumps(f));assert call('forecast',str(fp))['verdict']=='CASH_COVERED_WITHIN_VERIFIED_HORIZON'
        ip=t/'inflows.json';ip.write_text(json.dumps([{'id':'synthetic-pay','amount_cents':-10000,'pending':False,'linked_own_counterpart':False,'classification':'income','confidence':'HIGH'}]));assert call('inflows',str(ip))['confirmed_income_cents']==10000
        call('demo')
    out={'scope':'ACTUAL_LOCAL_CLI_SUBPROCESSES_SYNTHETIC_INPUTS','checks':results,'check_count':len(results),'external_provider_calls':0,'external_mutations':0,'all_passed':True}
    print(json.dumps(out,indent=2))
    if args.out:Path(args.out).write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
