#!/usr/bin/env python3
"""Actual local TLS/HTTP checks, with temporary test certificate and fixture state.
Requires an already installed openssl command. Installs nothing and never binds LAN.
Certificate validation is ENABLED; only the temporary local fixture is trusted.
Not an Android, production TLS, remote network, or push-notification test.
"""
import argparse,http.cookiejar,json,shutil,ssl,subprocess,sys,tempfile,threading,urllib.request,urllib.error,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from jarvis.web import LocalUI
from jarvis.common import iso,now_utc

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    if not shutil.which('openssl'):raise SystemExit('NOT_RUN: openssl is not installed; no installation attempted')
    checks=[]
    with tempfile.TemporaryDirectory() as d:
        d=Path(d);key=d/'key.pem';cert=d/'cert.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        key.chmod(0o600)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(cert,key)
        server=LocalUI(d/'household',0,'fixture-only-login-code',tls_context=tls)
        th=threading.Thread(target=server.serve_forever,daemon=True);th.start();url='https://127.0.0.1:'+str(server.server_port)
        context=ssl.create_default_context(cafile=str(cert))
        opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def call(path,body=None,headers=None):
            h={'Origin':url};h.update(headers or {})
            if body is not None:h['Content-Type']='application/json'
            req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers=h)
            try:r=opener.open(req,timeout=5)
            except urllib.error.HTTPError as e:r=e
            return r.status,r.read(),dict(r.headers)
        def check(name,passed):
            if not passed:raise AssertionError(name)
            checks.append({'check':name,'status':'PASS'})
        try:
            check('TLS chain and hostname verified',call('/')[0]==200 and context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED)
            check('No private state without session',call('/api/state')[0]==401)
            status,_,headers=call('/api/login',{'token':'fixture-only-login-code'})
            check('HTTPS session cookie is Secure and HttpOnly',status==200 and 'Secure' in headers['Set-Cookie'] and 'HttpOnly' in headers['Set-Cookie'])
            status,raw,headers=call('/api/state');state=json.loads(raw);csrf={'X-CSRF-Token':state['csrf']}
            check('Authenticated local state readable without cache',status==200 and headers['Cache-Control']=='no-store')
            event={'version':1,'occurred_at':iso(now_utc()),'household_instance':state['instance_id'],'source':'user_report'}
            check('Legitimate bound command succeeds',call('/api/command',{'command_id':'test-mode','op':'simplify','client_event':event},csrf)[0]==200)
            check('Forged Origin refused',call('/api/cues',{},dict(csrf,Origin='https://external.invalid'))[0]==403)
            check('Unknown Host refused',call('/',headers={'Host':'evil.invalid'})[0]==403)
            check('Old offline command is review-only',call('/api/command',{'command_id':'old','op':'done','object_id':'x','expected_revision':0},csrf)[0]==409)
            check('No approval endpoint exposed',call('/api/approve',{'approved_by':'anyone'},csrf)[0]==404)
            check('Logout invalidates session',call('/api/logout',{},csrf)[0]==200 and call('/api/state')[0]==401)
        finally:server.shutdown();server.server_close();th.join()
    report={'scope':'ACTUAL_LOOPBACK_HTTPS_WITH_TEMPORARY_TEST_CERTIFICATE','checks':checks,'count':len(checks),'certificate_validation':'ENABLED_WITH_TEMPORARY_TEST_CA','certificate_and_key_retained':False,'physical_phone_tested':False,'LAN_route_tested':False,'production_external_effects':0}
    Path(args.out).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
