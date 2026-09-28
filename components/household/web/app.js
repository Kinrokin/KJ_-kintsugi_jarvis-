'use strict';
const $ = id => document.getElementById(id);
const CONSENT = 'kj.offlineConsent.v311', SNAPSHOT = 'kj.routineView.v311', OUTBOX = 'kj.outbox';
let state = null, csrf = '', busy = false, online = false, persist = false, queue = [], storedQueue = false;
let editingAvailable=!navigator.locks;
if(navigator.locks){
  navigator.locks.request('kintsugi-private-outbox-editor',{ifAvailable:true},async lock=>{
    if(!lock){$('editStatus').textContent='Another tab owns the private outbox. This tab is read-only. Close the other tab and reload here to edit.';return;}
    try{const latest=localStorage.getItem(OUTBOX);storedQueue=!!latest;persist=localStorage.getItem(CONSENT)==='yes';queue=latest?JSON.parse(latest):[];if(!Array.isArray(queue))throw new Error();}
    catch(e){$('editStatus').textContent='Stored outbox needs review before editing.';return;}
    editingAvailable=true;$('editStatus').textContent='This tab owns the private outbox.';render();flush();
    await new Promise(()=>{}); // Browser releases the lock when this document is destroyed.
  }).catch(()=>{$('editStatus').textContent='Cannot establish an editing lock. Reopen a single trusted tab.';});
}else $('editStatus').textContent='This browser lacks an editing lock. Use only one editing tab; cross-tab safety is not established.';
try {
  persist = localStorage.getItem(CONSENT) === 'yes';
  const saved = localStorage.getItem(OUTBOX); storedQueue = !!saved;
  if (saved) {const parsed = JSON.parse(saved); if (!Array.isArray(parsed)) throw new Error('Outbox is not an array'); queue = parsed;}
  if (persist) {const savedView=localStorage.getItem(SNAPSHOT); if (savedView) state=JSON.parse(savedView);}
} catch (e) { $('error').textContent='Browser storage needs review. Existing data was not deliberately erased. Keep this tab open.'; }
$('offlineOpt').checked = persist;
function saveQueue() {
  if(!editingAvailable)return;
  try {
    if (persist || storedQueue) {
      if (queue.length) {localStorage.setItem(OUTBOX, JSON.stringify(queue)); storedQueue = true;}
      else {localStorage.removeItem(OUTBOX); storedQueue = false;}
    }
  } catch (e) { $('error').textContent='Device storage could not save the outbox. Keep this tab open until synchronization succeeds.'; }
  $('queueStatus').textContent=queue.length ? `${queue.length} change(s) awaiting server acknowledgment.` : 'No queued changes.';
}
function saveView() {
  if (!editingAvailable || !persist || !state || !online) return;
  // Cache only the routine view, not tokens, provider receipts, emails or obligations.
  const view={occurrences:state.occurrences,upcoming:state.upcoming,mode:state.mode,mode_date:state.mode_date,
    household_timezone:state.household_timezone,instance_id:state.instance_id,now:state.now,
    runtime_version:state.runtime_version,client_protocol:state.client_protocol,
    obligations:[],open_obligations:[],captures:[],actions:[],measurements:[],cached_view:true};
  try {localStorage.setItem(SNAPSHOT,JSON.stringify(view));} catch(e) {$('error').textContent='Offline routine view could not be saved.';}
}
$('offlineOpt').onchange=()=>{
  if(!editingAvailable){$('offlineOpt').checked=persist;return;}
  if (!$('offlineOpt').checked && queue.length && !confirm('Turn off device storage? Pending changes stay only in this open tab and may be lost if it closes.')) {$('offlineOpt').checked=true;return;}
  persist=$('offlineOpt').checked;
  try {
    localStorage.setItem(CONSENT,persist?'yes':'no');
    if (!persist) {localStorage.removeItem(SNAPSHOT);localStorage.removeItem(OUTBOX);storedQueue=false;}
  } catch(e) {$('error').textContent='Device storage is unavailable.';}
  saveQueue();saveView();
};
function node(tag,text,cls) {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function button(text,fn,cls) {const b=node('button',text,cls);b.onclick=fn;return b;}
function localDay(t,tz) {return new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:tz}).format(new Date(t));}
function when(t,tz=state?.household_timezone||'America/Chicago') {return new Date(t).toLocaleString(undefined,{weekday:'short',hour:'numeric',minute:'2-digit',timeZone:tz});}
function queuedMode(day,tz) {
  const changes=queue.filter(c=>['simplify','normal'].includes(c.op)&&c.client_event&&localDay(c.client_event.occurred_at,tz)===day);
  return changes.length ? (changes[changes.length-1].op==='simplify'?'minimum':'normal') : null;
}
function variant(r) {
  if(r.status==='DONE')return r.completion_version;
  const queued=queuedMode(localDay(r.due,r.timezone),r.timezone);
  return (queued ? (queued==='minimum'?'minimum':'full') : null) || r.display_variant || (state.mode==='minimum'&&localDay(r.due,r.timezone)===state.mode_date?'minimum':'full');
}
function command(op,args={}) {
  if(!editingAvailable){$('error').textContent='Read-only tab: use the tab that owns the outbox.';return;}
  if(!state?.instance_id) {$('error').textContent='Open this household online once before recording offline changes.';return;}
  const event={version:1,occurred_at:new Date().toISOString(),household_instance:state.instance_id,source:'user_report'};
  const r=state.occurrences.find(x=>x.id===args.object_id);
  if(r) {
    event.definition_version=r.definition_version;event.timezone=r.timezone;event.observed_user_revision=r.user_revision||0;
    if(op==='done')event.completion_variant=variant(r); // Same choice as the rendered steps, captured NOW.
  }
  queue.push({command_id:crypto.randomUUID(),op,...args,client_event:event});
  saveQueue();render();flush();return true;
}
async function request(path,body) {
  const r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},
    body:body?JSON.stringify(body):undefined,cache:'no-store'});
  const d=await r.json();if(!r.ok){const e=new Error(d.error||'Request refused');e.status=r.status;throw e;}return d;
}
async function cues() {
  if(!editingAvailable||!online||!csrf||document.visibilityState!=='visible')return;
  try {
    const result=await request('/api/cues',{});
    if(result.cues?.length) {$('cue').textContent='A private routine is ready. Check Routines below. This is a foreground cue, not a completed task.';$('cue').hidden=false;}
  } catch(e) {/* Source health stays visible in the ordinary connection status. No false push receipt. */}
}
async function refresh() {
  try {
    state=await request('/api/state');csrf=state.csrf;online=true;
    $('login').hidden=true;$('workspace').hidden=false;$('connection').textContent='';render();saveView();
    if(!queue.length)await cues();
  } catch(e) {
    online=false;
    if(e.status===401){$('login').hidden=false;$('workspace').hidden=true;}
    else if(state) {
      $('workspace').hidden=false;$('login').hidden=true;
      $('connection').textContent='Offline. Showing a previous routine view; other obligations are not certified current. New changes are not yet synchronized.';render();
    }
    throw e;
  }
}
async function flush() {
  if(busy||!editingAvailable)return;busy=true;
  try {
    if(!state||!online)await refresh();
    while(queue.length) {
      const c=queue[0];
      // A V3.1 queue lacks time and variant. Never invent them from reconnection.
      if(!c.client_event) {$('error').textContent='Legacy queued change has no original time/context. Export and review it before discarding; it will not be replayed automatically.';$('discard').hidden=false;return;}
      try {await request('/api/command',c);queue.shift();$('discard').hidden=true;saveQueue();}
      catch(e) {
        if(e.status) {$('error').textContent='Change needs review: '+e.message;$('discard').hidden=false;}
        else {online=false;$('connection').textContent='Offline: queued changes have NOT yet been saved to household state.';}
        return;
      }
    }
    await refresh();$('error').textContent='';
  } catch(e) {$('error').textContent=e.status?'Sign in again to synchronize.':'Server unavailable. Changes remain queued.';}
  finally {busy=false;}
}
$('discard').onclick=()=>{if(!editingAvailable)return;if(confirm('Discard only the first blocked change? Export it first if you need its original report.')){queue.shift();saveQueue();$('discard').hidden=true;flush();}};
$('exportQueue').onclick=()=>{
  const blob=new Blob([JSON.stringify({version:'3.2.0',private_outbox:queue},null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Kintsugi-private-outbox.json';a.click();URL.revokeObjectURL(url);
};
$('forgetOffline').onclick=()=>{
  if(!editingAvailable)return;
  if(queue.length&&!confirm('Erase this browser’s unsynchronized changes too? This cannot mark them completed.'))return;
  try {localStorage.removeItem(SNAPSHOT);localStorage.removeItem(OUTBOX);localStorage.removeItem(CONSENT);}catch(e){}
  persist=false;queue=[];storedQueue=false;$('offlineOpt').checked=false;saveQueue();$('error').textContent='Offline routine copy and outbox erased from this browser. Server records were not deleted.';
};
$('loginForm').onsubmit=async e=>{e.preventDefault();try{await request('/api/login',{token:$('token').value});$('token').value='';await refresh();flush();}catch(err){$('error').textContent=err.message;}};
$('captureForm').onsubmit=e=>{e.preventDefault();const text=$('capture').value.trim();if(text&&command('capture',{text})){$('capture').value='';}};
$('simplify').onclick=()=>command('simplify',{timezone:state?.household_timezone||'America/Chicago'});
$('normal').onclick=()=>command('normal',{timezone:state?.household_timezone||'America/Chicago'});
function render() {
  if(!state)return;
  const tz=state.household_timezone||'America/Chicago',day=localDay(new Date().toISOString(),tz);
  const effectiveMode=queuedMode(day,tz)||(state.mode_date===day?state.mode:'normal');
  $('mode').textContent=effectiveMode==='minimum'?'Minimum day':'Normal day';
  const routines=$('routines');routines.replaceChildren();
  const rows=state.occurrences.filter(x=>x.status!=='SUPERSEDED').sort((a,b)=>a.due.localeCompare(b.due)).slice(-12);
  $('routineCount').textContent=`${state.upcoming.length} open`;
  if(!rows.length)routines.append(node('p','No routines configured. Set your private windows during the local trial.'));
  for(const r of rows) {
    const c=node('article',undefined,'card'+(r.status==='DONE'?' completed':''));c.dataset.id=r.id;
    c.append(node('div',r.status,'state'),node('h3',r.title),node('p',when(r.due,r.timezone),'small'));
    const list=node('ul',undefined,'steps');for(const step of(variant(r)==='minimum'?r.minimum_steps:r.full_steps))list.append(node('li',step));c.append(list);
    if(r.status==='OPEN')c.append(node('p','Reminder after '+when(r.next_nudge,r.timezone),'small'));
    const bs=node('div',undefined,'buttons'),args={object_id:r.id,expected_revision:r.revision};
    const pending=queue.find(x=>x.object_id===r.id);
    if(pending)c.append(node('p',`Queued ${pending.op} — not server-confirmed. Original tap time and displayed steps are retained.`,'small'));
    else if(r.status==='DONE') {c.append(node('p',`Done · ${r.basis} · ${r.completion_version}`,'small'));bs.append(button('Undo',()=>command('undo',args),'secondary'));}
    else if(['OPEN','UNKNOWN'].includes(r.status)) {
      bs.append(button('Done',()=>command('done',args)));
      if(r.status==='OPEN')bs.append(button('Snooze 15 min',()=>command('snooze',{...args,minutes:15}),'secondary'));
      bs.append(button('Skip this one',()=>command('skip',args),'secondary'));
    }
    c.append(bs);routines.append(c);
  }
  const os=$('obligations');os.replaceChildren();
  for(const o of state.obligations) {
    const c=node('article',undefined,'card');c.append(node('div',o.status,'state'),node('h3',o.title),node('p',o.outcome),node('p','Deadline: '+(o.deadline?when(o.deadline):'not established'),'small'));
    const a={object_id:o.id,expected_revision:o.revision};
    c.append(node('p',`Owner: ${o.owner||'unassigned'} · ${o.owner_accepted?'accepted/reported':'not yet accepted'}`,'small'));
    if(o.status==='OPEN')c.append(button('Propose another owner',()=>{const owner=prompt('Who might take responsibility? This does not contact them or imply acceptance.');if(owner)command('delegate',{...a,owner});},'secondary'));
    if(o.status==='AWAITING_ACCEPTANCE')c.append(button('Record their reported acceptance',()=>{const note=prompt('How did they accept responsibility? This is your report, not authenticated agreement.');if(note)command('confirm_acceptance',{...a,acceptance_note:note});},'secondary'));
    if(o.needs_review) {
      c.append(node('p','Conflicting source versions. Review the original source before selecting.','small'));
      [o.candidate_claim,...(o.contradictions||[])].forEach((claim,i)=>{
        const block=node('div');block.append(node('p',`${i+1}: ${claim.title} — ${claim.outcome} — ${claim.deadline||'no deadline'}`,'small'));
        block.append(button('Use reviewed version '+(i+1),()=>{const note=prompt('What establishes this version as the correct one?');if(note)command('resolve_source',{...a,claim_index:i,resolution_note:note});},'secondary'));c.append(block);
      });
    }
    if(o.status==='DONE')c.append(button('Undo completion',()=>command('reopen_obligation',a),'secondary'));
    if(o.status==='CANDIDATE'&&!o.needs_review)c.append(button('Accept this obligation',()=>command('accept',{...a,criteria:[o.outcome]})));
    if(o.status==='OPEN') {
      for(const [k,v]of Object.entries(o.conditions)) {const lab=node('label',undefined,'small'),check=document.createElement('input');check.type='checkbox';check.checked=v;check.onchange=()=>command('condition',{...a,condition:k,value:check.checked});lab.append(check,document.createTextNode(' I confirm: '+k));c.append(lab);}
      c.append(button('Mark obligation complete',()=>command('complete_obligation',a)));
    }
    os.append(c);
  }
  if(!state.obligations.length)os.append(node('p',state.cached_view?'Offline routine-only copy. Other obligations are not available here.':'No obligations recorded. A missing record is not proof that nothing is due.'));
  const cs=$('captures');cs.replaceChildren();
  for(const x of state.captures.slice().reverse().slice(0,20)) {
    const c=node('article',undefined,'card');c.append(node('div','PRIVATE CAPTURE','state'),node('p',x.text));
    if(x.status==='INBOX')c.append(button('Use as my next action',()=>command('make_task',{object_id:x.id}),'secondary'));else c.append(node('p','Moved to obligations','small'));cs.append(c);
  }
  if(!state.captures.length)cs.append(node('p','A thought you capture will appear here after synchronization.'));
  $('statusText').textContent=`Times: ${tz}. Last state read ${when(state.now)}. ${state.open_obligations.length} recorded obligation(s) still open. Coverage and optional push status appear in Operations. Local foreground cues are not proof of phone delivery.`;
  saveQueue();
}
window.addEventListener('online',()=>flush());
window.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')flush();});
if(state){$('workspace').hidden=false;$('login').hidden=true;$('connection').textContent='Cached routine view: connecting…';render();}
refresh().then(flush).catch(()=>{});
setInterval(()=>{if(!busy&&state&&document.visibilityState==='visible')refresh().catch(()=>{});},15000);
// Offline shell; optional push shows generic reminders only. It cannot approve or complete tasks.
if('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('/sw.js').then(()=>{$('offlineStatus').textContent='Offline shell registered. Opt in above to retain a routine view and queued changes; background reminders require separate opt-in and verified transport.';}).catch(()=>{$('offlineStatus').textContent='Offline shell unavailable. Keep this tab open during a disconnection.';});
} else $('offlineStatus').textContent='Offline reload needs trusted HTTPS (or localhost). No insecure-origin bypass is provided.';
