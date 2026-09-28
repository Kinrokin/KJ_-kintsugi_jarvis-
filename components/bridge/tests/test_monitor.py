from pathlib import Path
from kintsugi_bridge.auth import Identity, MONITOR_AUDIENCE
from kintsugi_bridge.common import canonical, bounded_json
from kintsugi_bridge.monitor import Monitor, sign_report
from tests.support import Case

class MonitorTests(Case):
    def setUp(self):
        super().setUp()
        self.monitor=Monitor(self.root/"monitor.sqlite",self.auth,self.clock)
        self.epoch,self.key=self.monitor.enroll("node-demo")
        self.mt=self.auth.issue(Identity("node-demo","reporter","monitor",frozenset({"health:report"})),MONITOR_AUDIENCE)
    def report(self,seq=1,progress=1,coverage="COMPLETE",**changes):
        b={"node_id":"node-demo","enrollment_epoch":self.epoch,"sequence":seq,"sent_at":int(self.clock.now()),"progress_sequence":progress,"coverage":coverage}
        b.update(changes);return sign_report(self.key,b)
    def test_valid_health(self):
        self.monitor.receive(self.mt,self.report());self.assertEqual(self.monitor.evaluate(),{"node-demo":"HEALTHY"})
    def test_missing_report_unknown_not_healthy(self):
        self.assertEqual(self.monitor.evaluate(),{"node-demo":"AWAITING_REPORT"})
    def test_gateway_producer_cannot_report_health(self):
        self.expect("UNAUTHENTICATED",self.monitor.receive,self.pt,self.report())
    def test_bad_signature(self):
        b=bounded_json(self.report());b["mac"]="0"*64
        self.expect("REPORT_AUTHENTICATION",self.monitor.receive,self.mt,canonical(b))
    def test_payload_mutation(self):
        b=bounded_json(self.report());b["report"]["progress_sequence"]=50
        self.expect("REPORT_AUTHENTICATION",self.monitor.receive,self.mt,canonical(b))
    def test_replay_does_not_refresh_liveness(self):
        raw=self.report();self.monitor.receive(self.mt,raw);self.clock.advance(91)
        self.expect("REPORT_REPLAY",self.monitor.receive,self.mt,raw)
        self.assertEqual(self.monitor.evaluate()["node-demo"],"UNREACHABLE")
    def test_stale_signed_report_rejected(self):
        self.expect("REPORT_STALE",self.monitor.receive,self.mt,self.report(sent_at=int(self.clock.now()-61)))
    def test_future_signed_report_rejected(self):
        self.expect("REPORT_STALE",self.monitor.receive,self.mt,self.report(sent_at=int(self.clock.now()+6)))
    def test_cross_node_rejected(self):
        self.expect("REPORT_BINDING",self.monitor.receive,self.mt,self.report(node_id="other-node"))
    def test_epoch_rotation_rejects_old_report(self):
        raw=self.report();self.monitor.enroll("node-demo")
        self.expect("REPORT_AUTHENTICATION",self.monitor.receive,self.mt,raw)
    def test_forged_epoch_with_current_key_rejected(self):
        self.expect("REPORT_EPOCH",self.monitor.receive,self.mt,self.report(enrollment_epoch="wrong"))
    def test_coverage_degradation(self):
        self.monitor.receive(self.mt,self.report(coverage="PARTIAL"))
        self.assertEqual(self.monitor.evaluate()["node-demo"],"DEGRADED")
    def test_fresh_heartbeat_stalled_progress(self):
        self.monitor.receive(self.mt,self.report())
        self.clock.advance(91)
        self.monitor.receive(self.mt,self.report(seq=2,progress=1))
        self.assertEqual(self.monitor.evaluate()["node-demo"],"STALLED")
    def test_progress_recovery(self):
        self.monitor.receive(self.mt,self.report());self.clock.advance(91);self.monitor.evaluate()
        self.monitor.receive(self.mt,self.report(seq=2,progress=2))
        self.assertEqual(self.monitor.evaluate()["node-demo"],"HEALTHY")
    def test_quiet_queue_can_report_completed_empty_scan_progress(self):
        self.monitor.receive(self.mt,self.report(progress=1));self.clock.advance(20)
        self.monitor.receive(self.mt,self.report(seq=2,progress=2))
        self.assertEqual(self.monitor.evaluate()["node-demo"],"HEALTHY")
    def test_report_rate_bound(self):
        self.monitor.receive(self.mt,self.report())
        self.expect("REPORT_RATE_LIMIT",self.monitor.receive,self.mt,self.report(seq=2))
    def test_alert_only_on_state_change(self):
        self.monitor.receive(self.mt,self.report());n=len(self.monitor.alert_outbox())
        for _ in range(3):self.monitor.evaluate()
        self.assertEqual(len(self.monitor.alert_outbox()),n)
    def test_alerts_generic_and_not_falsely_sent(self):
        self.monitor.receive(self.mt,self.report());self.clock.advance(91);self.monitor.evaluate()
        for alert in self.monitor.alert_outbox():
            self.assertEqual(alert["delivery"],"NOT_SENT")
            self.assertNotIn("school",alert["text"])
    def test_restart_requires_trusted_key(self):
        self.monitor.receive(self.mt,self.report());self.clock.advance(6)
        again=Monitor(self.root/"monitor.sqlite",self.auth,self.clock)
        self.expect("REPORT_AUTHENTICATION",again.receive,self.mt,self.report(seq=2,progress=2))
        again.load_key("node-demo",self.key)
        again.receive(self.mt,self.report(seq=2,progress=2))
    def test_restart_preserves_replay_floor(self):
        raw=self.report();self.monitor.receive(self.mt,raw);self.clock.advance(6)
        again=Monitor(self.root/"monitor.sqlite",self.auth,self.clock);again.load_key("node-demo",self.key)
        self.expect("REPORT_REPLAY",again.receive,self.mt,raw)
    def test_extra_sensitive_fields_rejected(self):
        self.expect("FIELD_SET",self.monitor.receive,self.mt,self.report(location="home"))
    def test_backwards_clock_not_healthy(self):
        self.monitor.receive(self.mt,self.report());self.clock.advance(-1)
        self.assertEqual(self.monitor.evaluate()["node-demo"],"CLOCK_UNVERIFIED")
    def test_never_started_reporter_alerts_after_grace(self):
        self.clock.advance(91)
        self.assertEqual(self.monitor.evaluate()["node-demo"],"UNREACHABLE")
        self.assertEqual(len(self.monitor.alert_outbox()),1)
