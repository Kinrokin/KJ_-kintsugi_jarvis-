'use strict';
// Executes the actual service-worker code with synthetic browser facilities.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const file=path.join(__dirname,'../web/sw.js'),checks=[];
function fixture(){
 const handlers={},calls={shown:[],requests:[],opened:[],cached:[]};
 const env={URL,Date,Number,JSON,Promise,console,fetch:async(url,opts)=>{calls.requests.push({url,opts});return {};},
   caches:{open:async()=>({addAll:async v=>calls.cached.push(...v),match:async()=>null}),keys:async()=>[],delete:async()=>{}},
   self:{location:{origin:'https://private.invalid'},addEventListener:(n,fn)=>handlers[n]=fn,
     registration:{showNotification:async(...args)=>calls.shown.push(args)},
     clients:{claim:async()=>{},matchAll:async()=>[],openWindow:async u=>calls.opened.push(u)}}};
 vm.createContext(env);vm.runInContext(fs.readFileSync(file,'utf8'),env);
 async function invoke(type,event){let pending;handlers[type]({...event,waitUntil:p=>pending=p});if(pending)await pending;}
 return {handlers,calls,env,invoke};
}
async function check(name,fn){await fn();checks.push({name,status:'PASS'});}
(async()=>{
const payload=()=>({version:1,id:'a'.repeat(64),ack_token:'b'.repeat(43),expires:new Date(Date.now()+60000).toISOString(),title:'DO NOT EXPOSE',url:'https://evil.invalid'});
await check('Cache only static shell; no API resource cached',async()=>{const f=fixture();await f.invoke('install',{});assert(f.calls.cached.includes('/operations.js'));assert(!f.calls.cached.some(x=>x.startsWith('/api/')));});
await check('External/API/POST fetches are not intercepted',async()=>{const f=fixture();for(const [method,url] of [['GET','https://private.invalid/api/state'],['POST','https://private.invalid/'],['GET','https://elsewhere.invalid/app.js']])f.handlers.fetch({request:{method,url},respondWith:()=>{throw Error('intercepted unsafe fetch');}});});
await check('Valid encrypted-payload fixture produces generic notification',async()=>{const f=fixture();await f.invoke('push',{data:{json:payload}});assert.equal(f.calls.shown.length,1);assert(!JSON.stringify(f.calls.shown[0].slice(0,1)).includes('DO NOT EXPOSE'));assert.equal(f.calls.shown[0][1].body,'Open your private household view when it is safe to do so.');});
await check('Receipt calls only scoped endpoint, not completion',async()=>{const f=fixture();await f.invoke('push',{data:{json:payload}});assert.equal(f.calls.requests[0].url,'/api/push-ack');assert.equal(JSON.parse(f.calls.requests[0].opts.body).phase,'displayed');assert(!JSON.stringify(f.calls.requests).includes('/api/command'));});
await check('Expired notification is not displayed',async()=>{const f=fixture();await f.invoke('push',{data:{json:()=>({...payload(),expires:'2000-01-01T00:00:00Z'})}});assert.equal(f.calls.shown.length,0);});
await check('Malformed notification is ignored',async()=>{const f=fixture();await f.invoke('push',{data:{json:()=>({...payload(),id:'not-valid'})}});assert.equal(f.calls.shown.length,0);});
await check('Unparseable payload is ignored',async()=>{const f=fixture();await f.invoke('push',{data:{json:()=>{throw Error('bad JSON');}}});assert.equal(f.calls.shown.length,0);});
await check('Click cannot navigate injected destination',async()=>{const f=fixture();await f.invoke('notificationclick',{notification:{close:()=>{},data:payload()}});assert.deepEqual(f.calls.opened,['/']);assert.equal(JSON.parse(f.calls.requests[0].opts.body).phase,'opened');});
await check('Failed showNotification generates no display receipt',async()=>{const f=fixture();f.env.self.registration.showNotification=async()=>{throw Error('blocked');};await assert.rejects(()=>f.invoke('push',{data:{json:payload}}));assert.equal(f.calls.requests.length,0);});
await check('Offline receipt failure does not mark human completion',async()=>{const f=fixture();f.env.fetch=async()=>{throw Error('offline');};await f.invoke('push',{data:{json:payload}});assert.equal(f.calls.shown.length,1);assert(!f.handlers.sync);});
const report={scope:'ACTUAL_JS_LOGIC_WITH_SYNTHETIC_PUSH_SERVICE_WORKER_APIS',count:checks.length,checks,real_push_delivery:false,native_service_worker_lifecycle:false,physical_phone:false};
const out=process.argv[2];if(out)fs.writeFileSync(out,JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exit(1);});
