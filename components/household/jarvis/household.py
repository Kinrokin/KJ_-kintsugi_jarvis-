"""Private, local household records. None of these functions writes to a provider.
Human completion, routine occurrences and computer actions have distinct records.
"""
from __future__ import annotations
import json, uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from .common import *

class Household:
    def __init__(self, root):
        self.root=private_root(root); self.path=self.root/'household.sqlite3'
        existed=self.path.exists() and self.path.stat().st_size>0
        self.db=connect(self.path)
        if existed:
            try:
                row=self.db.execute("SELECT v FROM meta WHERE k='schema'").fetchone()
                if not row or row['v']!='3.1':raise Refused('Existing state has another schema; use an explicit migration and a new directory')
            except Exception:
                self.db.close()
                raise Refused('Existing state is not schema 3.1; no migration was performed') from None
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS delivery_outbox(id TEXT PRIMARY KEY,occurrence_id TEXT NOT NULL,created TEXT NOT NULL,expires TEXT NOT NULL,user_revision INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS routines(id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS occurrences(id TEXT PRIMARY KEY,routine_id TEXT NOT NULL,body TEXT NOT NULL,revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS obligations(id TEXT PRIMARY KEY,body TEXT NOT NULL,revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS captures(id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,digest TEXT NOT NULL,result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS history(seq INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,kind TEXT NOT NULL,object_id TEXT NOT NULL,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS measurements(id TEXT PRIMARY KEY,body TEXT NOT NULL);
        ''')
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('schema','3.1')")
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('instance',?)",(str(uuid.uuid4()),))
    def close(self): self.db.close()
    def _event(self,kind,oid,body,now):
        self.db.execute('INSERT INTO history(at,kind,object_id,body) VALUES(?,?,?,?)',(iso(now),kind,oid,canonical(body)))
    def _get(self,table,oid):
        if table not in {'occurrences','obligations','routines','captures','actions'}: raise Refused('Unknown record type')
        r=self.db.execute(f'SELECT * FROM {table} WHERE id=?',(oid,)).fetchone()
        if not r: raise Refused('Record not found')
        b=json.loads(r['body'])
        if 'revision' in r.keys(): b['revision']=r['revision']
        if table=='occurrences':b.setdefault('user_revision',0)
        return b
    def _put(self,table,b,*,user=False):
        if user and table=='occurrences':b['user_revision']=b.get('user_revision',0)+1
        revision=b.pop('revision')+1
        self.db.execute(f'UPDATE {table} SET body=?,revision=? WHERE id=?',(canonical(b),revision,b['id']))
        b['revision']=revision
        return b
    def _check_version(self,b,expected):
        integer(expected,'expected_revision',0)
        if b['revision']!=expected: raise Conflict('Record changed; refresh before applying this action')
    def _client_time(self,c,received_at):
        """Client occurrence time is a self-report, never authorization evidence."""
        event=c.get('client_event')
        if event is None:return received_at
        keys(event,{'version','occurred_at','household_instance','source'},
             {'definition_version','timezone','completion_variant','observed_user_revision'})
        if event['version']!=1 or type(event['version']) is not int or event['source']!='user_report':
            raise Refused('Unsupported client event envelope')
        instance=self.db.execute("SELECT v FROM meta WHERE k='instance'").fetchone()['v']
        if event['household_instance']!=instance:raise Conflict('Queued change belongs to another household instance')
        occurred=instant(event['occurred_at'])
        if occurred>received_at+timedelta(minutes=5):
            raise Conflict('Device clock is ahead of the server; review the reported time, do not silently rewrite it')
        return occurred
    def _check_occurrence_command(self,b,c):
        event=c.get('client_event')
        if not event:return self._check_version(b,c.get('expected_revision'))
        if event.get('definition_version')!=b['definition_version'] or event.get('timezone')!=b['timezone']:
            raise Conflict('Queued change refers to a different routine definition or timezone')
        integer(event.get('observed_user_revision'),'observed user revision',0)
        integer(c.get('expected_revision'),'expected_revision',0)
        if c['expected_revision']>b['revision'] or event['observed_user_revision']!=b.get('user_revision',0):
            raise Conflict('Someone changed this occurrence after the device last read it')
        # Only automated nudges/window expiration may change the main revision while
        # preserving user_revision. Never rebase through a user edit or redefinition.
        if b['status'] in {'SUPERSEDED','NEEDS_REVIEW'}:
            raise Conflict('Occurrence was superseded or needs review')
    def configure_routine(self,r,now=None):
        now=now or now_utc()
        keys(r,{'id','version','title','anchor','timezone','window_minutes','full_steps','minimum_steps','max_nudges','quiet_start','quiet_end','kind'},
             {'wall_time','fold','gap','interval','interval_semantics','first_due','event_name'})
        text(r['id']);text(r['title']);integer(r['version'],'version',1)
        if r['kind']!='ordinary': raise Refused('Clinical/treatment routines excluded from this household engine')
        if r['anchor'] not in {'clock','completion','event'}: raise Refused('Unsupported anchor')
        ZoneInfo(r['timezone']); integer(r['window_minutes'],'window',1,1440)
        integer(r['max_nudges'],'max_nudges',0,3)
        for s in [r['full_steps'],r['minimum_steps']]:
            if not isinstance(s,list) or not s or len(s)>20: raise Refused('Define full and minimum steps')
            for x in s:text(x,'step',300)
        if not set(r['minimum_steps'])<=set(r['full_steps']): raise Refused('Minimum must be selected from approved full steps')
        for t in [r['quiet_start'],r['quiet_end']]: time.fromisoformat(t)
        if r['anchor']=='clock': local_instant(now.astimezone(ZoneInfo(r['timezone'])).date(),r['wall_time'],r['timezone'],r.get('fold',0),r.get('gap','shift_forward'))
        if r['anchor']=='completion':
            instant(r['first_due']);integer(r['interval'],'interval',1,10000)
            if r['interval_semantics'] not in {'elapsed_hours','calendar_days'}: raise Refused('Choose interval semantics')
        if r['anchor']=='event': text(r['event_name'])
        with transaction(self.db):
            old=self.db.execute('SELECT body FROM routines WHERE id=?',(r['id'],)).fetchone()
            if old and canonical(r)!=canonical(json.loads(old['body'])):
                if r['version']<=json.loads(old['body'])['version']: raise Refused('Routine changes need a higher definition version')
                for row in self.db.execute('SELECT id,body,revision FROM occurrences WHERE routine_id=?',(r['id'],)).fetchall():
                    b=json.loads(row['body'])
                    if b['status'] in {'OPEN','UNKNOWN'}:
                        b['status']='SUPERSEDED';b['revision']=row['revision'];self._put('occurrences',b)
            self.db.execute('INSERT OR REPLACE INTO routines VALUES(?,?)',(r['id'],canonical(r)))
            self._event('ROUTINE_CONFIGURED',r['id'],{'version':r['version']},now)
    def _materialize(self,r,due,anchor_key,now):
        oid=digest({'routine':r['id'],'version':r['version'],'timezone':r['timezone'],'anchor':anchor_key})[:24]
        b={'id':oid,'routine_id':r['id'],'definition_version':r['version'],'title':r['title'],
           'due':iso(due),'window_end':iso(due+timedelta(minutes=r['window_minutes'])),
           'status':'OPEN','basis':None,'privacy':'private','full_steps':r['full_steps'],'minimum_steps':r['minimum_steps'],
           'completed_at':None,'completion_version':None,'next_nudge':iso(due),'nudges':0,'depends_on':anchor_key,
           'timezone':r['timezone'],'user_revision':0}
        if self.db.execute('INSERT OR IGNORE INTO occurrences VALUES(?,?,?,0)',(oid,r['id'],canonical(b))).rowcount:
            self._event('OCCURRENCE_CREATED',oid,{'anchor':anchor_key},now)
        return oid
    def tick(self,now=None):
        now=now or now_utc()
        with transaction(self.db):
            for row in self.db.execute('SELECT body FROM routines').fetchall():
                r=json.loads(row['body'])
                if r['anchor']=='clock':
                    day=now.astimezone(ZoneInfo(r['timezone'])).date()
                    due=local_instant(day,r['wall_time'],r['timezone'],r.get('fold',0),r.get('gap','shift_forward'))
                    self._materialize(r,due,day.isoformat(),now)
                elif r['anchor']=='completion':
                    all_b=[json.loads(x['body']) for x in self.db.execute('SELECT body FROM occurrences WHERE routine_id=?',(r['id'],))]
                    completions=[b for b in all_b if b['status']=='DONE' and b['definition_version']==r['version']]
                    if completions:
                        last=max(completions,key=lambda b:instant(b['completed_at'])); base=instant(last['completed_at'])
                        if r['interval_semantics']=='elapsed_hours': due=base+timedelta(hours=r['interval'])
                        else:
                            local=base.astimezone(ZoneInfo(r['timezone']))
                            due=local_instant(local.date()+timedelta(days=r['interval']),local.strftime('%H:%M'),r['timezone'],r.get('fold',0),r.get('gap','shift_forward'))
                        key=last['id']+':'+last['completed_at']
                    else: due=instant(r['first_due']);key='initial'
                    # Only one successor per completion. No occurrence avalanche after an outage.
                    self._materialize(r,due,key,now)
            for row in self.db.execute('SELECT * FROM occurrences').fetchall():
                b=json.loads(row['body'])
                if b['status']=='OPEN' and now>instant(b['window_end']):
                    r=self._get('routines',b['routine_id'])
                    if r['anchor']=='clock':
                        b['status']='UNKNOWN';b['revision']=row['revision'];self._put('occurrences',b)
                        self._event('WINDOW_ENDED_UNKNOWN',b['id'],{},now)
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('last_tick',?)",(iso(now),))
        return self.snapshot(now)
    def record_anchor(self,rid,event_id,occurred_at,now=None):
        now=now or now_utc();r=self._get('routines',rid)
        if r['anchor']!='event': raise Refused('Not an event-anchored routine')
        due=instant(occurred_at)
        if due>now+timedelta(minutes=5): raise Refused('Future event cannot be reported as already occurred')
        text(event_id)
        with transaction(self.db): return self._materialize(r,due,event_id,now)
    def import_email(self,mailbox,message_id,claim,now=None):
        """Extracted claims remain candidates; no instruction execution, external effect or acceptance."""
        now=now or now_utc();keys(claim,{'title','outcome','deadline'}, {'owner','sensitivity'})
        text(mailbox);text(message_id);text(claim['title']);text(claim['outcome'])
        if claim.get('sensitivity')=='employer_patient': raise Refused('Employer patient data excluded')
        if claim['deadline'] is not None: instant(claim['deadline'])
        oid=digest({'mailbox':mailbox,'message_id':message_id})[:24]
        with transaction(self.db):
            row=self.db.execute('SELECT * FROM obligations WHERE id=?',(oid,)).fetchone()
            if row:
                b=json.loads(row['body'])
                if b['candidate_claim']!=claim:
                    b['revision']=row['revision'];b['contradictions']=b.get('contradictions',[])+[claim]
                    b['needs_review']=True
                    if b['status']=='DONE': b['prior_status']='DONE';b['status']='NEEDS_REVIEW'
                    self._put('obligations',b)
                    self._event('SOURCE_CONTRADICTION',oid,{},now)
                return oid
            b={'id':oid,'title':claim['title'],'outcome':claim['outcome'],'deadline':claim['deadline'],
               'source':{'mailbox':mailbox,'message_id':message_id,'trust':'external_claim'},
               'candidate_claim':claim,'status':'CANDIDATE','owner':'unaccepted','owner_accepted':False,
               'basis':None,'privacy':'private','needs_review':False,'conditions':{},'next_nudge':claim['deadline']}
            self.db.execute('INSERT INTO obligations VALUES(?,?,0)',(oid,canonical(b)))
            self._event('OBLIGATION_CANDIDATE',oid,{'source_id':message_id},now)
        return oid
    def record_automation(self,action_id,record,now=None):
        """Record an untrusted report for display, NOT authenticated provider evidence.
        Only the authority/broker store holds adapter-originated verification.
        """
        now=now or now_utc()
        with transaction(self.db):
            self.db.execute('INSERT OR REPLACE INTO actions VALUES(?,?)',(text(action_id),canonical({'id':action_id,'status':'REPORTED_UNVERIFIED','report':record,'basis':'caller_report_not_provider_evidence'})))
            self._event('ACTION_RECORDED',action_id,{'obligation_auto_closed':False},now)
    def command(self,c,now=None):
        now=now or now_utc()
        keys(c,{'command_id','op'}, {'object_id','expected_revision','minutes','text','owner','criteria','condition','value','timezone','acceptance_note','outcome','deadline','claim_index','resolution_note','client_event'})
        text(c['command_id']);h=digest(c)
        allowed={'capture','make_task','done','undo','snooze','skip','simplify','normal','accept','delegate','confirm_acceptance','condition','complete_obligation','resolve_source','reopen_obligation'}
        if c['op'] not in allowed: raise Refused('Operation not in local household command set')
        with transaction(self.db):
            prior=self.db.execute('SELECT * FROM commands WHERE id=?',(c['command_id'],)).fetchone()
            if prior:
                if prior['digest']!=h: raise Conflict('Command ID reused with different content')
                return json.loads(prior['result'])
            occurred_at=self._client_time(c,now)
            op=c['op'];oid=c.get('object_id','');result={'ok':True,'op':op,'received_at':iso(now)}
            if op=='capture':
                value=text(c.get('text'),'capture',2000);oid=c['command_id']
                body={'id':oid,'text':value,'at':iso(occurred_at),'received_at':iso(now),'status':'INBOX','privacy':'private'}
                self.db.execute('INSERT INTO captures VALUES(?,?)',(oid,canonical(body)));result['id']=oid
            elif op=='make_task':
                captured=self._get('captures',oid)
                task_id=digest({'capture':oid})[:24]
                if not self.db.execute('SELECT 1 FROM obligations WHERE id=?',(task_id,)).fetchone():
                    deadline=c.get('deadline')
                    if deadline is not None:instant(deadline)
                    body={'id':task_id,'title':captured['text'],'outcome':text(c.get('outcome',captured['text'])),
                          'deadline':deadline,'source':{'capture_id':oid,'trust':'user_capture'},'candidate_claim':None,
                          'status':'OPEN','owner':'self','owner_accepted':True,'basis':None,'privacy':'private',
                          'needs_review':False,'conditions':{},'next_nudge':deadline}
                    self.db.execute('INSERT INTO obligations VALUES(?,?,0)',(task_id,canonical(body)))
                    captured['status']='TRIAGED';self.db.execute('UPDATE captures SET body=? WHERE id=?',(canonical(captured),oid))
                result['id']=task_id
            elif op in {'simplify','normal'}:
                tz=c.get('timezone','America/Chicago');day=occurred_at.astimezone(ZoneInfo(tz)).date().isoformat()
                self.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('mode:'+day,'minimum' if op=='simplify' else 'normal'))
                result['mode']='minimum' if op=='simplify' else 'normal';result['mode_date']=day
            elif op in {'done','undo','skip'}:
                b=self._get('occurrences',oid)
                if op=='done' and b['status']=='DONE':
                    if c.get('client_event') and (b['completed_at']!=iso(occurred_at) or b['completion_version']!=c['client_event'].get('completion_variant')):
                        raise Conflict('This occurrence already has a different completion report; review or undo it explicitly')
                    result.update({'id':oid,'deduplicated':True})
                else:
                    self._check_occurrence_command(b,c)
                    if b['status']=='SUPERSEDED': raise Conflict('Occurrence was superseded; review its history')
                    if op=='done':
                        if occurred_at<instant(b['due']): raise Refused('Cannot complete a future occurrence')
                        if c.get('client_event'):
                            variant=c['client_event'].get('completion_variant')
                            if variant not in {'minimum','full'}:raise Refused('Queued completion must name the steps actually displayed')
                        else:
                            day=occurred_at.astimezone(ZoneInfo(b['timezone'])).date().isoformat()
                            m=self.db.execute('SELECT v FROM meta WHERE k=?',('mode:'+day,)).fetchone()
                            variant='minimum' if m and m['v']=='minimum' else 'full'
                        b.update(status='DONE',basis='user_reported',completed_at=iso(occurred_at),completion_version=variant,
                                 completion_received_at=iso(now),completion_time_basis='client_reported' if c.get('client_event') else 'synchronous_local_command')
                    elif op=='skip': b.update(status='SKIPPED',basis='user_reported_skip',completed_at=None,skipped_at=iso(occurred_at))
                    else:
                        if b['status']!='DONE': raise Refused('Only completion can be undone')
                        for row in self.db.execute('SELECT * FROM occurrences WHERE routine_id=?',(b['routine_id'],)).fetchall():
                            child=json.loads(row['body'])
                            if child['depends_on']==oid+':'+b['completed_at']:
                                child['revision']=row['revision'];child['status']='NEEDS_REVIEW' if child['status']=='DONE' else 'SUPERSEDED'
                                self._put('occurrences',child)
                        b.update(status='OPEN' if now<=instant(b['window_end']) else 'UNKNOWN',basis=None,completed_at=None,completion_version=None)
                    self._put('occurrences',b,user=True);result['id']=oid
            elif op=='snooze':
                table='occurrences' if self.db.execute('SELECT 1 FROM occurrences WHERE id=?',(oid,)).fetchone() else 'obligations'
                b=self._get(table,oid)
                if table=='occurrences':self._check_occurrence_command(b,c)
                else:self._check_version(b,c.get('expected_revision'))
                mins=integer(c.get('minutes'),'minutes',1,1440)
                if b['status'] in {'DONE','SKIPPED','SUPERSEDED','NEEDS_REVIEW'}:raise Refused('This occurrence is no longer nudgeable')
                if b['status']=='UNKNOWN' and not (c.get('client_event') and occurred_at<=instant(b['window_end'])):
                    raise Refused('This occurrence is no longer nudgeable')
                b['next_nudge']=iso(occurred_at+timedelta(minutes=mins));self._put(table,b,user=True)
                result.update({'id':oid,'deadline_unchanged':True,'snooze_elapsed_at_reconnection':instant(b['next_nudge'])<=now})
            else:
                b=self._get('obligations',oid);self._check_version(b,c.get('expected_revision'))
                if op=='resolve_source':
                    if not b['needs_review']:raise Refused('No source conflict to resolve')
                    note=text(c.get('resolution_note'),'resolution note',1000)
                    candidates=[b['candidate_claim']]+b.get('contradictions',[])
                    ix=integer(c.get('claim_index'),'claim index',0,len(candidates)-1)
                    chosen=candidates[ix]
                    b.update(title=chosen['title'],outcome=chosen['outcome'],deadline=chosen['deadline'],candidate_claim=chosen,needs_review=False,
                             status='OPEN' if b['owner_accepted'] else 'CANDIDATE',conditions={chosen['outcome']:False},
                             basis=None,completed_at=None,resolution_basis='user_selected_claim',resolution_note=note)
                    b.setdefault('source_history',[]).append({'at':iso(now),'candidates':candidates,'selected_index':ix})
                    b['contradictions']=[]
                elif op=='reopen_obligation':
                    if b['status']!='DONE':raise Refused('Only a completed obligation can be reopened')
                    b.update(status='OPEN',basis=None,completed_at=None)
                elif op=='accept':
                    if b['needs_review']: raise Refused('Resolve conflicting evidence before accepting')
                    criteria=c.get('criteria',[])
                    if not isinstance(criteria,list) or len(criteria)>20:raise Refused('Invalid criteria')
                    for criterion in criteria:text(criterion,'criterion',200)
                    b.update(owner='self',owner_accepted=True,status='OPEN',conditions={x:False for x in criteria})
                elif op=='delegate':
                    b.update(owner=text(c.get('owner'),'owner',200),owner_accepted=False,status='AWAITING_ACCEPTANCE')
                elif op=='confirm_acceptance':
                    if b['status']!='AWAITING_ACCEPTANCE':raise Refused('No pending delegation')
                    note=text(c.get('acceptance_note'),'acceptance evidence',1000)
                    b.update(owner_accepted=True,status='OPEN',acceptance_basis='user_reported',acceptance_note=note)
                elif op=='condition':
                    name=c.get('condition')
                    if name not in b['conditions'] or type(c.get('value')) is not bool:raise Refused('Unknown condition')
                    b['conditions'][name]=c['value']
                elif op=='complete_obligation':
                    if not b['owner_accepted'] or b['needs_review'] or not all(b['conditions'].values()):
                        raise Refused('Unaccepted owner, evidence conflict or unresolved completion condition')
                    b.update(status='DONE',basis='user_reported',completed_at=iso(occurred_at),completion_received_at=iso(now))
                self._put('obligations',b);result['id']=oid
            self._event('USER_'+op.upper()+('_IDEMPOTENT' if result.get('deduplicated') else ''),oid,{'command_id':c['command_id'],'client_event':c.get('client_event'),'occurred_at':iso(occurred_at),'received_at':iso(now)},now)
            self.db.execute('INSERT INTO commands VALUES(?,?,?)',(c['command_id'],h,canonical(result)))
        return result
    def remind(self,oid,now=None):
        """Commit one cue offered to the local UI; NOT a delivery/reading/completion receipt."""
        now=now or now_utc()
        with transaction(self.db):
            b=self._get('occurrences',oid);r=self._get('routines',b['routine_id'])
            local=now.astimezone(ZoneInfo(r['timezone'])).strftime('%H:%M');a,z=r['quiet_start'],r['quiet_end']
            quiet=(a<=local<z) if a<z else (local>=a or local<z)
            if b['status']!='OPEN' or b['nudges']>=r['max_nudges'] or quiet or now<instant(b['next_nudge']) or now>instant(b['window_end']):
                return {'display':False,'status':b['status']}
            b['nudges']+=1;b['next_nudge']=iso(now+timedelta(minutes=30));self._put('occurrences',b)
            self._event('LOCAL_CUE',oid,{'delivery':'OFFERED_TO_LOCAL_UI_NOT_DELIVERY_PROOF'},now)
            cue_id=oid+':'+str(b['nudges'])
            self.db.execute('INSERT OR IGNORE INTO delivery_outbox VALUES(?,?,?,?,?)',(cue_id,oid,iso(now),b['window_end'],b.get('user_revision',0)))
            return {'display':True,'preview':'Private routine reminder','occurrence_id':oid}
    def measure(self,kind,value,event_id=None,now=None):
        now=now or now_utc()
        if kind not in {'review_seconds','maintenance_seconds','unnecessary_alert','missed_obligation','false_denial','verified_savings_cents','operating_cost_cents'}:raise Refused('Unknown metric')
        integer(value,'value',0);event_id=event_id or str(uuid.uuid4())
        b={'id':event_id,'kind':kind,'value':value,'at':iso(now),'basis':'user_recorded'}
        with transaction(self.db):self.db.execute('INSERT OR IGNORE INTO measurements VALUES(?,?)',(event_id,canonical(b)))
    def snapshot(self,now=None):
        now=now or now_utc()
        result={t:[dict(json.loads(r['body']),**({'revision':r['revision']} if 'revision' in r.keys() else {})) for r in self.db.execute(f'SELECT * FROM {t}')] for t in ('occurrences','obligations','captures','actions','measurements')}
        for b in result['occurrences']:
            b.setdefault('user_revision',0)
            day=instant(b['due']).astimezone(ZoneInfo(b['timezone'])).date().isoformat()
            mode=self.db.execute('SELECT v FROM meta WHERE k=?',('mode:'+day,)).fetchone()
            b['display_variant']='minimum' if mode and mode['v']=='minimum' else 'full'
        result['instance_id']=self.db.execute("SELECT v FROM meta WHERE k='instance'").fetchone()['v']
        result['runtime_version']='3.2.0';result['client_protocol']=1
        result['now']=iso(now);result['household_timezone']='America/Chicago';result['mode']='normal';result['external_writes']='NOT_EXPOSED_BY_HOUSEHOLD_UI'
        day=now.astimezone(ZoneInfo('America/Chicago')).date().isoformat();m=self.db.execute('SELECT v FROM meta WHERE k=?',('mode:'+day,)).fetchone()
        result['mode_date']=day
        if m: result['mode']=m['v']
        result['upcoming']=[b for b in result['occurrences'] if b['status']=='OPEN']
        result['open_obligations']=[b for b in result['obligations'] if b['status']!='DONE']
        return result
