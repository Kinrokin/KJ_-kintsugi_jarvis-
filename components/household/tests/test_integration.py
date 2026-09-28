import json,tempfile,unittest
from jarvis.calendar import *
from jarvis.common import *

class HttpContractTests(unittest.TestCase):
    """Mock transport only. No Google account, token or network involved."""
    def setUp(self):self.calls=[];self.object=None;self.response=201;self.acl=[{'role':'owner','scope':{'type':'user','value':'owner@example.invalid'}}]
    def transport(self,method,url,body,headers):
        self.calls.append((method,url,body,headers))
        if '/acl' in url:return 200,{'items':self.acl}
        if method=='GET':return (200,self.object) if self.object else (404,{})
        if self.response in (200,201):
            self.object=dict(body);self.object.update(id=body.get('id',self.object.get('id') if self.object else 'existing'),etag='"2"')
        return self.response,{}
    def adapter(self):return GoogleCalendar(lambda:'not-used',['allowed'],self.transport)
    def p(self):return make_proposal('allowed',{'summary':'Test','start':'2026-09-25T13:00:00Z','end':'2026-09-25T14:00:00Z'},'test')
    def test_I01_creation_contract_has_stable_id(self):
        a=self.adapter();p=self.p();a.apply(p);req=self.calls[-1];self.assertEqual(req[2]['id'],p['event_id']);self.assertIn('sendUpdates=none',req[1]);self.assertEqual(req[2]['visibility'],'private')
    def test_readback_comes_from_transport(self):
        a=self.adapter();p=self.p();a.apply(p);r=a.get('allowed',p['event_id']);self.assertEqual(r['payload'],p['payload'])
    def test_I02_patch_sends_approved_etag(self):
        a=self.adapter();p=self.p();a.apply(p);u=make_proposal('allowed',dict(p['payload'],summary='New'),'update',event_id=p['event_id'],expected_version='"2"');a.apply(u)
        self.assertEqual(self.calls[-1][3],{'If-Match':'"2"'});self.assertEqual(self.calls[-1][0],'PATCH')
    def test_412_no_effect(self):
        a=self.adapter();p=self.p();a.apply(p);self.response=412
        u=make_proposal('allowed',p['payload'],'update',event_id=p['event_id'],expected_version='"2"')
        with self.assertRaises(NoEffect):a.apply(u)
    def test_409_unknown_no_blind_retry(self):
        self.response=409
        with self.assertRaises(UnknownOutcome):self.adapter().apply(self.p())
        self.assertEqual(len(self.calls),1)
    def test_500_unknown(self):
        self.response=500
        with self.assertRaises(UnknownOutcome):self.adapter().apply(self.p())
    def test_unknown_target_refused(self):
        with self.assertRaises(Refused):self.adapter().audience('wrong')
    def test_acl_read_verified(self):self.assertEqual(self.adapter().audience('allowed')['viewers'],['owner@example.invalid'])
    def test_group_acl_refused(self):
        self.acl.append({'role':'reader','scope':{'type':'group','value':'group@example.invalid'}})
        with self.assertRaises(Refused):self.adapter().audience('allowed')
    def test_pagination_failure_does_not_certify_audience(self):
        calls=[]
        def pages(*args):
            calls.append(args)
            if len(calls)==1:return 200,{'items':self.acl,'nextPageToken':'next'}
            return 503,{}
        with self.assertRaises(Refused):GoogleCalendar(lambda:'x',['allowed'],pages).audience('allowed')
    def test_non_kintsugi_event_not_modified(self):
        self.object={'id':'x','etag':'1','summary':'Private event','start':{'dateTime':'2026-09-25T13:00:00Z'},'end':{'dateTime':'2026-09-25T14:00:00Z'}}
        with self.assertRaises(Refused):self.adapter().get('allowed','x')
    def test_attended_event_outside_scope(self):
        a=self.adapter();p=self.p();a.apply(p);self.object['attendees']=[{'email':'someone@example.invalid'}]
        with self.assertRaises(Refused):a.get('allowed',p['event_id'])
    def test_unauthenticated_acl_refused(self):
        with self.assertRaises(Refused):GoogleCalendar(lambda:'x',['allowed'],lambda *x:(401,{})).audience('allowed')
    def test_redirect_not_followed(self):
        from jarvis.calendar import NoRedirect
        with self.assertRaises(Refused):NoRedirect().redirect_request(None,None,302,'x',{},'https://evil.invalid')
