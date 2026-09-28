from pathlib import Path
from dataclasses import replace
import tempfile
import unittest
from kintsugi_bridge.auth import FixtureIdentityVerifier, Identity, MONITOR_AUDIENCE
from kintsugi_bridge.common import BridgeError, FakeClock, canonical
from kintsugi_bridge.gateway import Gateway, Limits
from kintsugi_bridge.inbox import LocalInbox
from kintsugi_bridge.monitor import Monitor, sign_report
from kintsugi_bridge.schema import example_candidate

class Case(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="bridge-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.clock=FakeClock()
        self.auth=FixtureIdentityVerifier(self.clock)
        self.producer=Identity("spark-demo","producer","demo_queue",frozenset({"candidate:submit","candidate:status"}),frozenset({("gmail","demo_mail")}))
        self.consumer=Identity("pi-demo","consumer","demo_queue",frozenset({"delivery:lease","delivery:ack","delivery:history"}))
        self.pt=self.auth.issue(self.producer)
        self.ct=self.auth.issue(self.consumer)
        self.gateway=Gateway(self.root/"gateway.sqlite",self.auth,self.clock)
        self.bindings={("spark-demo","gmail","demo_mail"):"account-demo"}
        self.inbox=LocalInbox(self.root/"inbox.sqlite",self.gateway.gateway_id,"demo_queue","pi-demo",self.bindings,clock=self.clock)
    def raw(self,key="candidate-0001",**changes):
        c=example_candidate(key)
        c.update(changes)
        return canonical(c)
    def submit(self,key="candidate-0001"):
        return self.gateway.submit_candidate(self.pt,self.raw(key))
    def delivery(self):
        self.submit()
        return self.gateway.lease(self.ct)[0]
    def expect(self,code,fn,*args,**kw):
        with self.assertRaises(BridgeError) as ctx:
            fn(*args,**kw)
        self.assertEqual(ctx.exception.code,code)
    def limits(self,**changes):
        self.gateway.limits=replace(self.gateway.limits,**changes)
    def ack(self,d,**kw):
        return self.gateway.acknowledge(self.ct,d["submission_id"],d["lease_token"],d["sha256"],**kw)
