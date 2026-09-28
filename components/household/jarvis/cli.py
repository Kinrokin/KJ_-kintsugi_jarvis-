from __future__ import annotations
import argparse, json, sys, uuid, platform
from pathlib import Path
from datetime import timedelta
from zoneinfo import ZoneInfo
from .common import *
from .household import Household
from .finance import affordability, classify_inflows
from .operations import read_policy_fixture, value_report

def emit(value):print(json.dumps(value,indent=2,ensure_ascii=False))
def demo(root):
    h=Household(root);now=now_utc();local=(now-timedelta(minutes=5)).astimezone(ZoneInfo('America/Chicago'))
    base={'version':1,'anchor':'clock','timezone':'America/Chicago','window_minutes':120,'full_steps':['Brush teeth','Get clothes ready','Check the next commitment'],
          'minimum_steps':['Brush teeth'],'max_nudges':2,'quiet_start':'23:00','quiet_end':'06:00','kind':'ordinary','fold':0,'gap':'shift_forward'}
    if not h.db.execute('SELECT 1 FROM routines').fetchone():
        h.configure_routine(dict(base,id='demo-reset',title='Private reset — demonstration',wall_time=local.strftime('%H:%M')),now)
        h.configure_routine(dict(base,id='demo-evening',title='Evening — demonstration',wall_time='20:00'),now)
        h.import_email('synthetic-mailbox','demo-form',{'title':'Demo school form','outcome':'The form was actually submitted','deadline':iso(now+timedelta(days=2))},now)
    h.tick(now);h.close()

def main(argv=None):
    ap=argparse.ArgumentParser(description='Kintsugi local household controls. No automatic external account actions.')
    ap.add_argument('--state',default=str(Path.home()/'KintsugiJarvis'/'household-v3_2'))
    sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('doctor');sub.add_parser('init');sub.add_parser('status');sub.add_parser('tick')
    d=sub.add_parser('demo');d.add_argument('--serve',action='store_true');d.add_argument('--port',type=int,default=8765)
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=8765)
    q=sub.add_parser('phone-trial',help='Explicit private HTTPS trial; requires an already trusted certificate')
    q.add_argument('--host',required=True);q.add_argument('--port',type=int,default=8766)
    q.add_argument('--cert',required=True);q.add_argument('--key',required=True);q.add_argument('--origin',required=True)
    q.add_argument('--ack-private-lan',action='store_true')
    for name in ['routine','command','forecast','inflows']:

        q=sub.add_parser(name);q.add_argument('file')
    q=sub.add_parser('capture');q.add_argument('text')
    q=sub.add_parser('email');q.add_argument('file');q.add_argument('--mailbox',required=True);q.add_argument('--message-id',required=True)
    q=sub.add_parser('policy-probe');q.add_argument('file');q.add_argument('--sha256',required=True)
    q=sub.add_parser('measure');q.add_argument('kind');q.add_argument('value',type=int)
    q=sub.add_parser('backup');q.add_argument('destination')
    q=sub.add_parser('inspect-v2');q.add_argument('database')
    a=ap.parse_args(argv)
    if a.cmd=='doctor':
        tz=True
        try:ZoneInfo('America/Chicago')
        except Exception:tz=False
        emit({'python':platform.python_version(),'platform':platform.platform(),'timezone_data':tz,'python_minimum':'3.10',
              'live_connections':'NOT_CHECKED','schedules':'NOT_CREATED','voice_wakeword':'NOT_IMPLEMENTED',
              'next':'Timezone data may need an approved tzdata install on Windows' if not tz else 'Ready for local demo'})
        if not tz:raise Refused('IANA timezone data is missing; no installation was performed')
        return
    if a.cmd=='policy-probe':emit(read_policy_fixture(a.file,a.sha256));return
    if a.cmd in {'forecast','inflows'}:
        data=strict_json(Path(a.file).read_text());emit(affordability(data) if a.cmd=='forecast' else classify_inflows(data));return
    if a.cmd=='inspect-v2':
        from .migration import inspect_v2_database
        emit(inspect_v2_database(a.database));return
    if a.cmd=='demo':
        # This creates examples, never user commitments or native scheduled tasks.
        demo(a.state)
        if a.serve:
            from .web import serve
            serve(a.state,a.port)
        else:emit({'demo_state':str(Path(a.state).resolve()),'synthetic':True,'external_changes':0})
        return
    if a.cmd=='phone-trial':
        from .web import serve_phone_trial
        serve_phone_trial(a.state,a.host,a.port,a.cert,a.key,a.origin,ack_private_lan=a.ack_private_lan);return
    if a.cmd=='serve':
        from .web import serve
        serve(a.state,a.port);return
    h=Household(a.state)
    try:
        if a.cmd=='init':emit({'state':str(h.root),'schema':'3.1','runtime_version':'3.2.0','writes':'local_only'})
        elif a.cmd=='status':emit(h.snapshot())
        elif a.cmd=='tick':emit(h.tick())
        elif a.cmd=='routine':h.configure_routine(strict_json(Path(a.file).read_text()));emit({'saved':True,'external_schedules_created':0})
        elif a.cmd=='command':emit(h.command(strict_json(Path(a.file).read_text())))
        elif a.cmd=='capture':emit(h.command({'command_id':str(uuid.uuid4()),'op':'capture','text':a.text}))
        elif a.cmd=='email':emit({'obligation_id':h.import_email(a.mailbox,a.message_id,strict_json(Path(a.file).read_text())),'status':'CANDIDATE'})
        elif a.cmd=='measure':h.measure(a.kind,a.value);emit(value_report(h.snapshot()['measurements']))
        elif a.cmd=='backup':
            from .migration import backup_household
            emit(backup_household(h,a.destination))
    finally:h.close()
if __name__=='__main__':
    try:main()
    except (Refused,ValueError,KeyError,FileNotFoundError) as e:print('REFUSED: '+str(e),file=sys.stderr);sys.exit(2)
