"""Executable non-sensitive demonstration; all credentials and sources are fake."""
from pathlib import Path
import tempfile
from .auth import FixtureIdentityVerifier, Identity, MONITOR_AUDIENCE
from .common import FakeClock, canonical
from .gateway import Gateway
from .inbox import LocalInbox
from .monitor import Monitor, sign_report
from .schema import example_candidate
from .worker import ConsumerWorker

def run_demo()->dict:
    with tempfile.TemporaryDirectory(prefix="kintsugi-bridge-demo-") as tmp:
        root=Path(tmp)
        clock=FakeClock()
        auth=FixtureIdentityVerifier(clock)
        producer=Identity("spark-demo","producer","demo_queue",frozenset({"candidate:submit","candidate:status"}),frozenset({("gmail","demo_mail")}))
        consumer=Identity("pi-demo","consumer","demo_queue",frozenset({"delivery:lease","delivery:ack","delivery:history"}))
        pt,ct=auth.issue(producer),auth.issue(consumer)
        gateway=Gateway(root/"gateway"/"queue.sqlite",auth,clock)
        inbox=LocalInbox(root/"pi"/"inbox.sqlite",gateway.gateway_id,"demo_queue","pi-demo",{("spark-demo","gmail","demo_mail"):"synthetic-account"},clock=clock)
        first=gateway.submit_candidate(pt,canonical(example_candidate()))
        worker=ConsumerWorker(gateway,inbox,ct,clock)
        interrupted=worker.tick(fault="after_local_commit")
        clock.advance(31)
        recovered=worker.tick()
        final=gateway.get_submission_status(pt,first["submission_id"])
        mt=auth.issue(Identity("node-demo","reporter","monitor",frozenset({"health:report"})),MONITOR_AUDIENCE)
        monitor=Monitor(root/"monitor"/"health.sqlite",auth,clock)
        epoch,key=monitor.enroll("node-demo")
        body={"node_id":"node-demo","enrollment_epoch":epoch,"sequence":1,"sent_at":int(clock.now()),"progress_sequence":1,"coverage":"COMPLETE"}
        monitor.receive(mt,sign_report(key,body))
        before=monitor.evaluate()
        clock.advance(91)
        after=monitor.evaluate()
        return {"mode":"LOCAL_ONLY_SYNTHETIC","public_listener":False,"oauth_connected":False,
                "after_submission":first["status"],"interrupted_tick":interrupted,
                "recovery_tick":recovered,"final_transport_status":final["status"],
                "private_inbox":inbox.summary(),"health_before":before,"health_after":after,
                "health_alert_delivery":"NOT_SENT","live_provider_writes":0,
                "v3_2_modified":False}
