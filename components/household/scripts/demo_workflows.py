#!/usr/bin/env python3
"""Run three actual local workflows against SYNTHETIC sources only. No account access."""
import argparse,json,tempfile,sys,uuid
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from jarvis.common import instant,iso
from jarvis.household import Household
from jarvis.authority import Authority
from jarvis.calendar import SimCalendar,Broker,make_proposal

def run():
    now=instant('2026-09-24T13:15:00Z');pw='synthetic-demo-password-no-real-authority'
    with tempfile.TemporaryDirectory() as t:
        root=Path(t);h=Household(root/'household');a=Authority(root/'authority');provider=SimCalendar(root/'provider')
        try:
            routine=json.loads((ROOT/'examples/routine_morning.json').read_text());h.configure_routine(routine,now);h.tick(now)
            oid=h.snapshot(now)['occurrences'][0]['id']
            def occurrence(op,**kw):return h.command(dict(command_id=str(uuid.uuid4()),op=op,object_id=oid,expected_revision=h._get('occurrences',oid)['revision'],**kw),now)
            h.command({'command_id':'minimum','op':'simplify'},now);occurrence('snooze',minutes=15);occurrence('done')
            assert h._get('occurrences',oid)['completion_version']=='minimum'
            occurrence('undo');assert h._get('occurrences',oid)['status']=='OPEN'
            occurrence('done')
            ob=h.import_email('synthetic-gmail','form-1',{'title':'Demo form','outcome':'Form submitted','deadline':iso(now+timedelta(days=1))},now)
            def obligation(op,**kw):return h.command(dict(command_id=str(uuid.uuid4()),op=op,object_id=ob,expected_revision=h._get('obligations',ob)['revision'],**kw),now)
            obligation('accept',criteria=['Form submitted'])
            a.initialize(pw);b=Broker(a,provider);a.resume(pw)
            p=make_proposal('private-demo',{'summary':'Demo reminder only','start':'2026-09-25T13:00:00Z','end':'2026-09-25T13:30:00Z'},'demo-calendar-once',obligation_id=ob)
            token=a.grant(p,b.prepare(p)[0],pw,now=now)
            result=b.execute(p,token,now);assert result['status']=='PROVIDER_VERIFIED'
            h.record_automation(p['id'],result,now);assert h._get('obligations',ob)['status']=='OPEN'
            obligation('condition',condition='Form submitted',value=True);obligation('complete_obligation')
            q=make_proposal('private-demo',dict(p['payload'],summary='Timeout demonstration'),'demo-timeout-once')
            provider.fault='after';tkn=a.grant(q,b.prepare(q)[0],pw,now=now);unknown=b.execute(q,tkn,now);assert unknown['status']=='UNKNOWN_EXTERNAL'
            reconciled=b.reconcile(q['operation_key']);assert reconciled['status']=='PROVIDER_VERIFIED'
            count=provider.db.execute('SELECT count(*) FROM events').fetchone()[0];assert count==2
            return {'scope':'EXECUTED_LOCAL_WORKFLOWS_WITH_SYNTHETIC_PROVIDER','routine':'minimum_done_undo_done','obligation':'accepted_conditions_reported_done_not_calendar_implied','calendar':'create_readback_and_timeout_reconciliation','provider_objects':count,'production_external_effects':0,'all_assertions_passed':True}
        finally:h.close();a.close();provider.close()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out');args=ap.parse_args();result=run();text=json.dumps(result,indent=2);print(text)
    if args.out:Path(args.out).write_text(text+'\n')
if __name__=='__main__':main()
