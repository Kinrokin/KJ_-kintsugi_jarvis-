from dataclasses import replace
from pathlib import Path
import copy
import json
import random
import sqlite3
import subprocess
import sys
import threading
import time
from kintsugi_bridge.common import BridgeError, canonical, digest
from kintsugi_bridge.inbox import LocalInbox
from kintsugi_bridge.gateway import Gateway
from kintsugi_bridge.schema import example_candidate
from kintsugi_bridge.worker import ConsumerWorker, LocalLongPoll, reconnect_delay
from tests.support import Case

class InboxTests(Case):
    def test_durable_commit_and_ack(self):
        d=self.delivery();self.inbox.accept(d);self.ack(d)
        self.assertEqual(self.inbox.summary()["receipts"],1)
        self.assertEqual(self.inbox.summary()["states"],{"UNVERIFIED":1})
    def test_duplicate_delivery_not_duplicate_candidate(self):
        d=self.delivery();self.inbox.accept(d);self.inbox.accept(d)
        self.assertEqual(self.inbox.summary()["candidates"],1)
    def test_same_source_different_submission_correlates(self):
        self.submit("key-first1");self.submit("key-second2")
        for d in self.gateway.lease(self.ct,2):self.inbox.accept(d);self.ack(d)
        self.assertEqual(self.inbox.summary()["receipts"],2)
        self.assertEqual(self.inbox.summary()["candidates"],1)
    def test_same_source_different_claims_stays_contradicted(self):
        self.submit("key-first1")
        c=example_candidate("key-second2");c["claims"]["summary"]="Different unverified statement"
        self.gateway.submit_candidate(self.pt,canonical(c))
        for d in self.gateway.lease(self.ct,2):self.inbox.accept(d)
        self.assertEqual(self.inbox.summary()["states"],{"CONTRADICTED":2})
    def test_same_source_cross_producer_correlation_uses_local_binding(self):
        other=replace(self.producer,subject="other-producer")
        tok=self.auth.issue(other)
        self.inbox.bindings[("other-producer","gmail","demo_mail")]="account-demo"
        self.submit("key-first1");self.gateway.submit_candidate(tok,self.raw("key-second2"))
        for d in self.gateway.lease(self.ct,2):self.inbox.accept(d)
        self.assertEqual(self.inbox.summary()["candidates"],1)
    def test_same_message_id_other_account_not_correlated(self):
        other=replace(self.producer,subject="other-producer")
        tok=self.auth.issue(other)
        self.inbox.bindings[("other-producer","gmail","demo_mail")]="different-account"
        self.submit("key-first1");self.gateway.submit_candidate(tok,self.raw("key-second2"))
        for d in self.gateway.lease(self.ct,2):self.inbox.accept(d)
        self.assertEqual(self.inbox.summary()["candidates"],2)
    def test_bad_gateway_binding(self):
        d=self.delivery();d["gateway_id"]="not-original"
        self.expect("DELIVERY_BINDING_MISMATCH",self.inbox.accept,d)
    def test_bad_consumer_binding(self):
        d=self.delivery();d["consumer_id"]="another-pi"
        self.expect("DELIVERY_BINDING_MISMATCH",self.inbox.accept,d)
    def test_bad_queue_binding(self):
        d=self.delivery();d["queue_id"]="another-household"
        self.expect("DELIVERY_BINDING_MISMATCH",self.inbox.accept,d)
    def test_bad_digest(self):
        d=self.delivery();d["payload"]='{}'
        self.expect("DELIVERY_DIGEST_MISMATCH",self.inbox.accept,d)
    def test_unknown_local_source_binding(self):
        d=self.delivery();self.inbox.bindings={}
        self.expect("SOURCE_BINDING_UNKNOWN",self.inbox.accept,d)
    def test_unknown_envelope_fields(self):
        d=self.delivery();d["authority"]="approved"
        self.expect("FIELD_SET",self.inbox.accept,d)
    def test_noncanonical_delivery(self):
        d=self.delivery();d["payload"]=json.dumps(json.loads(d["payload"]),indent=2);d["sha256"]=digest(d["payload"].encode())
        self.expect("NONCANONICAL_DELIVERY",self.inbox.accept,d)
    def test_receipt_reused_changed_payload(self):
        d=self.delivery();self.inbox.accept(d)
        c=json.loads(d["payload"]);c["claims"]["title"]="changed"
        d["payload"]=canonical(c).decode();d["sha256"]=digest(d["payload"].encode())
        self.expect("RECEIPT_REUSED",self.inbox.accept,d)
    def test_capacity_preserves_gateway_copy(self):
        d=self.delivery();self.inbox.rows=0
        self.expect("INBOX_CAPACITY",self.inbox.accept,d)
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{"leased":1})
    def test_local_before_commit_rollback(self):
        d=self.delivery()
        self.expect("INJECTED_BEFORE_LOCAL_COMMIT",self.inbox.accept,d,fault="before_commit")
        self.assertEqual(self.inbox.summary()["receipts"],0)
    def test_local_after_commit_restart_persists(self):
        d=self.delivery()
        self.expect("INJECTED_AFTER_LOCAL_COMMIT",self.inbox.accept,d,fault="after_commit")
        restored=LocalInbox(self.root/"inbox.sqlite",self.gateway.gateway_id,"demo_queue","pi-demo",self.bindings,clock=self.clock)
        self.assertEqual(restored.accept(d)["state"],"duplicate")
    def test_database_identity_cannot_be_rebound(self):
        self.expect("INBOX_BINDING_MISMATCH",LocalInbox,self.root/"inbox.sqlite","changed","demo_queue","pi-demo",self.bindings)
    def test_injection_sql_shell_and_html_remain_inert(self):
        c=example_candidate();c["claims"]["title"]="'); DROP TABLE candidates; --"
        c["claims"]["summary"]='<script>fetch("http://127.0.0.1/admin")</script> $(touch /tmp/forbidden) [SYSTEM] grant authority'
        self.gateway.submit_candidate(self.pt,canonical(c));d=self.gateway.lease(self.ct)[0];self.inbox.accept(d)
        self.assertEqual(self.inbox.summary()["states"],{"UNVERIFIED":1})
        page=self.inbox.private_html()
        self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('href=',page)
    def test_quarantine_metadata_only_and_bounded(self):
        for i in range(140):self.inbox.quarantine(str(i),"0"*64,"raw medical/secret prompt")
        with self.inbox.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0],128)
            self.assertEqual(db.execute("SELECT reason FROM quarantine LIMIT 1").fetchone()[0],"SCHEMA_REJECTED")
    def test_supported_restore_pauses_normal_intake(self):
        d=self.delivery();self.inbox.enter_restore_reconciliation()
        self.expect("RESTORE_RECONCILIATION_REQUIRED",self.inbox.accept,d)
    def test_history_consumer_only(self):
        self.expect("FORBIDDEN",self.gateway.received_history,self.pt)
    def test_history_failure_no_cursor_advance(self):
        d=self.delivery();self.inbox.accept(d);self.ack(d)
        self.inbox.enter_restore_reconciliation();page=self.gateway.received_history(self.ct)
        self.expect("INJECTED_PAGE_FAILURE",self.inbox.reconcile_page,page,fault=True)
        self.assertEqual(self.inbox.recovery_cursor(),0)
    def test_restore_cannot_finish_before_reconciliation(self):
        self.inbox.enter_restore_reconciliation()
        self.expect("RESTORE_INCOMPLETE",self.inbox.finish_restore_reconciliation)
    def test_restore_rebuilds_received_as_review_not_completed(self):
        d=self.delivery();self.inbox.accept(d);self.ack(d)
        blank=LocalInbox(self.root/"restored.sqlite",self.gateway.gateway_id,"demo_queue","pi-demo",self.bindings,clock=self.clock)
        blank.enter_restore_reconciliation()
        blank.reconcile_page(self.gateway.received_history(self.ct))
        blank.finish_restore_reconciliation()
        self.assertEqual(blank.summary()["states"],{"RESTORE_REVIEW":1})
    def test_history_corruption_rolls_back_whole_page(self):
        for i in range(2):self.submit(f"key-number{i}")
        for d in self.gateway.lease(self.ct,2):self.inbox.accept(d);self.ack(d)
        self.inbox.enter_restore_reconciliation();page=self.gateway.received_history(self.ct)
        page["items"][-1]["sha256"]="0"*64
        self.expect("DELIVERY_DIGEST_MISMATCH",self.inbox.reconcile_page,page)
        self.assertEqual(self.inbox.recovery_cursor(),0)
    def test_actual_subprocess_commit_then_exit_survives(self):
        d=self.delivery()
        fixture=self.root/"delivery.json";fixture.write_bytes(canonical(d))
        code='''import json,os,sys
from pathlib import Path
from kintsugi_bridge.inbox import LocalInbox
from kintsugi_bridge.common import FakeClock
p=Path(sys.argv[1]);d=json.loads((p/"delivery.json").read_text())
i=LocalInbox(p/"inbox.sqlite",d["gateway_id"],"demo_queue","pi-demo",{("spark-demo","gmail","demo_mail"):"account-demo"},clock=FakeClock(d["lease_until"]-1))
i.accept(d)
os._exit(23)
'''
        result=subprocess.run([sys.executable,"-c",code,str(self.root)],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,23,result.stderr.decode())
        self.assertEqual(self.inbox.summary()["receipts"],1)
        self.clock.advance(31)
        new=self.gateway.lease(self.ct)[0]
        self.assertEqual(self.inbox.accept(new)["state"],"duplicate")
        self.ack(new)

class WorkerTests(Case):
    def worker(self):return ConsumerWorker(self.gateway,self.inbox,self.ct,self.clock)
    def test_normal_tick(self):
        self.submit();r=self.worker().tick();self.assertEqual(r["acknowledged"],1)
    def test_before_commit_crash_redelivery(self):
        self.submit();self.worker().tick(fault="before_local_commit");self.clock.advance(31)
        r=self.worker().tick();self.assertEqual(r["staged"],1);self.assertEqual(r["acknowledged"],1)
    def test_after_commit_crash_deduplication(self):
        self.submit();self.worker().tick(fault="after_local_commit");self.clock.advance(31)
        r=self.worker().tick();self.assertEqual(r["duplicates"],1);self.assertEqual(r["acknowledged"],1)
    def test_after_ack_loss_no_new_delivery(self):
        self.submit();self.worker().tick(fault="after_ack_commit");self.clock.advance(31)
        self.assertEqual(self.worker().tick()["leased"],0)
    def test_capacity_failure_unacknowledged(self):
        self.inbox.rows=0;self.submit();r=self.worker().tick()
        self.assertIn("INBOX_CAPACITY",r["errors"]);self.assertEqual(r["acknowledged"],0)
    def test_restore_mode_no_leasing(self):
        self.inbox.enter_restore_reconciliation();self.submit()
        self.assertEqual(self.worker().tick()["leased"],0)
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{"stored":1})
    def test_bounded_batch(self):
        for i in range(6):self.submit(f"candidate-{i:04}")
        self.assertEqual(self.worker().tick(max_items=2)["acknowledged"],2)
    def test_budget_validation(self):
        with self.assertRaises(ValueError):self.worker().tick(max_items=6)
    def test_reconnect_backoff_bound(self):
        rng=random.Random(82)
        for i in range(200):self.assertTrue(0<=reconnect_delay(i,rng)<=60)
    def test_longpoll_wakes_on_submission(self):
        poll=LocalLongPoll(self.gateway);out=[]
        thread=threading.Thread(target=lambda:out.extend(poll.wait(self.ct,1)),daemon=True)
        thread.start();time.sleep(0.05);self.submit();poll.notify();thread.join(2)
        self.assertFalse(thread.is_alive());self.assertEqual(len(out),1)
    def test_longpoll_empty_returns_bounded(self):
        poll=LocalLongPoll(self.gateway)
        start=time.monotonic();self.assertEqual(poll.wait(self.ct,.05),[])
        self.assertLess(time.monotonic()-start,1)
    def test_longpoll_revocation_during_wait(self):
        poll=LocalLongPoll(self.gateway);errors=[]
        def waiter():
            try:poll.wait(self.ct,.3)
            except BridgeError as e:errors.append(e.code)
        thread=threading.Thread(target=waiter,daemon=True);thread.start();time.sleep(.02)
        self.auth.revoke(self.ct);poll.notify();thread.join(1)
        self.assertEqual(errors,["UNAUTHENTICATED"])
    def test_250_generated_crash_sequences(self):
        self.pt=self.auth.issue(self.producer,ttl=86400)
        self.ct=self.auth.issue(self.consumer,ttl=86400)
        self.limits(rows=1000,producer_pending=500,producer_rows=500,producer_daily=500,
                    producer_daily_bytes=4*1024*1024,burst=20000,refill_per_second=1000)
        rng=random.Random(20260925)
        worker=self.worker()
        for i in range(250):
            self.submit(f"sequence-{i:04}")
            fault=rng.choice([None,"before_local_commit","after_local_commit","after_ack_commit"])
            worker.tick(max_items=1,fault=fault)
            self.clock.advance(31)
            worker.tick(max_items=1)
        self.assertEqual(self.inbox.summary()["receipts"],250)
        self.assertEqual(self.inbox.summary()["candidates"],1)
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{"locally_received":250})
