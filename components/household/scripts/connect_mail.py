#!/usr/bin/env python3
"""Interactive, personal read-only OAuth. Requires a user's existing registered client ID.
No registrations, subscriptions, purchases, or global mail permissions are auto-created.
"""
import argparse,getpass,json,secrets,sys,time,urllib.parse,webbrowser
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jarvis.common import *
from jarvis.runtime import load_config,atomic_private,validate_config,InstanceLock
from jarvis.secret_store import SecretStore
from jarvis.onboarding import *

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--provider',choices=['gmail','outlook'],required=True)
    p.add_argument('--source-id',required=True);p.add_argument('--selector',required=True,help='Gmail label ID or Outlook folder ID/well-known name');a=p.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():raise Refused('Use an interactive private terminal, not a chat or redirected log')
    c=load_config(a.config);original_config=digest(c);vault=SecretStore(Path(c['home'])/'secrets')
    if any(s['id']==a.source_id for s in c['sources']):raise Refused('Source already exists; preserve its cursor and use a new source ID for a new binding')
    reference='mail_'+secrets.token_hex(12)
    print('Only consent for your personal account. Do not connect an employer clinical mailbox.')
    if input('Type PERSONAL READ ONLY: ')!='PERSONAL READ ONLY':raise Refused('Consent not given')
    client_id=input('Your registered public/native app client ID: ').strip()
    if a.provider=='gmail':
        client_secret=getpass.getpass('Native desktop client secret (blank if not issued): ').strip() or None
        result={};expected={}
        class Callback(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query)
                expected_host='127.0.0.1:'+str(self.server.server_port)
                if u.path!='/callback' or self.headers.get('Host')!=expected_host or not secrets.compare_digest(q.get('state',[''])[0],expected.get('state','')):
                    self.send_error(400);return
                if len(q.get('code',[]))!=1 or len(q['code'][0])>8192:self.send_error(400);return
                result['code']=q['code'][0]
                raw=b'Authorization received. Return to the private terminal.';self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        server=HTTPServer(('127.0.0.1',0),Callback);server.timeout=1
        redirect='http://127.0.0.1:'+str(server.server_port)+'/callback';auth=google_authorization(client_id,redirect);expected['state']=auth['state']
        print('Opening the official Google authorization page. If the browser does not open, retry in a supported interactive desktop environment.')
        if not webbrowser.open(auth['url']):server.server_close();raise Refused('Browser launch unavailable')
        until=time.monotonic()+300
        try:
            while 'code' not in result and time.monotonic()<until:server.handle_request()
        finally:server.server_close()
        if not result:raise Refused('Callback timed out')
        credential=google_exchange(client_id,client_secret,result['code'],redirect,auth['verifier'])
    else:
        device=microsoft_device_start(client_id)
        print('Open this official verification page locally: '+device['verification_uri']);print('Enter this temporary code on that page only: '+device['user_code'])
        credential=microsoft_device_finish(client_id,device)
    account=identify(credential)
    print('Verified personal account identifier: '+account)
    if input('Type SAVE THIS ACCOUNT: ')!='SAVE THIS ACCOUNT':raise Refused('Credential not saved')
    c['sources'].append({'id':a.source_id,'provider':a.provider,'account':account,'selector':a.selector,'credential_ref':reference,'enabled':False,'max_pages':20,'lookback_days':14})
    validate_config(c)
    with InstanceLock(c['home']):
        if digest(load_config(a.config))!=original_config:raise Refused('Config changed during authorization; review before saving')
        if vault.exists(reference):raise Refused('Credential already exists')
        vault.put(reference,credential);atomic_private(a.config,canonical(c)+'\n')
    print('Saved disabled source. Review its scope, set enabled=true locally, then restart the worker. No mail was modified.')
if __name__=='__main__':
    try:main()
    except Exception:print('Onboarding stopped. No provider error, token, or code is copied to logs. Review provider consent and local setup.',file=sys.stderr);sys.exit(1)
