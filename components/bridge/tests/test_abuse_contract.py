from dataclasses import replace
import ast
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import unittest
from kintsugi_bridge.auth import FixtureIdentityVerifier, Identity
from kintsugi_bridge.common import BridgeError, Store, canonical
from kintsugi_bridge.gateway import Gateway
from kintsugi_bridge.demo import run_demo
from tests.support import Case

class AbuseTests(Case):
    def test_bad_producer_saturates_only_own_pending_budget(self):
        self.limits(producer_pending=1)
        self.submit("first-msg1")
        for _ in range(10):
            self.expect("CAPACITY_LIMIT",self.gateway.submit_candidate,self.pt,self.raw("second-msg2"))
        other=self.auth.issue(replace(self.producer,subject="other-producer"))
        r=self.gateway.submit_candidate(other,self.raw("legit-msg3"))
        self.assertEqual(r["status"],"stored")
    def test_high_urgency_does_not_reorder_delivery(self):
        a=self.submit("first-msg1")
        b=self.gateway.submit_candidate(self.pt,self.raw("second-msg2",urgency_hint="CRITICAL"))
        d=self.gateway.lease(self.ct,2)
        self.assertEqual([x["submission_id"] for x in d],[a["submission_id"],b["submission_id"]])
    def test_quota_survives_gateway_restart(self):
        self.limits(burst=1)
        self.submit()
        self.gateway=Gateway(self.root/"gateway.sqlite",self.auth,self.clock,limits=self.gateway.limits)
        self.expect("RATE_LIMIT",self.gateway.submit_candidate,self.pt,self.raw("next-key2"))
    def test_rejected_event_ring_is_bounded(self):
        self.limits(operator_events=2,ttl_seconds=1)
        for i in range(3):self.submit(f"expired-{i}")
        self.clock.advance(2);self.gateway.lease(self.ct)
        self.assertEqual(len(self.gateway.operator_snapshot()["events"]),2)
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{"expired":3})
    def test_local_commit_expired_lease_rejected(self):
        d=self.delivery();self.clock.advance(31)
        self.expect("DELIVERY_LEASE_EXPIRED",self.inbox.accept,d)
        self.assertEqual(self.inbox.summary()["receipts"],0)
    def test_damaged_recovery_page_not_acknowledged(self):
        d=self.delivery();self.inbox.accept(d);self.ack(d)
        with self.gateway.store.connection(True) as db:db.execute("UPDATE messages SET payload=?",(b'{}',))
        self.expect("HISTORY_CORRUPTED",self.gateway.received_history,self.ct)
    def test_real_sqlite_page_limit_refuses_large_insert(self):
        small=Store(self.root/"small.sqlite",max_pages=16)
        with small.connection(True) as db:db.execute("CREATE TABLE t(v BLOB)")
        def fill():
            with small.connection(True) as db:db.execute("INSERT INTO t VALUES(?)",(b'x'*200000,))
        self.expect("STORE_UNAVAILABLE",fill)
        with small.connection() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM t").fetchone()[0],0)
    def test_uncommitted_process_exit_leaves_no_partial_record(self):
        path=self.root/"crash.sqlite"
        store=Store(path)
        with store.connection(True) as db:db.execute("CREATE TABLE t(v TEXT)")
        code='import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute("BEGIN IMMEDIATE");c.execute("INSERT INTO t VALUES(?)",("pending",));os._exit(24)'
        r=subprocess.run([sys.executable,"-c",code,str(path)],capture_output=True,timeout=10)
        self.assertEqual(r.returncode,24)
        with store.connection() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM t").fetchone()[0],0)
    def test_lock_contention_is_bounded_and_preserves_state(self):
        blocker=sqlite3.connect(self.root/"gateway.sqlite",isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")
        try:self.expect("STORE_BUSY",self.gateway.submit_candidate,self.pt,self.raw())
        finally:blocker.rollback();blocker.close()
        self.assertEqual(self.submit()["status"],"stored")
    def test_runtime_contains_no_network_or_process_launch_imports(self):
        root=Path(__file__).resolve().parents[1]/"kintsugi_bridge"
        forbidden={"socket","requests","http","urllib","subprocess","paramiko"}
        for path in root.glob("*.py"):
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    self.assertTrue(all(a.name.split('.')[0] not in forbidden for a in node.names),path)
                elif isinstance(node,ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split('.')[0],forbidden,path)
    def test_cli_demo_runs_and_claims_only_local_receipt(self):
        r=run_demo()
        self.assertFalse(r["public_listener"])
        self.assertFalse(r["oauth_connected"])
        self.assertEqual(r["final_transport_status"],"locally_received")
        self.assertEqual(r["private_inbox"]["states"],{"UNVERIFIED":1})
        self.assertEqual(r["health_alert_delivery"],"NOT_SENT")
    def test_leased_payload_is_never_provider_execution_ticket(self):
        d=self.delivery()
        self.assertNotIn("authority",d)
        self.assertNotIn("approved_by",d)
        self.inbox.accept(d)
        self.assertEqual(self.inbox.summary()["states"],{"UNVERIFIED":1})
