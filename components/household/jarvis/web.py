"""Loopback-default household UI with an explicit private-LAN HTTPS trial.
No broker/approval/payment endpoints. Not an Internet-facing production service;
responsive-browser tests are not an Android installation.
"""
from __future__ import annotations
import json, secrets, threading, time as monotime, ssl, ipaddress
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from .common import *
from .household import Household

class LocalUI(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,root,port=0,login_token=None,*,host="127.0.0.1",tls_context=None,public_origin=None,operations_config=None):
        self.state_root=private_root(root);self.token=login_token or secrets.token_urlsafe(24)
        self.sessions={};self.failures=[];self.mutex=threading.Lock()
        self.operations_config=operations_config;self.connection_slots=threading.BoundedSemaphore(24)
        self.secure=tls_context is not None
        addr=ipaddress.ip_address(host)
        private_v4=addr.version==4 and any(addr in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
        if host!='127.0.0.1' and not (self.secure and private_v4 and public_origin):
            raise Refused('Phone trial requires a specific private IPv4 address, TLS and an explicit HTTPS origin')
        parsed=urlsplit(public_origin) if public_origin else None
        if parsed and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment):
            raise Refused('Invalid private HTTPS origin')
        if parsed and not self.secure:raise Refused('HTTPS origin requires TLS')
        try: origin_port=(parsed.port or 443) if parsed else None
        except ValueError: raise Refused('Invalid HTTPS origin port') from None
        super().__init__((host,port),Handler)
        if tls_context:self.socket=tls_context.wrap_socket(self.socket,server_side=True)
        scheme='https' if self.secure else 'http'
        self.allowed_hosts={f'{host}:{self.server_port}'}
        if host=='127.0.0.1':self.allowed_hosts.add(f'localhost:{self.server_port}')
        self.allowed_origins={f'{scheme}://{x}' for x in self.allowed_hosts}
        if parsed:
            if origin_port!=self.server_port:
                self.server_close();raise Refused('HTTPS origin port must match the trial listener')
            self.allowed_hosts={parsed.netloc};self.allowed_origins={f'https://{parsed.netloc}'}
        self.scope='PRIVATE_LAN_HTTPS_TRIAL' if host!='127.0.0.1' else 'LOOPBACK_HOUSEHOLD_ONLY'
        self.timeout=15

    def process_request(self,request,client_address):
        if not self.connection_slots.acquire(blocking=False):
            self.shutdown_request(request);return
        try:super().process_request(request,client_address)
        except BaseException:self.connection_slots.release();raise
    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self.connection_slots.release()

    def session(self,header):
        c=SimpleCookie()
        try:c.load(header or '')
        except Exception:return None
        sid=c.get('jarvis_session');s=self.sessions.get(sid.value) if sid else None
        return s if s and monotime.monotonic()<s['expires'] else None

class Handler(BaseHTTPRequestHandler):
    server_version='KintsugiLocal'
    timeout=15
    def log_message(self,*args):pass  # No bodies, session identifiers or URLs logged.
    def _send(self,status,body,ctype='application/json',cookie=None):
        raw=canonical(body).encode() if ctype=='application/json' else body
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(raw)
    def _host(self):
        return self.headers.get('Host') in self.server.allowed_hosts
    def _origin(self):
        return self.headers.get('Origin') in self.server.allowed_origins
    def do_GET(self):
        if not self._host():return self._send(403,{'error':'Host refused'})
        if self.path in {'/','/app.js','/operations.js','/style.css','/sw.js','/manifest.webmanifest','/icon.svg'}:
            name={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/sw.js':'sw.js','/manifest.webmanifest':'manifest.webmanifest','/operations.js':'operations.js','/icon.svg':'icon.svg'}[self.path]
            kind={'/':'text/html; charset=utf-8','/app.js':'application/javascript','/style.css':'text/css','/sw.js':'application/javascript','/manifest.webmanifest':'application/manifest+json','/operations.js':'application/javascript','/icon.svg':'image/svg+xml'}[self.path]
            return self._send(200,(Path(__file__).parents[1]/'web'/name).read_bytes(),kind)
        if self.server.operations_config:
            from .operations_api import GET_ROUTES,get
            if self.path in GET_ROUTES:
                if not self.server.session(self.headers.get('Cookie')):return self._send(401,{'error':'Local session required'})
                try:return self._send(200,get(self.server.operations_config,self.path))
                except Exception:return self._send(503,{'error':'Operations state unavailable'})
        if self.path!='/api/state':return self._send(404,{'error':'Not found'})
        s=self.server.session(self.headers.get('Cookie'))
        if not s:return self._send(401,{'error':'Local session required'})
        h=Household(self.server.state_root)
        try:
            snapshot=h.tick();snapshot['csrf']=s['csrf'];snapshot['server_scope']=self.server.scope; snapshot['reminder_delivery']='FOREGROUND_ONLY_NO_PUSH'
            snapshot['phone_trial_certified']=False
            if self.server.operations_config:
                snapshot['reminder_delivery']='FOREGROUND_WITH_OPTIONAL_PUSH_NOT_DELIVERY_CERTIFICATION'
            return self._send(200,snapshot)
        finally:h.close()
    def do_POST(self):
        if not self._host() or not self._origin():return self._send(403,{'error':'Origin or Host refused'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self._send(415,{'error':'JSON required'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise Refused('Body size refused')
            b=strict_json(self.rfile.read(length).decode())
            if not isinstance(b,dict):raise Refused('JSON object required')
        except Exception:return self._send(400,{'error':'Invalid request body'})
        if self.path=='/api/push-ack' and self.server.operations_config:
            from .operations_api import push_ack
            try:return self._send(200,push_ack(self.server.operations_config,b))
            except (Refused,ValueError,KeyError):return self._send(403,{'error':'Notification receipt refused'})
        if self.path=='/api/login':
            with self.server.mutex:
                t=monotime.monotonic();self.server.sessions={k:v for k,v in self.server.sessions.items() if v['expires']>t}
                if len(self.server.sessions)>=128:return self._send(429,{'error':'Too many local sessions; restart to revoke them'})
                self.server.failures=[x for x in self.server.failures if t-x<60]
                if len(self.server.failures)>=5:return self._send(429,{'error':'Wait a minute before another login attempt'})
                if not isinstance(b.get('token'),str) or not secrets.compare_digest(b['token'],self.server.token):
                    self.server.failures.append(t);return self._send(403,{'error':'Invalid local login code'})
                sid=secrets.token_urlsafe(32);self.server.sessions[sid]={'csrf':secrets.token_urlsafe(32),'expires':t+12*3600}
            return self._send(200,{'ok':True},cookie=f'jarvis_session={sid}; Path=/; HttpOnly; SameSite=Strict'+('; Secure' if self.server.secure else ''))
        s=self.server.session(self.headers.get('Cookie'))
        if not s:return self._send(401,{'error':'Local session required'})
        if not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']):return self._send(403,{'error':'CSRF token required'})
        if self.path=='/api/logout':
            cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
            sid=cookies.get('jarvis_session')
            if sid:self.server.sessions.pop(sid.value,None)
            return self._send(200,{'ok':True},cookie='jarvis_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict'+('; Secure' if self.server.secure else ''))
        if self.server.operations_config:
            from .operations_api import POST_ROUTES,post
            if self.path in POST_ROUTES:
                try:return self._send(200,post(self.server.operations_config,self.path,b))
                except Conflict as e:return self._send(409,{'error':str(e)})
                except (Refused,ValueError,KeyError,TypeError) as e:return self._send(400,{'error':str(e)})
                except Exception:return self._send(500,{'error':'Operational request failed; refresh before retry'})
        if self.path not in {'/api/command','/api/cues'}:return self._send(404,{'error':'No such action endpoint'})
        h=Household(self.server.state_root)
        try:
            if self.path=='/api/cues':
                if b!={}:raise Refused('No fields accepted by local cue endpoint')
                snap=h.tick();cues=[h.remind(x['id']) for x in snap['upcoming']]
                return self._send(200,{'cues':[x for x in cues if x.get('display')],
                                     'delivery':'OFFERED_TO_FOREGROUND_UI_NOT_PUSH_OR_COMPLETION'})
            if b.get('op') in {'done','undo','skip','snooze','simplify','normal','complete_obligation'} and not b.get('client_event'):
                raise Conflict('Old queued change lacks its original time/context; review it instead of silently replaying')
            return self._send(200,h.command(b))
        except Conflict as e:return self._send(409,{'error':str(e)})
        except (Refused,ValueError,TypeError,KeyError) as e:return self._send(400,{'error':str(e)})
        except Exception:return self._send(500,{'error':'Local operation failed; retain command ID and inspect private state'})
        finally:h.close()

def serve(root,port=8765):
    server=LocalUI(root,port)
    print('Open http://127.0.0.1:'+str(server.server_port),flush=True)
    print('Private local login code: '+server.token,flush=True)
    print('No external accounts, live grants, or scheduled jobs are exposed by this UI.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


def serve_phone_trial(root,host,port,certfile,keyfile,origin,*,ack_private_lan=False):
    """Explicit short-lived HTTPS trial, not an installed/Internet-facing service.
    The user must supply a certificate already trusted by their phone for origin.
    This function performs no certificate installation, firewall, DNS or router change.
    """
    if not ack_private_lan:raise Refused('Explicit private-LAN trial acknowledgment required')
    for f in (certfile,keyfile):
        q=Path(f)
        if not q.is_file() or q.is_symlink():raise Refused('Supply existing certificate/key files, not symlinks')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile,keyfile)
    server=LocalUI(root,port,host=host,tls_context=context,public_origin=origin)
    print('Private foreground-only phone trial: '+origin,flush=True)
    print('Private local login code: '+server.token,flush=True)
    print('Keep this process running. No cloud push, background email service or provider writer is exposed.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
