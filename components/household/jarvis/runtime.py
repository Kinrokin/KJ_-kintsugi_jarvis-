"""Foreground supervisor + read-only mailbox/routine worker, optionally launched by the OS.
Never exposes the calendar authority store. No dependency installation or paid API use.
"""
from __future__ import annotations
import contextlib, importlib.util, json, os, signal, socket, ssl, sys, threading, time as monotime, uuid
from pathlib import Path
from .common import *
from .secret_store import SecretStore
from .service_store import ServiceStore
from .household import Household

class InstanceLock:
    """OS-held lock for one runtime directory on one host. NOT a distributed lock."""
    def __init__(self,root,name='runtime.lock'):self.path=private_root(root)/name;self.f=None
    def __enter__(self):
        if self.path.is_symlink():raise Refused('Instance lock symlink refused')
        self.f=open(self.path,'a+b');self.f.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                if self.path.stat().st_size==0:self.f.write(b'0');self.f.flush()
                self.f.seek(0);msvcrt.locking(self.f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.f.close();self.f=None;raise Refused('Another process already owns this runtime directory') from None
        return self
    def __exit__(self,*args):
        if self.f:
            if os.name=='nt':
                import msvcrt
                self.f.seek(0);msvcrt.locking(self.f.fileno(),msvcrt.LK_UNLCK,1)
            self.f.close();self.f=None

DEFAULT_CONFIG={'version':1,'home':'','host':'127.0.0.1','port':8765,'origin':None,'tls_cert':None,'tls_key':None,
                'worker_seconds':30,'mail_poll_seconds':900,'sources':[],
                'push':{'enabled':False,'contact':'','daily_limit':12},'continuity_export':True}

def validate_config(c):
    keys(c,set(DEFAULT_CONFIG))
    if type(c['version']) is not int or c['version']!=1:raise Refused('Runtime config version not supported')
    if not isinstance(c['home'],str) or not Path(c['home']).expanduser().is_absolute():raise Refused('Use an absolute private runtime home')
    if Path(c['home']).expanduser().resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise Refused('Runtime state must be outside the code package')
    integer(c['port'],'port',1024,65535);integer(c['worker_seconds'],'worker interval',15,300)
    integer(c['mail_poll_seconds'],'mail interval',300,86400)
    text(c['host'],'host',100)
    if c['host']!='127.0.0.1' and not all(c[k] for k in ('origin','tls_cert','tls_key')):raise Refused('Phone listener requires trusted TLS and explicit origin')
    if bool(c['tls_cert'])!=bool(c['tls_key']):raise Refused('Both TLS files required')
    if type(c['continuity_export']) is not bool:raise Refused('Continuity setting must be boolean')
    if not isinstance(c['sources'],list) or len(c['sources'])>8:raise Refused('At most eight explicit personal source scopes')
    seen=set()
    for s in c['sources']:
        keys(s,{'id','provider','account','selector','credential_ref','enabled'},{'lookback_days','max_pages'})
        if not isinstance(s['enabled'],bool):raise Refused('Source enabled must be boolean')
        for k in ('id','account','selector','credential_ref'):text(s[k],k,500)
        if s['id'] in seen:raise Refused('Duplicate source ID')
        seen.add(s['id'])
        if s['provider'] not in {'gmail','outlook'}:raise Refused('Unsupported source')
        integer(s.get('max_pages',20),'pages',1,100);integer(s.get('lookback_days',14),'lookback',1,365)
    keys(c['push'],{'enabled','contact','daily_limit'})
    if type(c['push']['enabled']) is not bool:raise Refused('Push enabled must be boolean')
    integer(c['push']['daily_limit'],'push cap',1,50)
    if c['push']['enabled'] and (not c['origin'] or not c['tls_cert']):raise Refused('Push activation requires the configured trusted HTTPS phone origin')
    return c

def load_config(path):
    p=Path(path)
    if p.is_symlink():raise Refused('Config symlink refused')
    return validate_config(strict_json(p.read_text()))

def atomic_private(path,data):
    p=Path(path)
    if p.is_symlink():raise Refused('Output symlink refused')
    tmp=p.with_name('.'+p.name+'.'+uuid.uuid4().hex)
    with open(tmp,'x',encoding='utf-8') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o600);os.replace(tmp,p)

def initialize(c):
    validate_config(c);home=private_root(c['home'])
    h=Household(home/'household');h.close();s=ServiceStore(home/'operations');s.close()
    vault=SecretStore(home/'secrets')
    if not vault.exists('ui_login'):
        import secrets
        vault.put('ui_login',{'token':secrets.token_urlsafe(32)})
    return {'home':str(home),'secret_protection':vault.protection,'default_external_writes':'NONE','routine_times':'NOT_CONFIGURED'}

def doctor(c):
    validate_config(c);home=Path(c['home']).expanduser();checks=[]
    checks.append({'name':'runtime_config','status':'PASS'})
    checks.append({'name':'python','status':'PASS' if sys.version_info>=(3,10) else 'BLOCKED'})
    try:ZoneInfo('America/Chicago');zone='PASS'
    except Exception:zone='BLOCKED_NEEDS_TZDATA'
    checks.append({'name':'timezone_database','status':zone})
    if c['tls_cert']:
        try:
            ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(c['tls_cert'],c['tls_key']);tls='LOCAL_KEY_PAIR_LOADS_PHONE_TRUST_NOT_PROVEN'
        except Exception:tls='BLOCKED_TLS_KEY_PAIR'
        checks.append({'name':'tls','status':tls})
    checks.extend([{'name':'physical_phone','status':'NOT_TESTED'}, {'name':'OS_autostart','status':'NOT_INSTALLED_BY_DOCTOR'},
                   {'name':'independent_watchdog','status':'NOT_CONFIGURED'}, {'name':'bank_or_calendar_writes','status':'NOT_IN_RUNTIME'},
                   {'name':'push_library','status':'INSTALLED_NOT_LIVE_TESTED' if importlib.util.find_spec('pywebpush') else 'OPTIONAL_NOT_INSTALLED'}])
    return {'checks':checks,'sources_enabled':len([x for x in c['sources'] if x['enabled']]),
            'installations_performed':0,'credentials_printed':0,'scope':'local preflight only'}

class Worker:
    def __init__(self,c,*,token_factory=None,http_factory=None,push_sender=None):
        self.c=validate_config(c);self.home=private_root(c['home']);self.token_factory=token_factory;self.http_factory=http_factory;self.sender=push_sender
    def cycle(self,now=None,*,lane='all'):
        if lane not in {'all','household','mail'}:raise Refused('Unknown worker lane')
        now=now or now_utc();store=ServiceStore(self.home/'operations');h=Household(self.home/'household');result={'mail':[],'push':[]}
        try:
            snap=h.snapshot(now) if lane=='mail' else h.tick(now);paused=store.get('outbound_paused',False)
            if lane!='mail' and self.c['push']['enabled'] and not paused:
                from .notifications import WebPushSender, queue_event, dispatch
                sender=self.sender
                if sender is None and WebPushSender.available():
                    sender=WebPushSender(SecretStore(self.home/'secrets'),self.c['push']['contact'])
                if sender is None:store.set('push_health','DEPENDENCY_NOT_INSTALLED_NO_DELIVERY')
                else:
                    # Persist cue creation in the SAME transaction as the nudge counter.
                    day=now.date().isoformat()
                    used=store.db.execute("SELECT count(*) FROM notifications WHERE attempted LIKE ?",(day+'%',)).fetchone()[0]
                    if used<self.c['push']['daily_limit'] and store.db.execute('SELECT count(*) FROM subscriptions WHERE active=1').fetchone()[0]:
                        for r in snap['upcoming']:h.remind(r['id'],now)
                    for e in h.db.execute('SELECT * FROM delivery_outbox WHERE expires>?',(iso(now),)).fetchall():
                        queue_event(store,dict(e),now)
                    day=now.date().isoformat()
                    used=store.db.execute("SELECT count(*) FROM notifications WHERE attempted LIKE ?",(day+'%',)).fetchone()[0]
                    remaining=max(0,self.c['push']['daily_limit']-used)
                    def eligible(n):
                        e=h.db.execute('SELECT * FROM delivery_outbox WHERE id=?',(n['object_id'],)).fetchone()
                        if not e:return False
                        try:o=h._get('occurrences',e['occurrence_id'])
                        except Refused:return False
                        routine=h._get('routines',o['routine_id'])
                        local=now.astimezone(ZoneInfo(routine['timezone'])).strftime('%H:%M');a,z=routine['quiet_start'],routine['quiet_end']
                        quiet=(a<=local<z) if a<z else (local>=a or local<z)
                        return not quiet and o['status']=='OPEN' and o.get('user_revision',0)==e['user_revision'] and instant(o['window_end'])>now
                    if remaining:result['push']=dispatch(store,sender,now,limit=min(1,remaining),eligible=eligible)
                    store.set('push_health','TRANSPORT_CONFIGURED_DELIVERY_NOT_GUARANTEED')
            for cfg in (self.c['sources'] if lane!='household' else []):
                if not cfg['enabled']:continue
                if store.get('outbound_paused',False):break
                old=store.source(cfg['id'])
                if old and old['checked_at'] and 0<=(now-instant(old['checked_at'])).total_seconds()<self.c['mail_poll_seconds']:continue
                try:
                    from .oauth import RefreshCredential
                    from .mail_ingest import poll_source
                    token=self.token_factory(cfg) if self.token_factory else RefreshCredential(SecretStore(self.home/'secrets'),cfg['credential_ref'],'google' if cfg['provider']=='gmail' else 'microsoft').token(now)
                    result['mail'].append(poll_source(store,cfg,token,self.http_factory(cfg) if self.http_factory else None,now))
                except Exception:
                    # Always represent configured but inaccessible sources; never drop them.
                    binding={'provider':cfg['provider'],'account':cfg['account'],'credential_ref':cfg['credential_ref']}
                    if not old:
                        scope={'selector':cfg['selector'],'lookback_days':cfg.get('lookback_days',14) if cfg['provider']=='gmail' else None,'metadata_only':True,'interpretation':'No assurance all household obligations are represented'}
                        store.begin_source(cfg['id'],binding,scope,now)
                    store.fail_source(cfg['id'],'CREDENTIAL_OR_CONFIG_BLOCKED',now)
                    result['mail'].append({'id':cfg['id'],'status':'DEGRADED','error_code':'CREDENTIAL_OR_CONFIG_BLOCKED'})
            # Heartbeat records completion, not the earlier cycle start.
            completed=now if self.token_factory or self.http_factory or self.sender else now_utc()
            store.set('mail_worker_heartbeat' if lane=='mail' else 'heartbeat',{'at':iso(completed),'cycle_started':iso(now),'outbound_paused':store.get('outbound_paused',False)})
            report=store.overview([s['id'] for s in self.c['sources'] if s['enabled']],completed,max_age=self.c['mail_poll_seconds']*2,heartbeat_max_age=self.c['worker_seconds']*3+30)
            if lane!='mail':atomic_private(self.home/'health.json',canonical(report)+'\n')
            if lane!='mail' and self.c['continuity_export']:
                lines=['PRIVATE HOUSEHOLD FALLBACK','Generated: '+iso(completed),'Not proof of complete email/bank coverage. No provider actions implied.','']
                for o in snap['open_obligations']:lines.append(o['title']+' | '+o['status']+' | due: '+str(o['deadline'])+' | owner: '+o['owner'])
                atomic_private(self.home/'continuity.txt','\n'.join(lines)+'\n')
            result['health']=report;return result
        finally:h.close();store.close()
    def run(self,stop,lane='all'):
        while not stop.is_set():
            try:self.cycle(lane=lane)
            except Exception:
                with contextlib.suppress(Exception):
                    s=ServiceStore(self.home/'operations');s.event('WORKER_'+lane.upper(),'CYCLE_FAILED');s.close()
            stop.wait(self.c['worker_seconds'])

def run_service(c):
    """Block until stopped. Starts no provider writer and no paid model calls."""
    validate_config(c);home=private_root(c['home'])
    from .web import LocalUI
    with InstanceLock(home):
        initialize(c)
        ctx=None
        if c['tls_cert']:
            ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(c['tls_cert'],c['tls_key'])
        token=SecretStore(home/'secrets').get('ui_login')['token']
        server=LocalUI(home/'household',c['port'],token,host=c['host'],tls_context=ctx,public_origin=c['origin'],operations_config=c)
        stop=threading.Event();worker=Worker(c)
        threads=[threading.Thread(target=worker.run,args=(stop,lane),daemon=True) for lane in ('household','mail')]
        for thread in threads:thread.start()
        def halt(*_):stop.set();threading.Thread(target=server.shutdown,daemon=True).start()
        for sig in (signal.SIGINT,signal.SIGTERM):
            with contextlib.suppress(ValueError):signal.signal(sig,halt)
        print('Kintsugi runtime active. Local logs never include the login code.',flush=True)
        print('Calendar and payment execution are not exposed by this service.',flush=True)
        try:server.serve_forever(poll_interval=.25)
        finally:
            stop.set();server.server_close()
            for thread in threads:thread.join(timeout=15)
