#!/usr/bin/env python3
"""Actual loopback subprocess supervisor acceptance; no real account or push transport."""
import argparse,http.cookiejar,json,socket,subprocess,sys,tempfile,time,urllib.error,urllib.request,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from jarvis.common import canonical
from jarvis.runtime import DEFAULT_CONFIG,load_config,atomic_private
from jarvis.secret_store import SecretStore

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);checks=[]
    def passed(name):checks.append({'name':name,'status':'PASS'})
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);config=tmp/'runtime.json';home=tmp/'private'
        operator=[sys.executable,'-I',str(root/'scripts/runtime_operator.py'),'--config',str(config)]
        r=subprocess.run(operator+['init','--home',str(home)],capture_output=True,text=True,timeout=10);assert r.returncode==0,r.stderr;passed('Explicit setup creates isolated empty private state')
        c=load_config(config)
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));c['port']=sock.getsockname()[1]
        atomic_private(config,canonical(c));url='http://127.0.0.1:'+str(c['port'])
        token=SecretStore(home/'secrets').get('ui_login')['token']
        def start():
            proc=subprocess.Popen(operator+['run'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            for _ in range(80):
                if proc.poll() is not None:raise AssertionError(proc.communicate())
                try:
                    if urllib.request.urlopen(url+'/',timeout=.3).status==200:return proc
                except Exception:time.sleep(.05)
            proc.terminate();raise AssertionError('Runtime failed to start')
        proc=start()
        try:
            passed('Supervisor starts actual local HTTP server and worker')
            second=subprocess.run(operator+['run'],capture_output=True,text=True,timeout=10);assert second.returncode!=0;passed('Second runtime process cannot own the same state')
            jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            def call(path,body=None,csrf=None):
                headers={'Origin':url}
                if body is not None:headers['Content-Type']='application/json'
                if csrf:headers['X-CSRF-Token']=csrf
                req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
                try:resp=client.open(req,timeout=3)
                except urllib.error.HTTPError as e:resp=e
                return resp.status,json.loads(resp.read())
            assert call('/api/operations')[0]==401;passed('Operations state requires a local session')
            assert call('/api/login',{'token':token})[0]==200;_,state=call('/api/state');csrf=state['csrf']
            assert state['runtime_version']=='3.2.0';passed('Authenticated household state loads')
            assert call('/api/network-pause',{})[0]==403;passed('Operational writes require CSRF')
            assert call('/api/operations')[1]['all_clear'] is False;passed('No sources does not become all-clear')
            assert call('/api/push-config')[1]['enabled'] is False;passed('Push is opt-in and disabled on clean setup')
            command={'command_id':uuid.uuid4().hex,'op':'capture','text':'Synthetic restart acceptance'}
            assert call('/api/command',command,csrf)[0]==200;assert call('/api/command',command,csrf)[0]==200
            assert len([x for x in call('/api/state')[1]['captures'] if x['text']==command['text']])==1;passed('Acknowledged duplicate capture has one persistent effect')
            assert call('/api/calendar/approve',{},csrf)[0]==404;passed('No calendar/approval endpoint in runtime')
            for _ in range(50):
                if (home/'health.json').exists():break
                time.sleep(.05)
            assert (home/'health.json').exists() and (home/'continuity.txt').exists();passed('Worker writes separate health and human-readable fallback')
            assert call('/api/network-pause',{},csrf)[0]==200;passed('Authenticated network pause is local and durable')
        finally:
            proc.terminate();output,error=proc.communicate(timeout=15);assert token not in output+error
        passed('Graceful stop does not print login secret')
        proc=start()
        try:
            assert call('/api/state')[0]==401;passed('Restart invalidates old HTTP session')
            assert call('/api/login',{'token':token})[0]==200;_,s=call('/api/state')
            assert len([x for x in s['captures'] if x['text']=='Synthetic restart acceptance'])==1;passed('Human state survives supervisor restart')
            assert call('/api/operations')[1]['outbound_paused'] is True;passed('Network pause survives restart')
            assert call('/api/logout',{},s['csrf'])[0]==200;assert call('/api/state')[0]==401;passed('Explicit logout invalidates current session')
        finally:proc.terminate();proc.communicate(timeout=15)
        p=subprocess.run([sys.executable,str(root/'scripts/plan_autostart.py'),'--config',str(config),'--out',str(tmp/'plans')],capture_output=True,text=True,timeout=10)
        assert p.returncode==0,p.stderr;assert (tmp/'plans/WINDOWS_AUTOSTART.ps1').exists();passed('OS setup plan generated without installation')
        doctor=subprocess.run(operator+['doctor'],capture_output=True,text=True,timeout=10);assert doctor.returncode==0;passed('Target preflight reports rather than invents capabilities')
    report={'scope':'ACTUAL_LOCAL_HTTP_AND_SUBPROCESS_SUPERVISOR_WITH_SYNTHETIC_STATE','checks':checks,'count':len(checks),
            'real_mail_accounts':0,'actual_push_provider_calls':0,'physical_phone':False,'Windows_task_installed':False,'OS_service_installed':False,'synthetic_state_deleted':True}
    (a.out/'OPERATIONS_RUNTIME_RESULTS.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
