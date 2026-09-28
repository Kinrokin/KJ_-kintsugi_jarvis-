import http.cookiejar,json,tempfile,threading,unittest,urllib.request,urllib.error,uuid,ssl
from jarvis.web import LocalUI,serve_phone_trial
from jarvis.household import Household
from jarvis.common import Refused,now_utc,iso
from test_household import routine

class PhoneSurfaceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.server=LocalUI(cls.tmp.name,0,'fixture-token');cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def setUp(self):self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,body=None,headers=None):
        h={'Origin':self.url};h.update(headers or {})
        if body is not None:h['Content-Type']='application/json'
        r=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=h)
        try:r=self.opener.open(r)
        except urllib.error.HTTPError as e:r=e
        return r.status,r.read(),dict(r.headers)
    def login(self):
        self.assertEqual(self.call('/api/login',{'token':'fixture-token'})[0],200)
        _,b,_=self.call('/api/state');return json.loads(b)
    def test_P01_legacy_timed_http_command_is_held_for_review(self):
        s=self.login();code,b,_=self.call('/api/command',{'command_id':'legacy','op':'done','object_id':'x','expected_revision':0},{'X-CSRF-Token':s['csrf']})
        self.assertEqual(code,409);self.assertIn(b'original time/context',b)
    def test_P02_versioned_minimum_mode_command_succeeds(self):
        s=self.login();event={'version':1,'occurred_at':iso(now_utc()),'household_instance':s['instance_id'],'source':'user_report'}
        code,b,_=self.call('/api/command',{'command_id':str(uuid.uuid4()),'op':'simplify','client_event':event},{'X-CSRF-Token':s['csrf']})
        self.assertEqual(code,200);self.assertEqual(json.loads(b)['mode'],'minimum')
    def test_P03_foreground_cues_are_not_claimed_as_push(self):
        s=self.login();code,b,_=self.call('/api/cues',{}, {'X-CSRF-Token':s['csrf']})
        self.assertEqual(code,200);self.assertEqual(json.loads(b)['delivery'],'OFFERED_TO_FOREGROUND_UI_NOT_PUSH_OR_COMPLETION')
    def test_P04_cue_endpoint_requires_csrf(self):
        self.login();self.assertEqual(self.call('/api/cues',{})[0],403)
    def test_P05_logout_invalidates_session(self):
        s=self.login();self.assertEqual(self.call('/api/logout',{}, {'X-CSRF-Token':s['csrf']})[0],200)
        self.assertEqual(self.call('/api/state')[0],401)
    def test_P06_api_never_cached(self):
        self.login();_,_,h=self.call('/api/state');self.assertEqual(h['Cache-Control'],'no-store')
    def test_P07_service_worker_has_only_static_shell_allowlist(self):
        code,b,_=self.call('/sw.js');self.assertEqual(code,200);self.assertIn(b"const SHELL=['/','/app.js','/operations.js','/style.css','/manifest.webmanifest','/icon.svg']",b)
        self.assertIn(b"addEventListener('push'",b);self.assertNotIn(b"addEventListener('sync'",b);self.assertNotIn(b'/api/command',b)
    def test_P08_manifest_is_available_no_remote_start_url(self):
        code,b,_=self.call('/manifest.webmanifest');self.assertEqual(code,200);self.assertEqual(json.loads(b)['start_url'],'/')
    def test_P09_forwarded_headers_do_not_bypass_origin(self):
        s=self.login();self.assertEqual(self.call('/api/cues',{}, {'X-CSRF-Token':s['csrf'],'Origin':'https://evil.invalid','X-Forwarded-Host':'localhost','X-Forwarded-Proto':'https'})[0],403)
    def test_P10_insecure_nonloopback_listener_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):LocalUI(d,0,host='192.168.1.9')
    def test_P11_public_listener_is_refused_even_with_tls(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):LocalUI(d,0,host='8.8.8.8',tls_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER),public_origin='https://8.8.8.8:8766')
    def test_P12_wildcard_listener_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):LocalUI(d,0,host='0.0.0.0')
    def test_P13_trial_requires_explicit_acknowledgment(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):serve_phone_trial(d,'192.168.1.9',8766,'absent','absent','https://192.168.1.9:8766')
    def test_P14_origin_with_userinfo_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):LocalUI(d,0,tls_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER),public_origin='https://user:pass@localhost:8766')

    def test_P15_malformed_origin_port_is_refused_before_binding(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):LocalUI(d,0,tls_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER),public_origin='https://localhost:invalid')

    def test_P16_nonobject_json_is_refused_without_session_or_command_effect(self):
        self.assertEqual(self.call('/api/login',[])[0],400)
        self.assertEqual(self.call('/api/cues',[])[0],400)
