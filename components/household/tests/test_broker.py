import copy,json,random,sqlite3,tempfile,unittest,uuid
from datetime import timedelta
from pathlib import Path
from jarvis.common import *
from jarvis.authority import Authority
from jarvis.calendar import Broker,SimCalendar,make_proposal
from jarvis.household import Household
from jarvis.migration import backup_household,restore_household
NOW=instant('2026-09-24T13:00:00Z')
PW='synthetic-test-passphrase-only'

def proposal(target='private-demo',key=None):
    return make_proposal(target,{'summary':'Private test','start':'2026-09-25T13:00:00Z','end':'2026-09-25T14:00:00Z'},key or str(uuid.uuid4()))

class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.a=Authority(self.root/'authority');self.a.initialize(PW)
        self.provider=SimCalendar(self.root/'provider');self.b=Broker(self.a,self.provider);self.a.resume(PW)
    def tearDown(self):self.a.close();self.provider.close();self.tmp.cleanup()
    def token(self,p,**kw):return self.a.grant(p,self.b.prepare(p)[0],PW,now=NOW,**kw)
    def test_I01_positive_exact_calendar_action(self):
        p=proposal();result=self.b.execute(p,self.token(p),NOW);self.assertEqual(result['status'],'PROVIDER_VERIFIED');self.assertFalse(result['receipt']['obligation_completed'])
    def test_P01_shared_target_private_label_refused(self):
        p=proposal('shared-demo');p['privacy']='private'
        with self.assertRaises(Refused):self.b.prepare(p)
    def test_P01_shared_target_no_scope_refused(self):
        p=proposal('shared-demo');t=self.token(p)
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
        self.assertIsNone(self.provider.get(p['target'],p['event_id']))
    def test_P02_attachment_blocked(self):
        p=proposal();p['payload']['attachments']=['sensitive-file']
        with self.assertRaises(Refused):self.b.prepare(p)
    def test_P02_shared_description_blocked_even_if_selected(self):
        p=proposal('shared-demo');p['payload']['description']='private source'
        c,a=self.b.prepare(p);s={'target':p['target'],'audience_hash':digest(a),'fields':list(p['payload']),'purpose':'test'}
        with self.assertRaises(Refused):self.b.execute(p,self.token(p,sharing=s),NOW)
    def test_P03_explicit_minimal_sharing_succeeds(self):
        p=proposal('shared-demo');c,a=self.b.prepare(p);s={'target':p['target'],'audience_hash':digest(a),'fields':list(p['payload']),'purpose':'User chose this test item'}
        self.assertEqual(self.b.execute(p,self.token(p,sharing=s),NOW)['status'],'PROVIDER_VERIFIED')
    def test_A01_forged_approval_rejected(self):
        p=proposal();t=self.token(p);t['body']['principal']='sovereign'
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
    def test_A01_fake_receipt_has_no_broker_entrypoint(self):
        self.assertFalse(hasattr(self.b,'accept_receipt'));p=proposal();p['provider_receipt']={'verified':True}
        with self.assertRaises(Refused):self.b.prepare(p)
    def test_A01_wrong_operator_password(self):
        with self.assertRaises(Refused):self.a.grant(proposal(),{},'not-the-password',now=NOW)
    def test_A02_revoke_before_dispatch_blocks(self):
        p=proposal();t=self.token(p);self.a.pause()
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
        self.assertIsNone(self.provider.get(p['target'],p['event_id']))
    def test_A03_revoke_after_dispatch_does_not_claim_undo(self):
        p=proposal();t=self.token(p);original=self.provider.apply
        def revoke_then_apply(x,*,before_submit=None):
            def at_dispatch():
                before_submit();self.a.pause()
            return original(x,before_submit=at_dispatch)
        self.provider.apply=revoke_then_apply
        self.assertEqual(self.b.execute(p,t,NOW)['status'],'PROVIDER_VERIFIED');self.assertTrue(self.a.report()['paused'])
    def test_A04_restart_invalidates_old_permit(self):
        p=proposal();t=self.token(p);self.b=Broker(self.a,self.provider);self.a.resume(PW)
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
    def test_A04_supported_restore_pauses(self):
        h=Household(self.root/'house');backup_household(h,self.root/'snapshot.db');h.close()
        p=proposal();t=self.token(p);restore_household(self.root/'snapshot.db',self.root/'restored',self.a)
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
        self.assertTrue(self.a.report()['paused'])
    def test_A05_restore_cannot_erase_external_intent(self):
        h=Household(self.root/'house');backup_household(h,self.root/'snapshot.db');h.close()
        p=proposal();self.provider.fault='after';self.assertEqual(self.b.execute(p,self.token(p),NOW)['status'],'UNKNOWN_EXTERNAL')
        restore_household(self.root/'snapshot.db',self.root/'restored',self.a)
        with self.assertRaises(Refused):self.a.resume(PW)
        self.assertEqual(self.b.reconcile(p['operation_key'])['status'],'PROVIDER_VERIFIED')
        self.a.resume(PW);new=self.token(p)
        with self.assertRaises(Refused):self.b.execute(p,new,NOW)
        self.assertEqual(self.provider.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
    def test_A06_risk_field_cannot_downgrade_policy(self):
        p=proposal();p['risk']='safe'
        with self.assertRaises(Refused):self.b.prepare(p)
    def test_I02_update_version_race(self):
        p=proposal();self.b.execute(p,self.token(p),NOW)
        update=make_proposal(p['target'],dict(p['payload'],summary='Desired'),str(uuid.uuid4()),event_id=p['event_id'],expected_version='1')
        t=self.token(update);self.provider.db.execute('UPDATE events SET version=2')
        self.assertEqual(self.b.execute(update,t,NOW)['status'],'REJECTED_NO_EFFECT')
        self.assertEqual(self.provider.get(p['target'],p['event_id'])['payload']['summary'],'Private test')
    def test_update_positive_path(self):
        p=proposal();self.b.execute(p,self.token(p),NOW)
        u=make_proposal(p['target'],dict(p['payload'],summary='Changed'),str(uuid.uuid4()),event_id=p['event_id'],expected_version='1')
        self.assertEqual(self.b.execute(u,self.token(u),NOW)['status'],'PROVIDER_VERIFIED')
    def test_I03_timeout_after_commit_no_retry(self):
        p=proposal();t=self.token(p);self.provider.fault='after';self.assertEqual(self.b.execute(p,t,NOW)['status'],'UNKNOWN_EXTERNAL')
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
        self.assertEqual(self.provider.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
    def test_U04_recovery_to_useful_work(self):
        p=proposal();self.provider.fault='after';self.b.execute(p,self.token(p),NOW);self.b=Broker(self.a,self.provider)
        self.b.reconcile(p['operation_key']);self.a.resume(PW);self.provider.fault=None;q=proposal()
        self.assertEqual(self.b.execute(q,self.token(q),NOW)['status'],'PROVIDER_VERIFIED')
    def test_mismatched_readback_not_verified(self):
        p=proposal();self.provider.fault='mismatch';self.assertEqual(self.b.execute(p,self.token(p),NOW)['status'],'UNKNOWN_EXTERNAL')
    def test_missing_readback_does_not_authorize_resubmit(self):
        p=proposal();t=self.token(p);self.a.reserve(t,p,self.b.prepare(p)[0],NOW)
        self.assertEqual(self.b.reconcile(p['operation_key'])['status'],'UNKNOWN_EXTERNAL')
        with self.assertRaises(Refused):self.b.execute(p,self.token(p),NOW)
    def test_second_target_operation_blocked_while_unknown(self):
        p=proposal();self.provider.fault='after';self.b.execute(p,self.token(p),NOW);q=proposal()
        with self.assertRaises(Refused):self.b.execute(q,self.token(q),NOW)
    def test_mutated_payload_refused(self):
        p=proposal();t=self.token(p);p['payload']['summary']='Different'
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
    def test_changed_audience_invalidates_approval(self):
        p=proposal();t=self.token(p);self.provider.db.execute('UPDATE audience SET body=? WHERE target=?',(canonical({'owner':'self@example.invalid','viewers':['self@example.invalid','intruder@example.invalid']}),'private-demo'))
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)
    def test_expired_approval_refused(self):
        p=proposal();t=self.token(p,ttl_seconds=1)
        with self.assertRaises(Refused):self.b.execute(p,t,NOW+timedelta(seconds=2))
    def test_future_approval_refused(self):
        p=proposal();t=self.token(p)
        with self.assertRaises(Refused):self.b.execute(p,t,NOW-timedelta(seconds=1))
    def test_missing_capability_is_not_assumed(self):
        self.provider.controls=dict(self.provider.controls,conditional_update=False)
        with self.assertRaises(Refused):self.b.prepare(proposal())
    def test_live_disabled_by_default(self):
        self.provider.live=True
        with self.assertRaises(Refused):self.b.prepare(proposal())
        self.provider.live=False
    def test_create_id_is_stable(self):
        p=proposal(key='same');q=proposal(key='same');self.assertEqual(p['event_id'],q['event_id'])
    def test_money_action_impossible(self):
        p=proposal();p['operation']='bill_pay'
        with self.assertRaises(Refused):self.b.prepare(p)
    def test_bulk_recurrence_refused(self):
        p=proposal();p['payload']['recurrence']=['RRULE:FREQ=DAILY']
        with self.assertRaises(Refused):self.b.prepare(p)
    def test_1000_payload_mutations(self):
        p=proposal();t=self.token(p);rng=random.Random(314159)
        for i in range(1000):
            changed=copy.deepcopy(p);field=rng.choice(['summary','start','end']);changed['payload'][field]=str(i)+str(rng.random()) if field=='summary' else ('2026-09-25T15:00:00Z' if field=='end' else '2026-09-25T12:00:00Z')
            with self.assertRaises(Refused):self.b.execute(changed,t,NOW)
        self.assertEqual(self.provider.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
    def test_local_second_connection_cannot_reserve_same_operation(self):
        p=proposal();t=self.token(p);context=self.b.prepare(p)[0];self.a.reserve(t,p,context,NOW)
        second=Authority(self.root/'authority')
        try:
            with self.assertRaises(Refused):second.reserve(t,p,context,NOW)
        finally:second.close()
    def test_raw_application_rollback_cannot_replay_grant(self):
        # Intent/consumption lives in the separate authority store, not application DB.
        h=Household(self.root/'app');backup_household(h,self.root/'old.db');h.close()
        p=proposal();t=self.token(p);self.b.execute(p,t,NOW)
        import shutil
        shutil.copy2(self.root/'old.db',self.root/'app'/'household.sqlite3')
        with self.assertRaises(Refused):self.b.execute(p,t,NOW)

    def test_simultaneous_local_writers_one_effect(self):
        import threading
        p=proposal();t=self.token(p);barrier=threading.Barrier(2);results=[]
        def worker():
            a=Authority(self.root/'authority');provider=SimCalendar(self.root/'provider');b=Broker(a,provider,startup=False)
            try:
                barrier.wait()
                try:results.append(b.execute(p,t,NOW)['status'])
                except Refused:results.append('REFUSED')
            finally:a.close();provider.close()
        threads=[threading.Thread(target=worker) for _ in range(2)]
        for th in threads:th.start()
        for th in threads:th.join(timeout=5)
        self.assertEqual(sorted(results),['PROVIDER_VERIFIED','REFUSED']);self.assertEqual(self.provider.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
    def test_restart_generation_never_reuses_old_approval(self):
        p=proposal();t=self.token(p);old=t['body']['generation'];self.a.restart_boundary();self.assertNotEqual(old,self.a._cfg('generation'))
