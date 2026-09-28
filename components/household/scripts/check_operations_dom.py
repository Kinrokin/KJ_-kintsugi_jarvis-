#!/usr/bin/env python3
"""Offline UI logic exercised in Chromium, with explicitly synthetic transport/storage/lock.
Does not certify a physical device, native Web Locks, Push API, or server connectivity.
"""
import argparse,hashlib,json,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
from jarvis.common import *
from jarvis.runtime import initialize
from jarvis.cli import demo
from jarvis.household import Household
from jarvis.service_store import ServiceStore
from jarvis.operations_api import get,post
from jarvis.mail_ingest import poll_source
from test_runtime_operations import cfg,source,gmail_full,NOW
from playwright.sync_api import sync_playwright

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);checks=[]
    with tempfile.TemporaryDirectory() as d:
        c=cfg(d);initialize(c);demo(Path(c['home'])/'household');c['sources']=[source()]
        s=ServiceStore(Path(c['home'])/'operations');poll_source(s,source(),'fixture',gmail_full('<img src=x onerror=window.bad=1>'),NOW);s.close()
        def bridge(path,body):
            try:
                if path=='/api/state':
                    h=Household(Path(c['home'])/'household')
                    try:v=h.tick();v['csrf']='synthetic';return {'status':200,'body':v}
                    finally:h.close()
                if path=='/api/cues':return {'status':200,'body':{'cues':[]}}
                if path=='/api/command':
                    h=Household(Path(c['home'])/'household')
                    try:return {'status':200,'body':h.command(body)}
                    finally:h.close()
                if path=='/api/logout':return {'status':200,'body':{'ok':True}}
                return {'status':200,'body':get(c,path) if body is None else post(c,path,body)}
            except Exception as e:return {'status':400,'body':{'error':str(e)}}
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            def mount(deny=False):
                ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);p=ctx.new_page();p.set_default_timeout(4000)
                p.on('pageerror',lambda e:print('SYNTHETIC_PAGE_ERROR:',str(e)));p.expose_function('__bridge',bridge);p.expose_function('__sha',lambda raw:list(hashlib.sha256(bytes(raw)).digest()))
                html=(root/'web/index.html').read_text().replace('<script src="/app.js"></script>','').replace('<script src="/operations.js"></script>','')
                p.set_content(html);p.add_style_tag(content=(root/'web/style.css').read_text())
                p.evaluate('''deny=>{
                    if(!crypto.randomUUID)crypto.randomUUID=()=>crypto.getRandomValues(new Uint32Array(4)).join('-');
                    const storage={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>storage[k]||null,setItem:(k,v)=>storage[k]=v,removeItem:k=>delete storage[k]}});
                    Object.defineProperty(crypto,'subtle',{value:{digest:async(a,b)=>Uint8Array.from(await window.__sha(Array.from(b))).buffer}});
                    Object.defineProperty(navigator,'locks',{value:{request:async(n,o,fn)=>fn(deny?null:{name:n})},configurable:true});
                    window.fetch=async(path,opts={})=>{const r=await window.__bridge(path,opts.body?JSON.parse(opts.body):null);return new Response(JSON.stringify(r.body),{status:r.status});};
                }''',deny)
                p.add_script_tag(content=(root/'web/app.js').read_text());p.add_script_tag(content=(root/'web/operations.js').read_text())
                p.locator('#workspace').wait_for(state='visible');p.evaluate('opsRefresh()');return ctx,p
            ctx,p=mount();p.get_by_text('<img src=x onerror=window.bad=1>',exact=True).wait_for();assert p.evaluate('window.bad===undefined')
            checks.append({'id':'OPS-DOM-01','status':'PASS','what':'External metadata rendered as inert text, not instructions/HTML'})
            assert 'No email scopes enabled' not in p.locator('#opsStatus').inner_text();checks.append({'id':'OPS-DOM-02','status':'PASS','what':'Configured source and worker status visible without all-clear'})
            p.once('dialog',lambda d:d.accept('Review the source form in original mailbox'));p.get_by_role('button',name='Turn into a private candidate').click();p.get_by_role('heading',name='<img src=x onerror=window.bad=1>',exact=True).wait_for()
            h=Household(Path(c['home'])/'household');new=[o for o in h.snapshot()['obligations'] if o['title'].startswith('<img')];h.close();assert new[0]['status']=='CANDIDATE'
            checks.append({'id':'OPS-DOM-03','status':'PASS','what':'Reviewed email becomes private candidate, not automatically accepted'})
            p.locator('#reviewMinutes').fill('2');p.get_by_role('button',name='Record review time').click();p.get_by_text('Review time recorded as your report.').wait_for()
            h=Household(Path(c['home'])/'household');assert any(m['value']==120 for m in h.snapshot()['measurements']);h.close();checks.append({'id':'OPS-DOM-04','status':'PASS','what':'Review burden records user-entered seconds'})
            p.get_by_role('button',name='Pause runtime network').click();p.wait_for_function("document.getElementById('opsStatus').textContent.includes('Network operations paused')")
            checks.append({'id':'OPS-DOM-05','status':'PASS','what':'Network pause persists through operations API'})
            p.get_by_role('button',name='Enable private reminders').click();p.wait_for_function("document.getElementById('pushStatus').textContent.includes('trusted HTTPS')")
            checks.append({'id':'OPS-DOM-06','status':'PASS','what':'Insecure synthetic page cannot subscribe to push'})
            assert p.evaluate('document.documentElement.scrollWidth<=window.innerWidth');checks.append({'id':'OPS-DOM-07','status':'PASS','what':'Operations view fits a 390px emulated viewport'})
            # Remove hostile synthetic fixture only from preview data.
            h=Household(Path(c['home'])/'household');h.db.execute("DELETE FROM obligations WHERE body LIKE '%window.bad%'");h.close();p.evaluate('refresh()');p.evaluate('opsRefresh()')
            p.screenshot(path=str(a.out/'OPERATIONS_MOBILE_PREVIEW.png'),full_page=True);ctx.close()
            ctx,p=mount(True);p.locator('#capture').fill('Do not lose this thought');p.get_by_role('button',name='Save privately').click()
            assert p.locator('#capture').input_value()=='Do not lose this thought';assert 'read-only' in p.locator('#editStatus').inner_text().lower()
            checks.append({'id':'OPS-DOM-08','status':'PASS','what':'Denied synthetic editing lock leaves capture text intact and does not queue it'})
            ctx.close();browser.close()
    report={'scope':'OFFLINE_CHROMIUM_DOM_SYNTHETIC_TRANSPORT_STORAGE_AND_LOCK','checks':checks,'count':len(checks),'physical_phone':False,'native_locks':False,'native_push':False,'real_accounts':0}
    (a.out/'OPERATIONS_DOM_RESULTS.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
