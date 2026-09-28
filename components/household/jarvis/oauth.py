"""Refresh only the user's locally consented OAuth credential; no ChatGPT token reuse."""
from __future__ import annotations
from datetime import timedelta
from .common import *
from .transport import HTTPS

SCOPES={'google':'https://www.googleapis.com/auth/gmail.readonly',
        'microsoft':'https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read offline_access'}
ENDPOINTS={'google':'https://oauth2.googleapis.com/token',
           'microsoft':'https://login.microsoftonline.com/consumers/oauth2/v2.0/token'}

class RefreshCredential:
    def __init__(self,store,name,provider,http=None):self.store=store;self.name=name;self.provider=provider;self.http=http
    def token(self,now=None):
        now=now or now_utc();c=self.store.get(self.name)
        if c.get('provider')!=self.provider:raise Refused('OAuth credential provider mismatch')
        if c.get('access_token') and c.get('expires_at') and instant(c['expires_at'])>now+timedelta(minutes=2):return c['access_token']
        if not c.get('refresh_token'):raise Refused('Reauthorization required')
        form={'client_id':text(c['client_id']),'refresh_token':text(c['refresh_token']), 'grant_type':'refresh_token'}
        if self.provider=='google' and c.get('client_secret'):form['client_secret']=c['client_secret']
        if self.provider=='microsoft':form['scope']=SCOPES['microsoft']
        http=self.http or HTTPS({'oauth2.googleapis.com','login.microsoftonline.com'},max_calls=2)
        status,body=http.request('POST',ENDPOINTS[self.provider],form=form)
        if status!=200 or not body.get('access_token'):raise Refused('OAuth refresh failed; reconnect locally')
        expiry=integer(body.get('expires_in'),'token lifetime',60,172800)
        c['access_token']=body['access_token'];c['expires_at']=iso(now+timedelta(seconds=expiry))
        if body.get('refresh_token'):c['refresh_token']=body['refresh_token']
        self.store.put(self.name,c);return c['access_token']
