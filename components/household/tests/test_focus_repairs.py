"""Focused review regressions, with both safe refusals and successful work.
No real provider/account is used. Fake HTTP transports are explicitly namespaced.
"""
import copy,json,tempfile,unittest,uuid
from pathlib import Path
from datetime import timedelta
from contextlib import contextmanager
from unittest.mock import patch
from jarvis.common import *
from jarvis.authority import Authority
from jarvis.calendar import Broker,GoogleCalendar,SimCalendar,make_proposal
from jarvis.household import Household
from test_household import routine

NOW=instant('2026-09-24T13:00:00Z');PW='synthetic-test-operator-password'
def proposal(target='private-demo',key=None):
    return make_proposal(target,{'summary':'Synthetic canary','start':'2026-09-25T13:00:00Z','end':'2026-09-25T14:00:00Z'},key or str(uuid.uuid4()))
class MockGoogle:
    def __init__(self):self.events={};self.calls=[];self.after_commit=False;self.clock_hook=None
    def __call__(self,method,url,body,headers):
        self.calls.append((method,url,copy.deepcopy(body),dict(headers)))
        if '/acl' in url:return 200,{'items':[{'role':'owner','scope':{'type':'user','value':'owner@example.invalid'}}]}
        if method=='GET':
            if self.clock_hook:self.clock_hook()
            eid=url.rsplit('/',1)[-1]
            return (200,copy.deepcopy(self.events[eid])) if eid in self.events else (404,{})
        eid=body.get('id') or url.split('/events/',1)[1].split('?')[0]
        if method=='POST':
            if eid in self.events:return 409,{}
            self.events[eid]=copy.deepcopy(body);self.events[eid]['etag']='"1"'
        elif method=='PATCH':
            if eid not in self.events:return 404,{}
            if headers.get('If-Match')!=self.events[eid]['etag']:return 412,{}
            self.events[eid].update(copy.deepcopy(body));self.events[eid]['etag']='"2"'
        if self.after_commit:raise UnknownOutcome('Mock response lost after provider commit')
        return (201 if method=='POST' else 200),{}
    def writes(self):return [x for x in self.calls if x[0] in {'POST','PATCH'}]

class FocusBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.auth=Authority(self.root/'auth');self.auth.initialize(PW)
        self.provider=SimCalendar(self.root/'provider');self.b=Broker(self.auth,self.provider);self.auth.resume(PW)
    def tearDown(self):self.auth.close();self.provider.close();self.tmp.cleanup()
    def grant(self,p,b=None,ttl=600):return self.auth.grant(p,(b or self.b).prepare(p)[0],PW,now=NOW,ttl_seconds=ttl)
    def google(self,store=None,**kw):
        store=store or MockGoogle()
        g=GoogleCalendar(lambda:'unused',['allowed'],store,account_id=kw.get('account_id','synthetic-google-sub'),connection_id=kw.get('connection_id','fixture-a'))
        return g,store
    def test_F01_expiry_during_preparation_blocks_before_intent(self):
        p=proposal();t=self.grant(p,ttl=1);clock={'now':NOW};original=self.b.prepare
        def slow(p):
            value=original(p);clock['now']=NOW+timedelta(seconds=2);return value
        self.b.prepare=slow
        with patch('jarvis.calendar.now_utc',side_effect=lambda:clock['now']):
            with self.assertRaises(Refused):self.b.execute(p,t)
        self.assertIsNone(self.provider.get(p['target'],p['event_id']))
        self.assertEqual(self.auth.report()['intents'],[])
    def test_F01_positive_preparation_within_validity_succeeds(self):
        p=proposal();t=self.grant(p)
        with patch('jarvis.calendar.now_utc',return_value=NOW):r=self.b.execute(p,t)
        self.assertEqual(r['status'],'PROVIDER_VERIFIED')
    def test_F01_expiry_during_provider_preflight_blocks_patch(self):
        g,store=self.google();b=Broker(self.auth,g,live_enabled=True,startup=False)
        p=proposal('allowed');b.execute(p,self.grant(p,b),NOW)
        u=make_proposal('allowed',dict(p['payload'],summary='New'),'u',event_id=p['event_id'],expected_version='"1"')
        t=self.grant(u,b,ttl=1);clock={'now':NOW}
        store.clock_hook=lambda:clock.update(now=NOW+timedelta(seconds=2))
        with patch('jarvis.calendar.now_utc',side_effect=lambda:clock['now']):
            with self.assertRaises(Refused):b.execute(u,t)
        self.assertEqual(len(store.writes()),1)
        self.assertEqual(store.events[p['event_id']]['summary'],'Synthetic canary')
        self.assertFalse(any(x['opkey']=='u' for x in self.auth.report()['intents']))
    def test_F01_expiry_while_authority_lock_waits_rechecked_inside_transaction(self):
        p=proposal();ctx=self.b.prepare(p)[0];t=self.grant(p,ttl=1);clock={'now':NOW}
        from jarvis.common import transaction as original
        @contextmanager
        def delayed(db):
            with original(db):
                clock['now']=NOW+timedelta(seconds=2);yield
        with patch('jarvis.authority.transaction',delayed):
            with self.assertRaises(Refused):self.auth.reserve(t,p,ctx,lambda:clock['now'])
        self.assertEqual(self.auth.report()['intents'],[])
    def test_F01_backward_wall_clock_does_not_extend_permit(self):
        p=proposal();t=self.grant(p,ttl=1);clock={'now':NOW,'mono':100.};original=self.b.prepare
        def slow(p):
            value=original(p);clock.update(now=NOW-timedelta(hours=1),mono=102.);return value
        self.b.prepare=slow
        with patch('jarvis.calendar.now_utc',side_effect=lambda:clock['now']),patch('jarvis.calendar.monotime.monotonic',side_effect=lambda:clock['mono']):
            with self.assertRaises(Refused):self.b.execute(p,t)
        self.assertEqual(self.auth.report()['intents'],[])
    def test_F01_revoked_during_provider_preflight_refuses(self):
        p=proposal();t=self.grant(p);original=self.provider.apply
        def revoke(x,*,before_submit=None):self.auth.pause();return original(x,before_submit=before_submit)
        self.provider.apply=revoke
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
        self.assertIsNone(self.provider.get(p['target'],p['event_id']))
    def test_F01_live_call_cannot_supply_historical_time(self):
        g=GoogleCalendar(lambda:'unused',['allowed'],account_id='sub')
        b=Broker(self.auth,g,live_enabled=True,startup=False)
        with self.assertRaises(Refused):b.execute(proposal('allowed'),{},NOW)
    def test_F02_google_unknown_not_verifiable_by_simulator(self):
        g,store=self.google();store.after_commit=True;b=Broker(self.auth,g,live_enabled=True,startup=False)
        p=proposal('allowed');self.assertEqual(b.execute(p,self.grant(p,b),NOW)['status'],'UNKNOWN_EXTERNAL')
        self.provider.db.execute('INSERT INTO events VALUES(?,?,1,?)',(p['target'],p['event_id'],canonical(p['payload'])))
        b.adapter=self.provider
        with self.assertRaises(Refused):b.reconcile(p['operation_key'])
        self.assertEqual(self.auth.intent(p['operation_key'])['status'],'UNKNOWN_EXTERNAL')
    def test_F02_same_provider_different_account_blocked(self):
        g,store=self.google();store.after_commit=True;b=Broker(self.auth,g,live_enabled=True,startup=False)
        p=proposal('allowed');b.execute(p,self.grant(p,b),NOW)
        other,_=self.google(store,account_id='another-account');b.adapter=other
        before=len(store.calls)
        with self.assertRaises(Refused):b.reconcile(p['operation_key'])
        self.assertEqual(len(store.calls),before)
    def test_F02_same_account_different_connection_blocked(self):
        g,store=self.google();store.after_commit=True;b=Broker(self.auth,g,live_enabled=True,startup=False)
        p=proposal('allowed');b.execute(p,self.grant(p,b),NOW)
        other,_=self.google(store,connection_id='unrelated-fixture');b.adapter=other
        with self.assertRaises(Refused):b.reconcile(p['operation_key'])
    def test_F02_mock_cannot_be_promoted_to_live_for_recovery(self):
        g,store=self.google();store.after_commit=True;b=Broker(self.auth,g,live_enabled=True,startup=False)
        p=proposal('allowed');b.execute(p,self.grant(p,b),NOW)
        g.transport=None
        with self.assertRaises(Refused):b.reconcile(p['operation_key'])
    def test_F02_separate_simulator_database_is_not_same_provider(self):
        p=proposal();self.provider.fault='after';self.b.execute(p,self.grant(p),NOW)
        other=SimCalendar(self.root/'different')
        try:
            other.db.execute('INSERT INTO events VALUES(?,?,1,?)',(p['target'],p['event_id'],canonical(p['payload'])))
            self.b.adapter=other
            with self.assertRaises(Refused):self.b.reconcile(p['operation_key'])
        finally:other.close()
    def test_F02_same_original_provider_recovers_without_resubmit(self):
        g,store=self.google();store.after_commit=True;b=Broker(self.auth,g,live_enabled=True,startup=False)
        p=proposal('allowed');b.execute(p,self.grant(p,b),NOW)
        recreated,_=self.google(store);b.adapter=recreated
        r=b.reconcile(p['operation_key']);self.assertEqual(r['status'],'PROVIDER_VERIFIED')
        self.assertEqual(len(store.writes()),1)
        self.assertEqual(r['receipt']['provider_binding']['account_id'],'synthetic-google-sub')
        self.assertEqual(r['receipt']['target'],'allowed')
        self.assertFalse(r['receipt']['obligation_completed'])
    def test_F02_simulator_identity_survives_reopen(self):
        p=proposal();self.provider.fault='after';self.b.execute(p,self.grant(p),NOW)
        reopened=SimCalendar(self.root/'provider')
        try:self.b.adapter=reopened;self.assertEqual(self.b.reconcile(p['operation_key'])['status'],'PROVIDER_VERIFIED')
        finally:reopened.close()
    def test_F02_legacy_unbound_intent_remains_quarantined(self):
        p=proposal();self.provider.fault='after';self.b.execute(p,self.grant(p),NOW)
        self.auth.db.execute('UPDATE intents SET provider_binding=NULL')
        with self.assertRaises(Refused):self.b.reconcile(p['operation_key'])
        self.assertEqual(self.auth.intent(p['operation_key'])['status'],'UNKNOWN_EXTERNAL')
    def test_F02_terminal_receipt_still_requires_original_binding(self):
        p=proposal();self.b.execute(p,self.grant(p),NOW)
        other=SimCalendar(self.root/'elsewhere')
        try:
            self.b.adapter=other
            with self.assertRaises(Refused):self.b.reconcile(p['operation_key'])
        finally:other.close()
    def test_F02_account_changes_at_final_dispatch_blocks(self):
        g,store=self.google();b=Broker(self.auth,g,live_enabled=True,startup=False);p=proposal('allowed');t=self.grant(p,b)
        original=g.apply
        def changed(x,*,before_submit=None):g.account_id='another';return original(x,before_submit=before_submit)
        g.apply=changed
        with self.assertRaises(Refused):b.execute(p,t,NOW)
        self.assertEqual(len(store.writes()),0)
    def test_F04_title_edit_preserves_existing_reminders_and_metadata(self):
        g,store=self.google();p=proposal('allowed');g.apply(p)
        store.events[p['event_id']].update(reminders={'useDefault':False,'overrides':[{'method':'popup','minutes':30}]},description='Keep this',visibility='private')
        prior=copy.deepcopy(store.events[p['event_id']])
        u=make_proposal('allowed',dict(p['payload'],summary='Approved new title'),'update',event_id=p['event_id'],expected_version='"1"')
        g.apply(u);wire=store.writes()[-1]
        self.assertEqual(set(wire[2]),set(u['payload']))
        for k in ['reminders','description','visibility','extendedProperties']:self.assertEqual(store.events[p['event_id']][k],prior[k])
        self.assertEqual(wire[3]['If-Match'],'"1"')
    def test_F04_default_reminders_preserved(self):
        g,store=self.google();p=proposal('allowed');g.apply(p);store.events[p['event_id']]['reminders']={'useDefault':True}
        u=make_proposal('allowed',p['payload'],'u',event_id=p['event_id'],expected_version='"1"');g.apply(u)
        self.assertEqual(store.events[p['event_id']]['reminders'],{'useDefault':True})
    def test_F04_explicit_reminder_change_not_silently_allowed(self):
        p=proposal();p['payload']['reminders']={'useDefault':False}
        with self.assertRaises(Refused):self.b.prepare(p)
    def test_F04_create_keeps_disclosed_private_no_reminder_defaults(self):
        g,store=self.google();p=proposal('allowed');g.apply(p)
        self.assertEqual(store.events[p['event_id']]['reminders'],{'useDefault':False,'overrides':[]})
        self.assertEqual(store.events[p['event_id']]['visibility'],'private')
    def test_F04_readback_verifies_partial_update_without_erasing_description(self):
        g,store=self.google();b=Broker(self.auth,g,live_enabled=True,startup=False);p=proposal('allowed');b.execute(p,self.grant(p,b),NOW)
        store.events[p['event_id']]['description']='Unchanged private note'
        u=make_proposal('allowed',dict(p['payload'],summary='Renamed'),'u',event_id=p['event_id'],expected_version='"1"')
        self.assertEqual(b.execute(u,self.grant(u,b),NOW)['status'],'PROVIDER_VERIFIED')
        self.assertEqual(store.events[p['event_id']]['description'],'Unchanged private note')

class CredentialBoundaryTests(unittest.TestCase):
    class Response:
        status=200
        def __init__(self,body):self.body=canonical(body).encode()
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,*a):return self.body
    def test_F02_real_http_path_checks_current_token_subject_before_write(self):
        calls=[]
        def open_(req,timeout):calls.append(req.full_url);return self.Response({'sub':'WRONG'})
        g=GoogleCalendar(lambda:'synthetic-token-never-sent',['allowed'],account_id='expected')
        g.opener=type('Opener',(),{'open':staticmethod(open_)})();guard=[]
        with self.assertRaises(Refused):g.apply(proposal('allowed'),before_submit=lambda:guard.append(True))
        self.assertEqual(guard,[]);self.assertEqual(calls,['https://openidconnect.googleapis.com/v1/userinfo'])
    def test_F01_token_delay_checked_after_identity_before_socket_write(self):
        with tempfile.TemporaryDirectory() as d:
            a=Authority(d);a.initialize(PW);clock={'now':NOW};late={'armed':False};calls=[]
            def token():
                if late['armed']:clock['now']=NOW+timedelta(seconds=2)
                return 'synthetic-never-sent'
            def open_(req,timeout):
                calls.append(req.full_url)
                if 'userinfo' in req.full_url:return self.Response({'sub':'expected'})
                if '/acl' in req.full_url:return self.Response({'items':[{'role':'owner','scope':{'type':'user','value':'a@example.invalid'}}]})
                raise AssertionError('No external write should reach the socket')
            g=GoogleCalendar(token,['allowed'],account_id='expected');g.opener=type('Opener',(),{'open':staticmethod(open_)})();b=Broker(a,g,live_enabled=True);a.resume(PW)
            p=proposal('allowed');t=a.grant(p,b.prepare(p)[0],PW,now=NOW,ttl_seconds=1);original=g.apply
            def apply(x,*,before_submit=None):late['armed']=True;return original(x,before_submit=before_submit)
            g.apply=apply
            with patch('jarvis.calendar.now_utc',side_effect=lambda:clock['now']):
                with self.assertRaises(Refused):b.execute(p,t)
            self.assertEqual(a.report()['intents'],[]);self.assertFalse(any('/events' in x for x in calls));a.close()

class OfflineContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.h=Household(self.tmp.name)
        self.h.configure_routine(routine(),NOW);self.row=self.h.tick(NOW)['occurrences'][0]
    def tearDown(self):self.h.close();self.tmp.cleanup()
    def event(self,row=None,when=NOW,variant='minimum'):
        row=row or self.row
        return {'version':1,'occurred_at':iso(when),'household_instance':self.h.snapshot(NOW)['instance_id'],'source':'user_report',
                'definition_version':row['definition_version'],'timezone':row['timezone'],'completion_variant':variant,'observed_user_revision':row.get('user_revision',0)}
    def c(self,op='done',row=None,when=NOW,variant='minimum',**kw):
        row=row or self.row
        return dict({'command_id':str(uuid.uuid4()),'op':op,'object_id':row['id'],'expected_revision':row['revision'],'client_event':self.event(row,when,variant)},**kw)
    def test_F03_original_day_minimum_survives_reconnection_and_window_expiry(self):
        c=self.c();received=NOW+timedelta(days=1);self.h.tick(received);self.h.command(c,received)
        done=self.h._get('occurrences',self.row['id'])
        self.assertEqual(done['completed_at'],iso(NOW));self.assertEqual(done['completion_received_at'],iso(received));self.assertEqual(done['completion_version'],'minimum')
        self.assertEqual(done['basis'],'user_reported');self.assertEqual(self.h.snapshot(received)['mode'],'normal')
        other=[x for x in self.h.snapshot(received)['occurrences'] if x['id']!=self.row['id']][0];self.assertEqual(other['status'],'OPEN')
    def test_F03_completion_anchored_next_due_uses_reported_not_receipt_time(self):
        self.h.configure_routine(routine(id='interval',anchor='completion',first_due=iso(NOW),interval=24,interval_semantics='elapsed_hours'),NOW)
        r=next(x for x in self.h.tick(NOW)['occurrences'] if x['routine_id']=='interval');c=self.c(row=r)
        received=NOW+timedelta(days=2);self.h.command(c,received);s=self.h.tick(received)
        child=next(x for x in s['occurrences'] if x['routine_id']=='interval' and x['id']!=r['id'])
        self.assertEqual(instant(child['due']),NOW+timedelta(hours=24))
    def test_F03_full_variant_does_not_become_todays_minimum(self):
        c=self.c(variant='full');later=NOW+timedelta(days=1);self.h.command({'command_id':'min-now','op':'simplify'},later)
        self.h.command(c,later);self.assertEqual(self.h._get('occurrences',self.row['id'])['completion_version'],'full')
    def test_F03_outbox_replay_is_exactly_once(self):
        c=self.c();a=self.h.command(c,NOW+timedelta(days=1));b=self.h.command(c,NOW+timedelta(days=2));self.assertEqual(a,b)
        self.assertEqual(self.h._get('occurrences',self.row['id'])['user_revision'],1)
    def test_F03_changed_payload_same_id_refused(self):
        c=self.c();self.h.command(c,NOW);changed=copy.deepcopy(c);changed['client_event']['completion_variant']='full'
        with self.assertRaises(Conflict):self.h.command(changed,NOW)
    def test_F03_auto_nudge_revision_can_rebase_but_not_change_report(self):
        c=self.c();self.h.remind(self.row['id'],NOW);self.h.command(c,NOW+timedelta(minutes=2))
        self.assertEqual(self.h._get('occurrences',self.row['id'])['completed_at'],iso(NOW))
    def test_F03_concurrent_human_edit_blocks_stale_completion(self):
        c=self.c();self.h.command({'command_id':'other','op':'snooze','object_id':self.row['id'],'expected_revision':0,'minutes':15},NOW)
        with self.assertRaises(Conflict):self.h.command(c,NOW+timedelta(days=1))
    def test_F03_future_clock_is_not_silently_rewritten(self):
        with self.assertRaises(Conflict):self.h.command(self.c(when=NOW+timedelta(hours=2)),NOW)
    def test_F03_naive_client_time_refused(self):
        c=self.c();c['client_event']['occurred_at']='2026-09-24T13:00:00'
        with self.assertRaises(Refused):self.h.command(c,NOW)
    def test_F03_completion_before_occurrence_due_refused(self):
        with self.assertRaises(Refused):self.h.command(self.c(when=NOW-timedelta(days=1)),NOW)
    def test_F03_missing_displayed_variant_refused(self):
        c=self.c();del c['client_event']['completion_variant']
        with self.assertRaises(Refused):self.h.command(c,NOW)
    def test_F03_wrong_household_outbox_refused(self):
        c=self.c();c['client_event']['household_instance']='another-instance'
        with self.assertRaises(Conflict):self.h.command(c,NOW)
    def test_F03_wrong_definition_refused(self):
        c=self.c();c['client_event']['definition_version']=2
        with self.assertRaises(Conflict):self.h.command(c,NOW)
    def test_F03_wrong_timezone_refused(self):
        c=self.c();c['client_event']['timezone']='UTC'
        with self.assertRaises(Conflict):self.h.command(c,NOW)
    def test_F03_redefined_routine_does_not_reinterpret_queued_done(self):
        c=self.c();self.h.configure_routine(routine(version=2,title='New definition'),NOW)
        with self.assertRaises(Conflict):self.h.command(c,NOW+timedelta(minutes=1))
    def test_F03_delayed_mode_change_applies_original_day_only(self):
        ev={k:v for k,v in self.event().items() if k in {'version','occurred_at','household_instance','source'}}
        self.h.command({'command_id':'old-min','op':'simplify','timezone':'America/Chicago','client_event':ev},NOW+timedelta(days=1))
        self.assertEqual(self.h.snapshot(NOW)['mode'],'minimum');self.assertEqual(self.h.snapshot(NOW+timedelta(days=1))['mode'],'normal')
    def test_F03_delayed_snooze_does_not_create_new_fifteen_minute_delay(self):
        c=self.c(op='snooze',minutes=15);self.h.tick(NOW+timedelta(days=1));r=self.h.command(c,NOW+timedelta(days=1))
        self.assertTrue(r['snooze_elapsed_at_reconnection']);b=self.h._get('occurrences',self.row['id'])
        self.assertEqual(instant(b['next_nudge']),NOW+timedelta(minutes=15));self.assertEqual(b['status'],'UNKNOWN')
    def test_F03_capture_keeps_reported_and_received_times_separate(self):
        ev={k:v for k,v in self.event().items() if k in {'version','occurred_at','household_instance','source'}}
        c={'command_id':'thought','op':'capture','text':'Private thought','client_event':ev};self.h.command(c,NOW+timedelta(days=1))
        b=self.h.snapshot(NOW)['captures'][0];self.assertEqual(b['at'],iso(NOW));self.assertEqual(b['received_at'],iso(NOW+timedelta(days=1)))
    def test_F03_offline_report_survives_database_reopen(self):
        c=self.c();self.h.command(c,NOW+timedelta(days=1));self.h.close();self.h=Household(self.tmp.name)
        self.assertEqual(self.h._get('occurrences',self.row['id'])['completion_version'],'minimum')
        self.assertEqual(self.h._get('occurrences',self.row['id'])['completed_at'],iso(NOW))
    def test_F03_undo_offline_completion_is_available(self):
        self.h.command(self.c(),NOW+timedelta(days=1));r=self.h._get('occurrences',self.row['id'])
        self.h.command(self.c('undo',row=r,when=NOW+timedelta(days=1)),NOW+timedelta(days=1))
        b=self.h._get('occurrences',r['id']);self.assertEqual(b['status'],'UNKNOWN');self.assertIsNone(b['completed_at'])
    def test_F03_snapshot_gives_displayed_steps_for_occurrences_original_day(self):
        self.h.command({'command_id':'min','op':'simplify'},NOW);s=self.h.tick(NOW+timedelta(days=1))
        old=next(x for x in s['occurrences'] if x['id']==self.row['id']);self.assertEqual(old['display_variant'],'minimum')
        self.assertEqual(s['mode'],'normal')
    def test_F03_self_report_cannot_mint_provider_authority(self):
        c=self.c();c['client_event']['approved_by']='sovereign'
        with self.assertRaises(Refused):self.h.command(c,NOW)
