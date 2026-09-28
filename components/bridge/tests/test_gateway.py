from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from kintsugi_bridge.auth import Identity, FixtureIdentityVerifier, GATEWAY_AUDIENCE, MONITOR_AUDIENCE
from kintsugi_bridge.common import BridgeError, canonical
from kintsugi_bridge.gateway import Gateway
from kintsugi_bridge.surface import ProducerSurface, TOOLS
from tests.support import Case

class GatewayTests(Case):
    def test_anonymous_rejected(self):
        self.expect("UNAUTHENTICATED",self.gateway.submit_candidate,"",self.raw())
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{})
    def test_wrong_audience_rejected(self):
        token=self.auth.issue(self.producer,MONITOR_AUDIENCE)
        self.expect("UNAUTHENTICATED",self.gateway.submit_candidate,token,self.raw())
    def test_wrong_scope_rejected(self):
        token=self.auth.issue(replace(self.producer,scopes=frozenset({"candidate:status"})))
        self.expect("FORBIDDEN",self.gateway.submit_candidate,token,self.raw())
    def test_consumer_cannot_submit(self):
        self.expect("FORBIDDEN",self.gateway.submit_candidate,self.ct,self.raw())
    def test_producer_cannot_consume(self):
        self.expect("FORBIDDEN",self.gateway.lease,self.pt)
    def test_expiry(self):
        token=self.auth.issue(self.producer,ttl=1);self.clock.advance(1)
        self.expect("UNAUTHENTICATED",self.gateway.submit_candidate,token,self.raw())
    def test_revocation(self):
        self.auth.revoke(self.pt)
        self.expect("UNAUTHENTICATED",self.gateway.submit_candidate,self.pt,self.raw())
    def test_fresh_auth_after_preparation(self):
        original=self.gateway._rate
        def slow(identity,lane):
            original(identity,lane);self.clock.advance(2)
        self.gateway._rate=slow
        token=self.auth.issue(self.producer,ttl=1)
        self.expect("UNAUTHENTICATED",self.gateway.submit_candidate,token,self.raw())
    def test_revocation_during_preparation(self):
        original=self.gateway._rate
        def revoke(identity,lane):
            original(identity,lane);self.auth.revoke(self.pt)
        self.gateway._rate=revoke
        self.expect("UNAUTHENTICATED",self.gateway.submit_candidate,self.pt,self.raw())
    def test_sources_bound_to_authenticated_account(self):
        c=self.raw(source_refs=[{"kind":"gmail","account_alias":"other_account","object_id":"demo"}])
        self.expect("SOURCE_ACCOUNT_FORBIDDEN",self.gateway.submit_candidate,self.pt,c)
    def test_reissue_cannot_reset_burst(self):
        self.limits(burst=2)
        self.submit("item-one1");self.submit("item-two2")
        other=self.auth.issue(self.producer)
        self.expect("RATE_LIMIT",self.gateway.submit_candidate,other,self.raw("item-three3"))
    def test_invalid_requests_consume_burst(self):
        self.limits(burst=2)
        for _ in range(2):self.expect("INVALID_JSON",self.gateway.submit_candidate,self.pt,b'bad')
        self.expect("RATE_LIMIT",self.gateway.submit_candidate,self.pt,self.raw())
    def test_burst_replenishes(self):
        self.limits(burst=1,refill_per_second=1)
        self.submit("item-one1");self.clock.advance(1);self.submit("item-two2")
    def test_daily_limit(self):
        self.limits(producer_daily=1)
        self.submit("item-one1")
        self.expect("DAILY_LIMIT",self.gateway.submit_candidate,self.pt,self.raw("item-two2"))
    def test_daily_byte_limit(self):
        self.limits(producer_daily_bytes=100)
        self.expect("DAILY_LIMIT",self.gateway.submit_candidate,self.pt,self.raw())
    def test_daily_clock_rollback_does_not_reset(self):
        self.limits(producer_daily=1)
        self.submit("item-one1");self.clock.advance(-86400)
        self.expect("DAILY_LIMIT",self.gateway.submit_candidate,self.pt,self.raw("item-two2"))
    def test_total_capacity_limit(self):
        self.limits(rows=1)
        self.submit("item-one1")
        self.expect("CAPACITY_LIMIT",self.gateway.submit_candidate,self.pt,self.raw("item-two2"))
    def test_payload_bytes_capacity_limit(self):
        self.limits(bytes=100)
        self.expect("CAPACITY_LIMIT",self.gateway.submit_candidate,self.pt,self.raw())
    def test_producer_pending_bound(self):
        self.limits(producer_pending=1)
        self.submit("item-one1")
        self.expect("CAPACITY_LIMIT",self.gateway.submit_candidate,self.pt,self.raw("item-two2"))
    def test_status_minimal(self):
        item=self.submit();status=self.gateway.get_submission_status(self.pt,item["submission_id"])
        self.assertEqual(set(status),{"submission_id","status"})
    def test_receipt_isolation(self):
        item=self.submit();other=self.auth.issue(replace(self.producer,subject="other"))
        self.expect("NOT_FOUND",self.gateway.get_submission_status,other,item["submission_id"])
        self.expect("NOT_FOUND",self.gateway.get_submission_status,other,"0"*32)
    def test_idempotent_retry(self):
        a=self.submit();b=self.submit();self.assertEqual(a,b)
    def test_same_key_changed_payload_conflict(self):
        self.submit()
        self.expect("IDEMPOTENCY_CONFLICT",self.gateway.submit_candidate,self.pt,self.raw(urgency_hint="LOW"))
    def test_same_key_different_producer_is_not_same_receipt(self):
        a=self.submit();other=self.auth.issue(replace(self.producer,subject="other"))
        b=self.gateway.submit_candidate(other,self.raw())
        self.assertNotEqual(a["submission_id"],b["submission_id"])
    def test_before_commit_has_no_receipt(self):
        self.expect("INJECTED_BEFORE_COMMIT",self.gateway.submit_candidate,self.pt,self.raw(),fault="before_commit")
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{})
    def test_after_commit_lost_response_recovers_same_receipt(self):
        self.expect("INJECTED_RESPONSE_LOSS",self.gateway.submit_candidate,self.pt,self.raw(),fault="after_commit")
        first=self.submit()
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{"stored":1})
        self.assertEqual(first,self.submit())
    def test_gateway_restart_preserves_receipt(self):
        item=self.submit();old=self.gateway.gateway_id
        self.gateway=Gateway(self.root/"gateway.sqlite",self.auth,self.clock)
        self.assertEqual(old,self.gateway.gateway_id)
        self.assertEqual(item,self.gateway.get_submission_status(self.pt,item["submission_id"]))
    def test_fixture_identity_restart_invalidates_tokens(self):
        self.gateway.verifier=FixtureIdentityVerifier(self.clock)
        self.expect("UNAUTHENTICATED",self.gateway.submit_candidate,self.pt,self.raw())
    def test_pause_survives_restart(self):
        self.gateway.pause()
        self.gateway=Gateway(self.root/"gateway.sqlite",self.auth,self.clock)
        self.expect("ADMISSION_PAUSED",self.gateway.submit_candidate,self.pt,self.raw())
    def test_pause_still_allows_delivery(self):
        self.submit();self.gateway.pause()
        self.assertEqual(len(self.gateway.lease(self.ct)),1)
    def test_simultaneous_same_submission(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.submit(),range(4)))
        self.assertEqual(len({r["submission_id"] for r in results}),1)
    def test_simultaneous_leases_do_not_duplicate(self):
        self.submit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.gateway.lease(self.ct),range(2)))
        self.assertEqual(sum(map(len,results)),1)
    def test_lease_not_destructive(self):
        item=self.submit();self.gateway.lease(self.ct)
        self.assertEqual(self.gateway.get_submission_status(self.pt,item["submission_id"])["status"],"stored")
    def test_expired_lease_redelivered(self):
        d=self.delivery();self.clock.advance(31);other=self.gateway.lease(self.ct)[0]
        self.assertEqual(d["submission_id"],other["submission_id"])
        self.assertNotEqual(d["lease_token"],other["lease_token"])
    def test_old_lease_cannot_ack_after_redelivery(self):
        d=self.delivery();self.clock.advance(31);self.gateway.lease(self.ct)
        self.expect("ACK_MISMATCH",self.ack,d)
    def test_wrong_digest_ack(self):
        d=self.delivery();d["sha256"]="0"*64
        self.expect("ACK_MISMATCH",self.ack,d)
    def test_expired_lease_ack_rejected(self):
        d=self.delivery();self.clock.advance(31)
        self.expect("STALE_LEASE",self.ack,d)
    def test_accepted_ack_is_idempotent(self):
        d=self.delivery();a=self.ack(d);b=self.ack(d);self.assertEqual(a,b)
    def test_ack_after_expiry_cannot_change_disposition(self):
        d=self.delivery();self.ack(d);self.clock.advance(40)
        self.expect("STALE_LEASE",self.ack,d,disposition="rejected")
    def test_ack_response_loss_still_received(self):
        d=self.delivery();self.expect("INJECTED_ACK_RESPONSE_LOSS",self.ack,d,fault="after_commit")
        self.assertEqual(self.ack(d)["status"],"locally_received")
    def test_poison_retry_ceiling(self):
        self.limits(max_attempts=1)
        self.delivery();self.clock.advance(31)
        self.assertEqual(self.gateway.lease(self.ct),[])
        self.assertEqual(self.gateway.operator_snapshot()["counts"],{"rejected":1})
    def test_expiry_recorded_not_deleted(self):
        self.limits(ttl_seconds=1)
        item=self.submit();self.clock.advance(2);self.gateway.lease(self.ct)
        self.assertEqual(self.gateway.get_submission_status(self.pt,item["submission_id"])["status"],"expired")
        self.assertEqual(self.gateway.operator_snapshot()["events"][0]["kind"],"expired")
    def test_storage_payload_corruption_quarantined(self):
        item=self.submit()
        with self.gateway.store.connection(True) as db:db.execute("UPDATE messages SET payload=?",(b'{}',))
        self.assertEqual(self.gateway.lease(self.ct),[])
        self.assertEqual(self.gateway.get_submission_status(self.pt,item["submission_id"])["status"],"rejected")
    def test_batch_size_bound(self):
        self.expect("INTEGER_RANGE",self.gateway.lease,self.ct,6)
    def test_consumer_bound_to_queue_identity(self):
        wrong=self.auth.issue(replace(self.consumer,subject="wrong-device"))
        self.expect("FORBIDDEN",self.gateway.lease,wrong)
    def test_two_tools_only(self):
        self.assertEqual(len(TOOLS),2)
        surface=ProducerSurface(self.gateway)
        for name in ["jarvis.get_household_brief","jarvis.get_system_health","jarvis.submit_observation","jarvis.request_decision","jarvis.execute_payment"]:
            self.expect("TOOL_NOT_AVAILABLE",surface.call,self.pt,name,b'{}')
    def test_surface_success(self):
        surface=ProducerSurface(self.gateway)
        item=surface.call(self.pt,TOOLS[0],self.raw())
        self.assertEqual(item,surface.call(self.pt,TOOLS[1],canonical({"submission_id":item["submission_id"]})))
