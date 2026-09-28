"""Four local reproductions of the review. No credentials, network or user data.
This script deliberately reports whether the vulnerable behavior is observed.
"""
import argparse, json, sys, tempfile, uuid
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
sys.path.insert(0,str(Path(a.source).resolve()))
from jarvis.common import *
from jarvis.authority import Authority
from jarvis.calendar import Broker,SimCalendar,GoogleCalendar,make_proposal
from jarvis.household import Household
NOW=instant('2026-09-24T13:00:00Z');PW='synthetic-only-operator-password'
results=[]
def add(id, reproduced, evidence):results.append({'finding':id,'vulnerable_behavior_reproduced':bool(reproduced),'observed':evidence})
with tempfile.TemporaryDirectory() as d:
 root=Path(d);auth=Authority(root/'auth');auth.initialize(PW);provider=SimCalendar(root/'sim');b=Broker(auth,provider);auth.resume(PW)
 p=make_proposal('private-demo',{'summary':'Synthetic test','start':'2026-09-25T13:00:00Z','end':'2026-09-25T14:00:00Z'},'expired')
 ctx,_=b.prepare(p);token=auth.grant(p,ctx,PW,now=NOW,ttl_seconds=1)
 clock={'now':NOW};original=b.prepare
 def slow_prepare(p):
  result=original(p);clock['now']=NOW+timedelta(seconds=2);return result
 b.prepare=slow_prepare
 with patch('jarvis.calendar.now_utc',side_effect=lambda:clock['now']):
  try:r=b.execute(p,token)
  except Refused as e:r={'status':'REFUSED','reason':str(e)}
 add('F01_DISPATCH_EXPIRY',r['status']=='PROVIDER_VERIFIED',{'result':r['status'],'approval_expires':iso(NOW+timedelta(seconds=1)),'clock_after_preparation':iso(clock['now']),'provider_object_exists':provider.get(p['target'],p['event_id']) is not None})
 auth.close();provider.close()

with tempfile.TemporaryDirectory() as d:
 root=Path(d);auth=Authority(root/'auth');auth.initialize(PW);stored={}
 def http(method,url,body,headers):
  if '/acl' in url:return 200,{'items':[{'role':'owner','scope':{'type':'user','value':'test@example.invalid'}}]}
  if method=='GET':return 404,{}
  raise UnknownOutcome('Synthetic timeout: outcome remains uncertain')
 google=GoogleCalendar(lambda:'never-used',['allowed'],http);b=Broker(auth,google,live_enabled=True);auth.resume(PW)
 p=make_proposal('allowed',{'summary':'Original Google operation','start':'2026-09-25T13:00:00Z','end':'2026-09-25T14:00:00Z'},'wrong-provider')
 t=auth.grant(p,b.prepare(p)[0],PW,now=NOW);initial=b.execute(p,t,NOW)
 fake=SimCalendar(root/'unrelated-provider');fake.db.execute('INSERT INTO events VALUES(?,?,1,?)',(p['target'],p['event_id'],canonical(p['payload'])))
 b.adapter=fake
 try:r=b.reconcile(p['operation_key'])
 except Refused as e:r={'status':'REFUSED','reason':str(e)}
 add('F02_RECOVERY_PROVIDER_SUBSTITUTION',r['status']=='PROVIDER_VERIFIED',{'original_provider':'google_calendar_https','substituted_provider':fake.name,'before':initial['status'],'after':r['status']})
 auth.close();fake.close()

with tempfile.TemporaryDirectory() as d:
 h=Household(d)
 routine={'id':'maintenance','version':1,'title':'Private synthetic routine','anchor':'completion','timezone':'America/Chicago','first_due':iso(NOW),'interval':24,'interval_semantics':'elapsed_hours','window_minutes':120,'full_steps':['Brush teeth','Prepare clothes'],'minimum_steps':['Brush teeth'],'max_nudges':2,'quiet_start':'23:00','quiet_end':'06:00','kind':'ordinary'}
 h.configure_routine(routine,NOW);row=h.tick(NOW)['occurrences'][0]
 h.command({'command_id':'minimum-day-1','op':'simplify'},NOW)
 # The V3.1 app enqueues only these fields: no original time or displayed variant.
 queued={'command_id':'done-offline-day-1','op':'done','object_id':row['id'],'expected_revision':row['revision']}
 received=NOW+timedelta(days=1)
 h.command(queued,received);s=h.tick(received);done=h._get('occurrences',row['id']);child=next(x for x in s['occurrences'] if x['id']!=row['id'])
 add('F03_OFFLINE_COMPLETION_CONTEXT',done['completed_at']==iso(received) and done['completion_version']=='full',{'human_action_time':iso(NOW),'reconnection_time':iso(received),'saved_completed_at':done['completed_at'],'saved_variant':done['completion_version'],'next_due':child['due']})
 h.close()

calls=[];obj=None
def transport(method,url,body,headers):
 global obj
 calls.append((method,url,body,headers))
 if method=='GET':return 200,obj
 if method=='POST':obj=dict(body,id=body['id'],etag='"1"');return 201,{}
 if method=='PATCH':obj.update(body);obj['etag']='"2"';return 200,{}
g=GoogleCalendar(lambda:'never-used',['allowed'],transport)
p=make_proposal('allowed',{'summary':'Before','start':'2026-09-25T13:00:00Z','end':'2026-09-25T14:00:00Z'},'create')
g.apply(p);obj['reminders']={'useDefault':False,'overrides':[{'method':'popup','minutes':30}]}
u=make_proposal('allowed',dict(p['payload'],summary='After'),'update',event_id=p['event_id'],expected_version='"1"')
g.apply(u)
add('F04_UNAPPROVED_REMINDER_CLEAR',obj['reminders'].get('overrides')==[],{'requested_fields':sorted(u['payload']),'wire_fields':sorted(calls[-1][2]),'reminders_after':obj['reminders']})
report={'source_path':str(Path(a.source).resolve()),'scope':'LOCAL_SYNTHETIC_REPRODUCTIONS','findings':results,'reproduced':sum(x['vulnerable_behavior_reproduced'] for x in results),'live_provider_calls':0,'account_mutations':0}
Path(a.out).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
