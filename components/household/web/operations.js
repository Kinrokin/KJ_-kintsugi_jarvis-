'use strict';
// Optional service features. This file has no authority, calendar or payment API.
const opsStatus=document.getElementById('opsStatus');
let opsBusy=false;
async function opsRefresh(){
  if(!online||!csrf||opsBusy)return;opsBusy=true;
  try{
    const r=await request('/api/operations');
    const sourceText=r.sources.map(s=>`${s.id}: ${s.status} (${s.covered?'within selected scope':'coverage incomplete'})`).join('; ');
    opsStatus.textContent=`Worker: ${r.worker}. ${sourceText||'No email scopes enabled.'} Push: ${r.push_health}. ${r.outbound_paused?'Network operations paused.':''} Physical phone delivery is not certified by this screen.`;
    const inbox=await request('/api/inbox'),dest=document.getElementById('mailCandidates');dest.replaceChildren();
    if(inbox.remaining_candidates>inbox.items.length)dest.append(node('p',`Showing ${inbox.items.length} of ${inbox.remaining_candidates} review candidates. Review or dismiss this group to see the next items.`,'small'));
    for(const row of inbox.items){
      const m=row.metadata,c=node('article',undefined,'card');
      c.append(node('div','UNTRUSTED EMAIL METADATA','state'),node('h3',m.subject),node('p',m.sender,'small'));
      const bodyHash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(stableJSON(m)));
      const hash=Array.from(new Uint8Array(bodyHash)).map(b=>b.toString(16).padStart(2,'0')).join('');
      c.append(button('Turn into a private candidate',async()=>{
        const outcome=prompt('What outcome actually needs to happen? Verify the original email; metadata alone does not establish a deadline.');
        if(!outcome)return;
        try{await request('/api/mail-review',{id:row.id,metadata_hash:hash,outcome,deadline:null});await refresh();await opsRefresh();}
        catch(e){document.getElementById('error').textContent=e.message;}
      }));
      c.append(button('Dismiss locally',async()=>{try{await request('/api/mail-dismiss',{id:row.id,metadata_hash:hash});await opsRefresh();}catch(e){document.getElementById('error').textContent=e.message;}},'secondary'));
      dest.append(c);
    }
    if(!inbox.items.length)dest.append(node('p','No new metadata candidates in the configured scopes. This does not mean nothing needs attention.'));
  }catch(e){opsStatus.textContent=e.status===404?'Standalone household mode. No background worker or mail/push integration attached.':'Operations coverage unavailable; no all-clear.';}
  finally{opsBusy=false;}
}
function stableJSON(v){if(Array.isArray(v))return '['+v.map(stableJSON).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stableJSON(v[k])).join(',')+'}';return JSON.stringify(v);}
function urlBytes(s){const raw=atob(s.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-s.length%4)%4));return Uint8Array.from(raw,c=>c.charCodeAt(0));}
document.getElementById('enablePush').onclick=async()=>{
  try{
    if(!online||!window.isSecureContext||!('serviceWorker'in navigator)||!('PushManager'in window))throw new Error('A connected, trusted HTTPS browser with Web Push support is required.');
    const c=await request('/api/push-config');if(!c.enabled)throw new Error('Push is not configured by the local operator. No permission request was made.');
    if(!confirm('Enable generic private reminder notifications on this device? Routine titles and email details will not be included.'))return;
    const permission=await Notification.requestPermission();if(permission!=='granted')throw new Error('Notification permission not granted.');
    const reg=await navigator.serviceWorker.ready;
    const sub=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:urlBytes(c.public_key)});
    const result=await request('/api/push-subscribe',{subscription:sub.toJSON(),consent:true});
    // Endpoint stays in browser-managed storage. Only a non-secret local reference is saved here.
    sessionStorage.setItem('kj.pushId',result.subscription_id);
    document.getElementById('pushStatus').textContent='Device registered. Await a real reminder and verify it appears. Registration is not delivery proof.';
  }catch(e){document.getElementById('pushStatus').textContent=e.message;}
};
document.getElementById('disablePush').onclick=async()=>{
  try{
    const reg=await navigator.serviceWorker.ready,sub=await reg.pushManager.getSubscription();
    if(!sub){document.getElementById('pushStatus').textContent='No browser subscription.';return;}
    const normalized={endpoint:sub.toJSON().endpoint,keys:sub.toJSON().keys};
    const h=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(stableJSON(normalized)));
    const id=Array.from(new Uint8Array(h)).map(b=>b.toString(16).padStart(2,'0')).join('');
    // Disable local dispatch first; native unsubscribe also revokes the provider route.
    let serverDisabled=false;
    try{await request('/api/push-unsubscribe',{subscription_id:id});serverDisabled=true;}catch(e){}
    await sub.unsubscribe();sessionStorage.removeItem('kj.pushId');
    document.getElementById('pushStatus').textContent=serverDisabled?'Future sends disabled. Already submitted messages may still arrive.':'Browser subscription removed. Server unreachable; its local record still needs reconciliation.';
  }catch(e){document.getElementById('pushStatus').textContent=e.message;}
};
document.getElementById('pauseNetwork').onclick=async()=>{
  try{await request('/api/network-pause',{});await opsRefresh();}catch(e){document.getElementById('error').textContent=e.message;}
};
document.getElementById('lockSession').onclick=async()=>{
  try{await request('/api/logout',{});}catch(e){}
  csrf='';online=false;document.getElementById('workspace').hidden=true;document.getElementById('login').hidden=false;
  document.getElementById('error').textContent='Session locked. Any offline copy you explicitly enabled remains on this device; use Erase offline copy before sharing it.';
};
setInterval(()=>{if(document.visibilityState==='visible')opsRefresh();},30000);
window.addEventListener('online',()=>opsRefresh());setTimeout(opsRefresh,1500);

document.getElementById('measureForm').onsubmit=async e=>{
 e.preventDefault();const minutes=Number(document.getElementById('reviewMinutes').value);
 if(!Number.isInteger(minutes)||minutes<0||minutes>1440)return;
 try{await request('/api/measure',{kind:'review_seconds',value:minutes*60,event_id:crypto.randomUUID()});document.getElementById('measureStatus').textContent='Review time recorded as your report.';}
 catch(err){document.getElementById('measureStatus').textContent='Not recorded: '+err.message;}
};
