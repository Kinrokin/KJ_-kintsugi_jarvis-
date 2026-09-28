'use strict';
// Cache static application bytes only; never fetch/cache APIs or source emails.
const CACHE='kintsugi-shell-3.2.0';
const SHELL=['/','/app.js','/operations.js','/style.css','/manifest.webmanifest','/icon.svg'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL))));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
  for(const key of await caches.keys())if(key.startsWith('kintsugi-shell-')&&key!==CACHE)await caches.delete(key);
  await self.clients.claim();
})()));
self.addEventListener('fetch',event=>{
  const u=new URL(event.request.url);
  if(event.request.method!=='GET'||u.origin!==self.location.origin||!SHELL.includes(u.pathname)||u.search)return;
  event.respondWith(caches.open(CACHE).then(async c=>(await c.match(event.request))||fetch(event.request)));
});
function validPush(p){return p&&p.version===1&&/^[a-f0-9]{64}$/.test(p.id)&&typeof p.ack_token==='string'&&/^[A-Za-z0-9_-]{30,100}$/.test(p.ack_token)&&Number.isFinite(Date.parse(p.expires));}
async function report(p,phase){
  try{await fetch('/api/push-ack',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:p.id,token:p.ack_token,phase}),cache:'no-store'});}catch(e){}
  // Offline/missing receipt remains unknown; never invent a successful delivery.
}
self.addEventListener('push',event=>event.waitUntil((async()=>{
  let p;try{p=event.data.json();}catch(e){return;}
  if(!validPush(p)||Date.parse(p.expires)<Date.now())return;
  await self.registration.showNotification('JARVIS — private reminder',{
    body:'Open your private household view when it is safe to do so.',
    tag:p.id,renotify:false,data:p,icon:'/icon.svg'
  });
  await report(p,'displayed'); // Client report of showNotification resolving, not proof a human saw it.
})()));
self.addEventListener('notificationclick',event=>{
  event.notification.close();const p=event.notification.data;
  event.waitUntil((async()=>{
    if(validPush(p))await report(p,'opened');
    const clients=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    const target=clients.find(c=>new URL(c.url).origin===self.location.origin);
    if(target)await target.focus();else await self.clients.openWindow('/');
  })());
});
// No push-triggered completion, arbitrary URLs, microphone or authority endpoints.
