#!/usr/bin/env python3
"""Chromium DOM + synthetic clock/fetch/storage checks for the repaired outbox.
Does not access the local server, bypass browser policy, certify native storage,
service-worker delivery, an Android device, a LAN route or background push.
"""
import argparse,json,sys,tempfile
from pathlib import Path
from datetime import timedelta
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from jarvis.common import *
from jarvis.household import Household
from playwright.sync_api import sync_playwright
NOW=instant('2026-09-24T13:00:00Z')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--chromium',default='/usr/bin/chromium');a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    checks=[];clock={'now':NOW};applied=[]
    with tempfile.TemporaryDirectory() as temp:
        h=Household(temp)
        routine={'id':'disconnect','version':1,'title':'Disconnect trial','anchor':'completion','timezone':'America/Chicago','first_due':iso(NOW),'interval':24,'interval_semantics':'elapsed_hours','window_minutes':120,'full_steps':['Brush teeth','Prepare clothes'],'minimum_steps':['Brush teeth'],'max_nudges':0,'quiet_start':'23:00','quiet_end':'06:00','kind':'ordinary'}
        h.configure_routine(routine,NOW);row=h.tick(NOW)['occurrences'][0];h.command({'command_id':'minimum','op':'simplify'},NOW);h.close()
        def bridge(path,body):
            h=Household(temp)
            try:
                if path=='/api/login':return {'status':200,'body':{'ok':True}}
                if path=='/api/state':
                    s=h.tick(clock['now']);s['csrf']='synthetic-context-only';return {'status':200,'body':s}
                if path=='/api/cues':return {'status':200,'body':{'cues':[]}}
                if path=='/api/command':
                    result=h.command(body,clock['now']);applied.append(body);return {'status':200,'body':result}
                return {'status':404,'body':{'error':'Not found'}}
            except Conflict as e:return {'status':409,'body':{'error':str(e)}}
            except (Refused,ValueError,KeyError) as e:return {'status':400,'body':{'error':str(e)}}
            finally:h.close()
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=a.chromium,headless=True,args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            def mount(seed=None):
                page=ctx.new_page();page.set_default_timeout(5000);page.expose_function('__fixture',bridge)
                html=(root/'web/index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js"></script>','')
                page.set_content(html);page.add_style_tag(content=(root/'web/style.css').read_text())
                page.evaluate('''arg=>{
                    window.__clockMs=arg.ms;const RealDate=Date;
                    window.Date=class extends RealDate {constructor(...args){super(...(args.length?args:[window.__clockMs]));}static now(){return window.__clockMs;}};
                    if(!crypto.randomUUID)crypto.randomUUID=()=>crypto.getRandomValues(new Uint32Array(4)).join('-');
                    window.__storage=arg.seed;Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.__storage[k]??null,setItem:(k,v)=>window.__storage[k]=String(v),removeItem:k=>delete window.__storage[k]},configurable:true});
                    window.fetch=async(path,opts={})=>{if(window.__offline)throw new TypeError('Synthetic outage');const r=await __fixture(path,opts.body?JSON.parse(opts.body):null);return new Response(JSON.stringify(r.body),{status:r.status});};
                }''',{'seed':seed or {},'ms':clock['now'].timestamp()*1000})
                page.add_script_tag(content=(root/'web/app.js').read_text());page.locator('#workspace').wait_for(state='visible');return page
            page=mount();page.locator('#offlineOpt').check();page.wait_for_timeout(100);page.evaluate('window.__offline=true')
            card=page.locator(f'article[data-id="{row["id"]}"]');card.get_by_role('button',name='Done',exact=True).click()
            page.wait_for_function("JSON.parse(localStorage.getItem('kj.outbox')||'[]').length===1")
            pending=page.evaluate("JSON.parse(localStorage.getItem('kj.outbox'))[0]")
            assert instant(pending['client_event']['occurred_at'])==NOW and pending['client_event']['completion_variant']=='minimum'
            assert pending['object_id']==row['id'] and pending['client_event']['definition_version']==1
            checks.append({'id':'DOM-F03-01','status':'PASS','what':'Done captures original tap time, occurrence, definition, user revision and displayed minimum steps before disconnect'})
            stored=page.evaluate('window.__storage');cached=json.loads(stored['kj.routineView.v311'])
            assert 'csrf' not in cached and cached['obligations']==[] and cached['captures']==[] and cached['actions']==[]
            checks.append({'id':'DOM-PRIVACY-02','status':'PASS','what':'Opt-in cached view contains routines, not CSRF token, email obligations, captures or provider receipts'})
            page.close();clock['now']=NOW+timedelta(days=1);page=mount(stored)
            page.wait_for_function("JSON.parse(localStorage.getItem('kj.outbox')||'[]').length===0")
            h=Household(temp);done=h._get('occurrences',row['id']);snapshot=h.tick(clock['now']);child=next(x for x in snapshot['occurrences'] if x['id']!=row['id']);h.close()
            assert instant(done['completed_at'])==NOW and done['completion_version']=='minimum' and instant(child['due'])==NOW+timedelta(days=1)
            assert snapshot['mode']=='normal'
            checks.append({'id':'DOM-F03-03','status':'PASS','what':'Next-day reconnection preserves yesterday minimum report and completion-based successor date; today remains normal'})
            page.get_by_role('button',name='Simplify today',exact=True).click();page.wait_for_function("document.getElementById('mode').textContent==='Minimum day'")
            page.wait_for_function("!busy && queue.length===0")
            page.get_by_role('button',name='Normal mode',exact=True).click();page.wait_for_function("document.getElementById('mode').textContent==='Normal day'")
            page.wait_for_function("!busy && queue.length===0")
            page.locator(f'article[data-id="{child["id"]}"]').get_by_role('button',name='Done',exact=True).click();page.wait_for_function("!busy && queue.length===0")
            h=Household(temp);assert h._get('occurrences',child['id'])['completion_version']=='full';h.close()
            checks.append({'id':'DOM-F03-04','status':'PASS','what':'Normal mode generates valid full completion, not a normal/variant mismatch'})
            page.screenshot(path=str(out/'FOCUSED_MOBILE_DOM_PREVIEW.png'),full_page=True);page.close()
            before=len(applied);legacy={'kj.outbox':json.dumps([{'command_id':'legacy','op':'done','object_id':row['id'],'expected_revision':0}])}
            page=mount(legacy);page.wait_for_function("document.getElementById('error').textContent.includes('Legacy queued')")
            assert len(applied)==before and page.evaluate("JSON.parse(localStorage.getItem('kj.outbox')).length") == 1
            checks.append({'id':'DOM-MIGRATION-05','status':'PASS','what':'Legacy unversioned outbox is retained for review, never replayed with invented time'})
            page.close()
            bad=json.loads(json.dumps(pending));bad['command_id']='foreign-household';bad['client_event']['household_instance']='foreign'
            page=mount({'kj.outbox':json.dumps([bad])});page.wait_for_function("document.getElementById('error').textContent.includes('another household instance')")
            assert page.evaluate("JSON.parse(localStorage.getItem('kj.outbox')).length") == 1
            checks.append({'id':'DOM-BINDING-06','status':'PASS','what':'Wrong-household queue remains blocked and exportable, not erased'})
            ctx.close();browser.close()
    report={'scope':'OFFLINE_CHROMIUM_DOM_SYNTHETIC_CLOCK_FETCH_STORAGE','checks':checks,'count':len(checks),'physical_phone_tested':False,'native_storage_tested':False,'service_worker_runtime_tested':False,'production_external_effects':0}
    (out/'OFFLINE_CONTEXT_DOM_RESULTS.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
