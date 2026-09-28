#!/usr/bin/env python3
"""Human-supervised narrow adapter. Never give a model the operator password/token.
Use a separate protected operator account to establish a meaningful boundary.
"""
import argparse, getpass, json, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jarvis.common import *
from jarvis.authority import Authority
from jarvis.calendar import Broker,GoogleCalendar,SimCalendar

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authority',required=True);p.add_argument('--provider',choices=['simulation','google'],default='simulation')
    p.add_argument('--simulation-state');p.add_argument('--allow-calendar',action='append',default=[])
    p.add_argument('--token-env',default='KINTSUGI_GOOGLE_ACCESS_TOKEN')
    p.add_argument('--google-account-sub',help='Expected Google OpenID subject from a separately verified OAuth sign-in')
    p.add_argument('action',choices=['initialize','pause','status','execute','reconcile']);p.add_argument('--proposal');p.add_argument('--operation-key');p.add_argument('--sharing')
    a=p.parse_args();auth=Authority(a.authority)
    try:
        if a.action=='initialize':
            pw=getpass.getpass('Create PRIVATE local operator password (14+ chars): ')
            if pw!=getpass.getpass('Repeat password: '):raise Refused('Passwords differ')
            auth.initialize(pw);print('Initialized PAUSED. No external call.');return
        if a.action=='pause':auth.pause();print('New dispatches paused. In-flight requests still need reconciliation.');return
        if a.action=='status':print(json.dumps(auth.report(),indent=2));return
        if a.provider=='simulation':
            if not a.simulation_state:raise Refused('Provide separate --simulation-state')
            if Path(a.simulation_state).resolve()==auth.root:raise Refused('Simulation and authority directories must differ')
            adapter=SimCalendar(a.simulation_state)
        else:
            if not a.allow_calendar:raise Refused('Explicit calendar allowlist required')
            if not a.google_account_sub:raise Refused('--google-account-sub required; current token subject is checked before HTTPS calls')
            adapter=GoogleCalendar(lambda:os.environ.get(a.token_env),a.allow_calendar,account_id=a.google_account_sub)
        broker=Broker(auth,adapter,live_enabled=a.provider=='google')
        if a.action=='reconcile':
            if not a.operation_key:raise Refused('--operation-key required')
            print(json.dumps(broker.reconcile(a.operation_key),indent=2));return
        if not a.proposal:raise Refused('--proposal required')
        proposal=strict_json(Path(a.proposal).read_text())
        context,audience=broker.prepare(proposal)
        print('EXACT ACTION — review target, audience, fields, time, and source independently:')
        print(json.dumps({'proposal':proposal,'context':context,'audience':audience},indent=2))
        sharing=strict_json(Path(a.sharing).read_text()) if a.sharing else None
        if sharing:print('SHARING GRANT:',json.dumps(sharing,indent=2))
        challenge='APPROVE '+digest(proposal)[:16]
        if input('Type '+challenge+' to approve this exact action: ').strip()!=challenge:raise Refused('Approval not given')
        pw=getpass.getpass('PRIVATE operator password: ')
        auth.resume(pw)
        token=auth.grant(proposal,context,pw,sharing=sharing)
        print(json.dumps(broker.execute(proposal,token),indent=2))
    finally:auth.close()
if __name__=='__main__':
    try:main()
    except (Refused,ValueError,KeyError,OSError) as e:print('STOPPED:',str(e),file=sys.stderr);sys.exit(2)
