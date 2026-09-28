"""Narrow one-off calendar adapter and broker. No financial or browser executor.
The simulator and HTTP transport have deliberately different evidence labels.
"""
from __future__ import annotations
import json, urllib.request, urllib.error, urllib.parse, uuid
import time as monotime
from datetime import timedelta
from .common import *

class NoEffect(Refused): pass

FIELDS={'summary','description','start','end'}

def validate_proposal(p):
    keys(p,{'id','operation','operation_key','target','event_id','payload','expected_version'}, {'obligation_id'})
    for k in ['id','operation_key','target','event_id']:text(p[k],k,400)
    if p['operation'] not in {'calendar.create','calendar.update'}:raise Refused('Only bounded calendar create/update is implemented')
    if not isinstance(p['payload'],dict) or not {'summary','start','end'}<=p['payload'].keys() or p['payload'].keys()-FIELDS:
        raise Refused('Payload fields not allowed: attendees, source links, attachments, recurrence and arbitrary metadata are excluded')
    for k,v in p['payload'].items():text(v,k,4000 if k=='description' else 300)
    if instant(p['payload']['end'])<=instant(p['payload']['start']):raise Refused('End must follow start')
    if (instant(p['payload']['end'])-instant(p['payload']['start'])).total_seconds()>86400:raise Refused('Only one-off events of at most one day supported')
    if p['operation']=='calendar.create':
        if p['event_id']!=digest({'target':p['target'],'operation_key':p['operation_key']}):raise Refused('Creation requires stable client-selected event ID')
        if p['expected_version'] is not None:raise Refused('Create does not use an ETag precondition')
    else:text(p['expected_version'],'approved event version',500)

def make_proposal(target,payload,operation_key,*,event_id=None,expected_version=None,obligation_id=None):
    p={'id':str(uuid.uuid4()),'operation':'calendar.update' if event_id else 'calendar.create','operation_key':operation_key,
       'target':target,'event_id':event_id or digest({'target':target,'operation_key':operation_key}),
       'expected_version':expected_version,'payload':payload}
    if obligation_id:p['obligation_id']=obligation_id
    validate_proposal(p);return p

class SimCalendar:
    name='synthetic_calendar'
    contract='synthetic-cas-idempotent-v1'
    controls={'conditional_update':True,'client_event_id':True,'audience_read':True,'readback':True}
    live=False
    def __init__(self,root):
        self.root=private_root(root);self.db=connect(self.root/'simulated_provider.sqlite3');self.fault=None
        self.db.executescript('CREATE TABLE IF NOT EXISTS events(target TEXT,id TEXT,version INTEGER,body TEXT,PRIMARY KEY(target,id));CREATE TABLE IF NOT EXISTS audience(target TEXT PRIMARY KEY,body TEXT);CREATE TABLE IF NOT EXISTS provider_identity(k TEXT PRIMARY KEY,v TEXT NOT NULL);')
        self.db.execute("INSERT OR IGNORE INTO provider_identity VALUES('instance',?)",(str(uuid.uuid4()),))
        self.db.execute('INSERT OR IGNORE INTO audience VALUES(?,?)',('private-demo',canonical({'owner':'self@example.invalid','viewers':['self@example.invalid']})))
        self.db.execute('INSERT OR IGNORE INTO audience VALUES(?,?)',('shared-demo',canonical({'owner':'self@example.invalid','viewers':['self@example.invalid','other@example.invalid']})))
    def binding(self):
        return {'provider':self.name,'contract':self.contract,'environment':'SIMULATOR',
                'account_id':'synthetic-household','instance_id':self.db.execute("SELECT v FROM provider_identity WHERE k='instance'").fetchone()['v']}
    def close(self):self.db.close()
    def audience(self,target):
        row=self.db.execute('SELECT body FROM audience WHERE target=?',(target,)).fetchone()
        if not row:raise Refused('Unknown audience')
        return json.loads(row['body'])
    def get(self,target,event_id):
        row=self.db.execute('SELECT * FROM events WHERE target=? AND id=?',(target,event_id)).fetchone()
        return None if not row else {'id':row['id'],'version':str(row['version']),'payload':json.loads(row['body']),'origin':self.name}
    def apply(self,p,*,before_submit=None):
        validate_proposal(p)
        with transaction(self.db):
            r=self.get(p['target'],p['event_id'])
            if self.fault=='before':raise NoEffect('Synthetic provider rejected before commit')
            if p['operation']=='calendar.create':
                if r:raise Refused('Existing provider object needs reconciliation; no new dispatch')
                if before_submit:before_submit()
                self.db.execute('INSERT INTO events VALUES(?,?,1,?)',(p['target'],p['event_id'],canonical(p['payload'])))
            else:
                if not r or r['version']!=p['expected_version']:raise NoEffect('412: approved version changed')
                if before_submit:before_submit()
                self.db.execute('UPDATE events SET version=version+1,body=? WHERE target=? AND id=?',(canonical(p['payload']),p['target'],p['event_id']))
        if self.fault=='after':raise UnknownOutcome('Synthetic connection lost AFTER provider commit')
        if self.fault=='mismatch':
            self.db.execute('UPDATE events SET body=? WHERE target=? AND id=?',(canonical(dict(p['payload'],summary='external change')),p['target'],p['event_id']))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise Refused('Redirect refused; credentials never follow external destinations')

class GoogleCalendar:
    """Executable HTTPS adapter. Needs a trusted host-supplied OAuth token provider.
    There is no token acquisition, password collection, or native connector interception.
    Only events created by Kintsugi and without attendees/recurrence may be updated.
    """
    name='google_calendar_https'
    contract='google-calendar-oneoff-v1.1'
    controls={'conditional_update':True,'client_event_id':True,'audience_read':True,'readback':True}
    live=True
    def __init__(self,token_provider,allowed_calendars,transport=None,*,account_id=None,connection_id=None):
        self.token_provider=token_provider;self.allowed=set(allowed_calendars);self.transport=transport
        # account_id is the Google OpenID subject, verified against the CURRENT token
        # on real HTTPS calls. It is not a caller-authored field in the proposal.
        self.account_id=account_id;self.connection_id=connection_id
        self.opener=urllib.request.build_opener(NoRedirect())
    def binding(self):
        if not self.account_id:raise Refused('Provider account identity not configured')
        if self.transport and not self.connection_id:raise Refused('Mock connection needs an explicit isolated identity')
        return {'provider':self.name,'contract':self.contract,
                'environment':'MOCK_HTTP' if self.transport else 'LIVE_HTTPS',
                'account_id':self.account_id,
                'instance_id':self.connection_id if self.transport else 'https://www.googleapis.com/calendar/v3'}
    def _send(self,method,url,token,body=None,headers=None,before_submit=None):
        hdr={'Authorization':'Bearer '+token,'Accept':'application/json'};hdr.update(headers or {})
        data=None
        if body is not None:data=canonical(body).encode();hdr['Content-Type']='application/json'
        request=urllib.request.Request(url,data=data,headers=hdr,method=method)
        # All preparation, token acquisition and JSON serialization precede the guard.
        if before_submit:before_submit()
        try:
            with self.opener.open(request,timeout=20) as response:
                blob=response.read(1_000_001)
                if len(blob)>1_000_000:raise Refused('Provider response too large')
                return response.status,strict_json(blob.decode())
        except urllib.error.HTTPError as e:
            return e.code,{}
        except (urllib.error.URLError,TimeoutError,OSError):
            raise UnknownOutcome('Provider transport interrupted') from None

    def _url(self,target,suffix=''):
        if target not in self.allowed:raise Refused('Calendar outside trusted host allowlist')
        return 'https://www.googleapis.com/calendar/v3/calendars/'+urllib.parse.quote(target,safe='')+suffix
    def _request(self,method,url,body=None,headers=None,*,before_submit=None):
        if self.transport:
            if before_submit:before_submit()
            return self.transport(method,url,body,headers or {})
        self.binding()  # No anonymous/unbound live adapter.
        token=self.token_provider()
        if not isinstance(token,str) or not token or any(c.isspace() for c in token):
            raise Refused('OAuth token unavailable or malformed')
        # UserInfo requires separately consented OpenID scope. No credential harvesting.
        status,identity=self._send('GET','https://openidconnect.googleapis.com/v1/userinfo',token)
        if status!=200 or identity.get('sub')!=self.account_id:
            raise Refused('Current OAuth credential does not match the approved provider account')
        return self._send(method,url,token,body,headers,before_submit)
    def audience(self,target):
        viewers=[];owner=None;page=None;seen=set()
        for _ in range(100):
            suffix='/acl'+('?pageToken='+urllib.parse.quote(page,safe='') if page else '')
            status,body=self._request('GET',self._url(target,suffix))
            if status!=200:raise Refused('Calendar audience cannot be verified')
            for rule in body.get('items',[]):
                if rule.get('role')=='none':continue
                scope=rule.get('scope',{})
                if scope.get('type')!='user' or not scope.get('value'):raise Refused('Group, domain, public or unknown ACL unsupported')
                viewers.append(scope['value'])
                if rule.get('role')=='owner':
                    if owner and owner!=scope['value']:raise Refused('Ambiguous calendar owner')
                    owner=scope['value']
            page=body.get('nextPageToken')
            if not page:break
            if page in seen:raise Refused('ACL pagination cycle')
            seen.add(page)
        else:raise Refused('ACL scan incomplete')
        if not owner:raise Refused('No verified calendar owner')
        return {'owner':owner,'viewers':sorted(set(viewers))}
    def get(self,target,event_id):
        status,b=self._request('GET',self._url(target,'/events/'+urllib.parse.quote(event_id,safe='')))
        if status==404:return None
        if status!=200:raise Refused('Provider event read unavailable')
        if b.get('status')=='cancelled':return None
        if b.get('attendees') or b.get('recurrence') or b.get('recurringEventId'):raise Refused('Attended or recurring events outside this adapter')
        if b.get('extendedProperties',{}).get('private',{}).get('kintsugi') not in {'3.1','3.1.1'}:raise Refused('Only Kintsugi-owned canary events can be modified/readback')
        payload={'summary':b.get('summary',''),'start':b.get('start',{}).get('dateTime',''),'end':b.get('end',{}).get('dateTime','')}
        if 'description'in b:payload['description']=b['description']
        return {'id':b.get('id'),'version':b.get('etag'),'payload':payload,'origin':self.name}
    def apply(self,p,*,before_submit=None):
        validate_proposal(p)
        b=dict(p['payload']);b['start']={'dateTime':b['start']};b['end']={'dateTime':b['end']}
        if p['operation']=='calendar.create':
            # Fixed, disclosed creation defaults. Update NEVER reapplies these defaults.
            b['visibility']='private'
            b['extendedProperties']={'private':{'kintsugi':'3.1.1','operation':p['operation_key']}}
            b['reminders']={'useDefault':False,'overrides':[]}
            b['id']=p['event_id'];method='POST';url=self._url(p['target'],'/events?sendUpdates=none');h={}
        else:
            current=self.get(p['target'],p['event_id'])
            if not current or current['version']!=p['expected_version']:raise NoEffect('Approved event version changed')
            # PATCH contains only the fields approved in payload. Omitted reminders,
            # description, visibility and extended properties remain untouched.
            method='PATCH';url=self._url(p['target'],'/events/'+urllib.parse.quote(p['event_id'],safe='')+'?sendUpdates=none');h={'If-Match':p['expected_version']}
        status,_=self._request(method,url,b,h,before_submit=before_submit)
        if status in (200,201):return
        if status in (400,401,403,404,412):raise NoEffect('Provider rejected request: HTTP '+str(status))
        raise UnknownOutcome('Provider outcome needs reconciliation: HTTP '+str(status))

class Broker:
    def __init__(self,authority,adapter,*,live_enabled=False,startup=True):
        self.authority=authority;self.adapter=adapter;self.live_enabled=live_enabled
        if startup:self.authority.restart_boundary()
    def prepare(self,proposal):
        validate_proposal(proposal)
        if self.adapter.live and not self.live_enabled:raise Refused('Live writes disabled; conformance and operator setup required')
        if not all(self.adapter.controls.get(x) for x in ('conditional_update','client_event_id','audience_read','readback')):raise Refused('Adapter does not expose required controls')
        audience=self.adapter.audience(proposal['target'])
        context={'provider':self.adapter.name,'target':proposal['target'],'audience_hash':digest(audience),
                 'risk':'calendar_personal_data_write','adapter_contract':self.adapter.contract,
                 'provider_binding':self.adapter.binding()}
        return context,audience
    def _sharing(self,p,audience,grant):
        if audience['viewers']==[audience['owner']] or set(audience['viewers'])=={audience['owner']}:return
        if set(p['payload'])-{'summary','start','end'}:raise Refused('Shared records are limited to summary and times; source details stay private')
        sharing=grant.get('sharing')
        if not sharing:raise Refused('Shared destination requires explicit item-level sharing authorization')
        keys(sharing,{'target','audience_hash','fields','purpose'})
        if sharing['target']!=p['target'] or sharing['audience_hash']!=digest(audience) or set(sharing['fields'])!=set(p['payload']):raise Refused('Sharing scope does not match actual destination and every outgoing field')
        text(sharing['purpose'])
    def execute(self,proposal,token,now=None):
        p=strict_json(canonical(proposal)) # frozen proposal, not a mutable caller dictionary
        # Explicit historical time is a synthetic-test facility only. Production time
        # is sampled freshly at dispatch. A monotonic floor prevents a backward wall
        # clock adjustment during preparation from lengthening the authorization.
        if now is not None and self.adapter.live and not getattr(self.adapter,'transport',None):
            raise Refused('Caller-supplied dispatch time is forbidden for live HTTPS')
        first=now if now is not None else now_utc();started=monotime.monotonic()
        def fresh_time():
            floor=first+timedelta(seconds=max(0,monotime.monotonic()-started))
            return floor if now is not None else max(floor,now_utc())
        context,audience=self.prepare(p)
        g=self.authority.inspect_grant(token,p,context,fresh_time());self._sharing(p,audience,g)
        reserved=False
        expected_binding=context['provider_binding']
        def dispatch_guard():
            nonlocal reserved
            if reserved:raise Refused('Adapter attempted more than one submission')
            if self.adapter.binding()!=expected_binding:raise Refused('Provider/account changed before dispatch')
            # reserve rechecks signature, consumption, epoch, pause and fresh time
            # INSIDE the authority transaction, immediately before the transport call.
            self.authority.reserve(token,p,context,fresh_time)
            reserved=True
        try:
            self.adapter.apply(p,before_submit=dispatch_guard)
            if not reserved:raise Refused('Adapter did not enter the controlled dispatch boundary')
            return self.reconcile(p['operation_key'])
        except NoEffect as e:
            if reserved:self.authority.finish(p['operation_key'],'REJECTED_NO_EFFECT',{'origin':self.adapter.name,'provider_binding':expected_binding,'reason':str(e)})
            return {'status':'REJECTED_NO_EFFECT'}
        except Exception:
            if not reserved:raise  # preparation/authorization failure: no dispatch intent
            self.authority.finish(p['operation_key'],'UNKNOWN_EXTERNAL',{'origin':self.adapter.name,'provider_binding':expected_binding,'needs':'provider_readback'})
            return {'status':'UNKNOWN_EXTERNAL'}
    def reconcile(self,key):
        record=self.authority.intent(key);p=strict_json(record['proposal'])
        if not record.get('provider_binding'):
            raise Refused('Legacy intent has no provider/account binding; manual migration/reconciliation required')
        binding=strict_json(record['provider_binding'])
        if self.adapter.binding()!=binding:
            raise Refused('Recovery provider, account, environment or connection differs from original dispatch')
        # An exact provider namespace is mandatory even for terminal status retrieval.
        if record['status'] in {'PROVIDER_VERIFIED','REJECTED_NO_EFFECT'}:
            return {'status':record['status'],'receipt':strict_json(record['receipt']) if record['receipt'] else None,'historical_receipt':True}
        try:r=self.adapter.get(p['target'],p['event_id'])
        except Exception:r=None
        if self.adapter.binding()!=binding:
            raise Refused('Recovery binding changed during readback')
        matches=False
        if r and r.get('origin')==binding['provider'] and r.get('id')==p['event_id'] and r.get('version'):
            expected=p['payload'];observed=r.get('payload',{})
            # Partial calendar updates preserve unmentioned fields. Verify exactly the
            # approved fields, not a fictitious full replacement of the event.
            matches=isinstance(observed,dict) and set(expected)<=set(observed)
            for k,v in expected.items():
                try:equal=instant(observed.get(k,''))==instant(v) if k in {'start','end'} else observed.get(k)==v
                except (ValueError,TypeError):equal=False
                matches=matches and equal
        status='PROVIDER_VERIFIED' if matches else 'UNKNOWN_EXTERNAL'
        receipt={'origin':binding['provider'],'provider_binding':binding,'target':p['target'],'operation_key':key,
                 'evidence_scope':binding['environment'],'readback':r,'matches':matches,
                 'captured_at':iso(now_utc()),'obligation_completed':False}
        self.authority.finish(key,status,receipt)
        return {'status':status,'receipt':receipt}
