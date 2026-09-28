import http.cookiejar,json,tempfile,threading,unittest,urllib.request,urllib.error,uuid
from jarvis.web import LocalUI

class LocalUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.server=LocalUI(cls.tmp.name,0,'synthetic-ui-login-only');cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def setUp(self):self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,body=None,headers=None,opener=None):
        h={'Origin':self.url};h.update(headers or {})
        if body is not None:h['Content-Type']='application/json'
        req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=h)
        try:r=(opener or self.opener).open(req)
        except urllib.error.HTTPError as e:r=e
        return r.status,r.read(),dict(r.headers)
    def login(self):
        code,_,_=self.call('/api/login',{'token':'synthetic-ui-login-only'});self.assertEqual(code,200)
        _,b,_=self.call('/api/state');return json.loads(b)['csrf']
    def test_no_state_without_session(self):self.assertEqual(self.call('/api/state')[0],401)
    def test_cross_origin_login_blocked(self):self.assertEqual(self.call('/api/login',{'token':'synthetic-ui-login-only'},{'Origin':'https://external.invalid'})[0],403)
    def test_dns_rebinding_host_blocked(self):self.assertEqual(self.call('/',headers={'Host':'evil.invalid'})[0],403)
    def test_csrf_required_for_mutation(self):
        self.login();self.assertEqual(self.call('/api/command',{'command_id':'x','op':'capture','text':'test'})[0],403)
    def test_U01_positive_capture(self):
        csrf=self.login();code,b,_=self.call('/api/command',{'command_id':str(uuid.uuid4()),'op':'capture','text':'Local thought'},{'X-CSRF-Token':csrf});self.assertEqual(code,200)
    def test_U03_approval_endpoint_not_exposed(self):
        csrf=self.login();self.assertEqual(self.call('/api/approve',{'spoken':'yes','approved_by':'sovereign'},{'X-CSRF-Token':csrf})[0],404)
    def test_policy_escalation_not_in_household_api(self):
        csrf=self.login();self.assertEqual(self.call('/api/command',{'command_id':'hack','op':'pay_bill'},{'X-CSRF-Token':csrf})[0],400)
    def test_security_headers(self):
        code,_,h=self.call('/');self.assertEqual(code,200);self.assertEqual(h['Cache-Control'],'no-store');self.assertIn("frame-ancestors 'none'",h['Content-Security-Policy'])
    def test_unsafe_static_path_not_served(self):self.assertEqual(self.call('/../jarvis/authority.py')[0],404)
    def test_cookie_not_accessible_to_javascript(self):
        _,_,h=self.call('/api/login',{'token':'synthetic-ui-login-only'});self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Strict',h['Set-Cookie'])
