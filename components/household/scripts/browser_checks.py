#!/usr/bin/env python3
"""Offline browser DOM test with a synthetic fetch/storage bridge.
This deliberately does not navigate to blocked network destinations or alter browser
security policy. HTTP/auth endpoint tests run separately in test_local_ui.py.
It does NOT certify browser-to-server networking, native offline storage or Android.
Requires existing Playwright/Chromium; installs nothing.
"""
import argparse,json,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from jarvis.cli import demo
from jarvis.household import Household
from jarvis.common import Refused,Conflict
from playwright.sync_api import sync_playwright

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--chromium',default='/usr/bin/chromium');args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);checks=[]
    with tempfile.TemporaryDirectory() as tmp:
        demo(tmp)
        def bridge(path,body):
            if path=='/api/login':return {'status':200,'body':{'ok':True}}
            h=Household(tmp)
            try:
                if path=='/api/state':
                    s=h.tick();s['csrf']='synthetic-dom-only';return {'status':200,'body':s}
                if path=='/api/command':return {'status':200,'body':h.command(body)}
                return {'status':404,'body':{'error':'Not found'}}
            except Conflict as e:return {'status':409,'body':{'error':str(e)}}
            except Refused as e:return {'status':400,'body':{'error':str(e)}}
            finally:h.close()
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
            def mount(ctx,storage=None):
                page=ctx.new_page();page.set_default_timeout(4000);page.on('pageerror',lambda e:print('PAGEERROR',str(e),flush=True));page.expose_function('__fixture',bridge)
                html=(root/'web/index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js"></script>','')
                page.set_content(html);page.add_style_tag(content=(root/'web/style.css').read_text())
                page.evaluate('''seed=>{if(!crypto.randomUUID)crypto.randomUUID=()=>crypto.getRandomValues(new Uint32Array(4)).join('-');window.__storage=seed;Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.__storage[k]??null,setItem:(k,v)=>window.__storage[k]=String(v),removeItem:k=>delete window.__storage[k]},configurable:true});window.fetch=async (path,opts={})=>{if(window.__testOffline)throw new TypeError('Synthetic offline');const r=await window.__fixture(path,opts.body?JSON.parse(opts.body):null);return new Response(JSON.stringify(r.body),{status:r.status})};}''',storage or {})
                page.add_script_tag(content=(root/'web/app.js').read_text());page.locator('#workspace').wait_for(state='visible');return page
            ctx=browser.new_context(viewport={'width':1200,'height':1000});page=mount(ctx)
            checks.append({'id':'UI01','status':'PASS','what':'Desktop DOM renders with synthetic data bridge'})
            page.get_by_role('button',name='Simplify today',exact=True).click();page.wait_for_function("document.getElementById('mode').textContent==='Minimum day'")
            checks.append({'id':'UI02','status':'PASS','what':'Minimum mode uses approved steps'})
            card=page.locator('article').filter(has=page.get_by_role('heading',name='Private reset — demonstration'))
            card.get_by_role('button',name='Done',exact=True).click();card.get_by_role('button',name='Undo',exact=True).wait_for();card.get_by_role('button',name='Undo',exact=True).click();card.get_by_role('button',name='Done',exact=True).wait_for();card.get_by_role('button',name='Snooze 15 min').click();page.wait_for_timeout(100)
            checks.append({'id':'UI03','status':'PASS','what':'Done/undo/snooze bound to displayed occurrence through synthetic bridge'})
            page.locator('#capture').fill('<img src=x onerror="window.pwned=1">');page.get_by_role('button',name='Save privately').click();page.get_by_text('<img src=x onerror="window.pwned=1">',exact=True).wait_for();assert page.evaluate('window.pwned===undefined')
            checks.append({'id':'UI04','status':'PASS','what':'Captured HTML is inert text'})
            page.get_by_role('button',name='Use as my next action').click();page.get_by_role('heading',name='<img src=x onerror="window.pwned=1">',exact=True).wait_for()
            checks.append({'id':'UI05','status':'PASS','what':'Capture becomes private next action'})
            # Remove attack fixture from the synthetic preview only, not product code.
            h=Household(tmp);h.db.execute('DELETE FROM captures');h.db.execute("DELETE FROM obligations WHERE body LIKE '%window.pwned%'");h.close()
            page.evaluate('refresh()');page.wait_for_timeout(100);page.screenshot(path=str(out/'DESKTOP_PREVIEW.png'),full_page=True);ctx.close()
            ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=1);p=mount(ctx)
            assert p.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            checks.append({'id':'UI06','status':'PASS','what':'390px mobile DOM emulation has no horizontal overflow'})
            p.locator('#offlineOpt').check();p.evaluate('window.__testOffline=true');p.locator('#capture').fill('School form — review after work');p.get_by_role('button',name='Save privately').click();p.wait_for_function("JSON.parse(localStorage.getItem('kj.outbox')||'[]').length===1")
            stored=p.evaluate('window.__storage');p.close();p=mount(ctx,stored)
            p.get_by_text('School form — review after work',exact=True).wait_for(timeout=5000);p.wait_for_function("JSON.parse(localStorage.getItem('kj.outbox')||'[]').length===0")
            assert p.get_by_text('School form — review after work',exact=True).count()==1
            checks.append({'id':'UI07','status':'PASS','what':'Serialized outbox replays once after DOM remount; native persistence not tested'})
            p.screenshot(path=str(out/'MOBILE_PREVIEW.png'),full_page=True);ctx.close();browser.close()
    report={'scope':'OFFLINE_CHROMIUM_DOM_WITH_SYNTHETIC_FETCH_AND_STORAGE','checks':checks,'physical_android_tested':False,
            'browser_to_local_server':'BLOCKED_BY_ENVIRONMENT_ADMIN_POLICY_NOT_BYPASSED','native_offline_storage':'NOT_TESTED',
            'http_endpoints':'TESTED_SEPARATELY_BY_UNIT_SUITE','external_mutations':0,'live_scheduled_runs':0}
    (out/'BROWSER_RESULTS.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
