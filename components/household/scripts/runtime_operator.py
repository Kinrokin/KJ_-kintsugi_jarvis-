#!/usr/bin/env python3
"""Explicit local operator entry point. Never prints credentials except show-login in a TTY."""
import argparse,copy,json,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jarvis.common import *
from jarvis.runtime import *

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path)
    sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('init');q.add_argument('--home',required=True)
    for name in ('doctor','run','once','status','pause-network','resume-network','show-login','watchdog'):sub.add_parser(name)
    q=sub.add_parser('retention-plan');q.add_argument('--days',type=int,default=90)
    q=sub.add_parser('retention-apply');q.add_argument('--plan',type=Path,required=True);q.add_argument('--confirm',required=True)
    args=p.parse_args()
    if args.command=='init':
        if args.config.exists():raise Refused('Existing config preserved; do not initialize over it')
        c=copy.deepcopy(DEFAULT_CONFIG);c['home']=str(Path(args.home).expanduser().absolute())
        
        with InstanceLock(c['home']):result=initialize(c)
        args.config.parent.mkdir(parents=True,exist_ok=True);atomic_private(args.config,canonical(c)+'\n')
        print(json.dumps(result,indent=2));return
    c=load_config(args.config)
    if args.command=='doctor':result=doctor(c)
    elif args.command=='run':run_service(c);return
    elif args.command=='once':
        with InstanceLock(c['home']):
            initialize(c);result=Worker(c).cycle()
    elif args.command=='show-login':
        if not sys.stdin.isatty() or not sys.stdout.isatty():raise Refused('Login code only displayed in a private interactive terminal; never redirect to chat/logs')
        print(SecretStore(Path(c['home'])/'secrets').get('ui_login')['token']);return
    else:
        s=ServiceStore(Path(c['home'])/'operations')
        try:
            if args.command in ('status','watchdog'):
                result=s.overview([x['id'] for x in c['sources'] if x['enabled']],max_age=c['mail_poll_seconds']*2,heartbeat_max_age=c['worker_seconds']*3+30)
                if args.command=='watchdog':
                    # Only a status code/output. A separately configured observer must act on it.
                    print(json.dumps(result,indent=2));sys.exit(0 if result['worker']=='RUNNING_RECENTLY' else 2)
            elif args.command in ('pause-network','resume-network'):
                if args.command=='resume-network' and (not sys.stdin.isatty() or input('Type RESUME LOCAL NETWORK: ')!='RESUME LOCAL NETWORK'):raise Refused('Interactive operator resumption required')
                s.set('outbound_paused',args.command=='pause-network');result={'scope':'THIS_RUNTIME_ONLY','paused':s.get('outbound_paused'),'in_flight':'may finish','external_writes_enabled':False}
            elif args.command=='retention-plan':result=s.retention_plan(args.days)
            elif args.command=='retention-apply':
                if args.confirm!='DELETE REVIEWED METADATA':raise Refused('Explicit retention acknowledgment required')
                plan=strict_json(args.plan.read_text());result=s.apply_retention(plan)
        finally:s.close()
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    try:main()
    except (Refused,OSError,ValueError) as e:
        # Provider and secret exceptions never include credentials.
        print('Operation refused: '+str(e),file=sys.stderr);sys.exit(1)
