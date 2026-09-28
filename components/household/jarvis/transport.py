"""Bounded provider HTTPS transport. No redirects, implicit proxies or arbitrary hosts."""
from __future__ import annotations
import urllib.request, urllib.error, urllib.parse, time
from .common import Refused, strict_json, canonical

class TransportFailure(Refused):
    def __init__(self, code):
        super().__init__(code); self.code=code

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw): raise TransportFailure('REDIRECT_REFUSED')

class HTTPS:
    def __init__(self, hosts, *, max_calls=250, timeout=15, deadline_seconds=240, opener=None):
        self.hosts=frozenset(hosts); self.max_calls=max_calls; self.calls=0
        self.timeout=timeout; self.deadline=time.monotonic()+deadline_seconds
        self.opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def request(self, method, url, *, token=None, form=None, data=None, headers=None):
        u=urllib.parse.urlsplit(url)
        if (u.scheme!='https' or u.hostname not in self.hosts or u.port not in (None,443)
            or u.username or u.password or u.fragment or any(c in url for c in '\r\n\\')):
            raise TransportFailure('DESTINATION_REFUSED')
        if method not in {'GET','POST'}: raise TransportFailure('METHOD_REFUSED')
        if self.calls>=self.max_calls or time.monotonic()>=self.deadline: raise TransportFailure('REQUEST_BUDGET_EXCEEDED')
        h={'Accept':'application/json'}; h.update(headers or {}); payload=None
        if token:
            if not isinstance(token,str) or any(c.isspace() for c in token): raise TransportFailure('TOKEN_MALFORMED')
            h['Authorization']='Bearer '+token
        if form is not None: payload=urllib.parse.urlencode(form).encode(); h['Content-Type']='application/x-www-form-urlencoded'
        if data is not None: payload=canonical(data).encode(); h['Content-Type']='application/json'
        req=urllib.request.Request(url,data=payload,headers=h,method=method); self.calls+=1
        try:
            with self.opener.open(req,timeout=max(.1,min(self.timeout,self.deadline-time.monotonic()))) as r:
                raw=r.read(2_000_001)
                if len(raw)>2_000_000: raise TransportFailure('RESPONSE_LIMIT')
                result=strict_json(raw.decode())
                if not isinstance(result,dict): raise TransportFailure('RESPONSE_SHAPE')
                return r.status,result
        except urllib.error.HTTPError as e:
            # Never expose provider body/URLs/cursors/credentials through exception logs.
            if u.hostname=='login.microsoftonline.com' and u.path=='/consumers/oauth2/v2.0/token':
                try:
                    b=strict_json(e.read(16385).decode());code=b.get('error')
                    if code in {'authorization_pending','slow_down','authorization_declined','expired_token','bad_verification_code'}:return e.code,{'error':code}
                except Exception:pass
            return e.code,{}
        except TransportFailure: raise
        except Exception: raise TransportFailure('TRANSPORT_INTERRUPTED') from None
