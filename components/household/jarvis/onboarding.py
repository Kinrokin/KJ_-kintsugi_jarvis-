"""Personal read-only OAuth onboarding, invoked only from an interactive operator terminal.
Never imports ChatGPT connector credentials or accepts instructions from mail content.
"""
from __future__ import annotations
import base64,hashlib,secrets,time,urllib.parse
from datetime import timedelta
from .common import Refused,now_utc,iso,integer,text
from .transport import HTTPS
from .oauth import SCOPES

def google_authorization(client_id,redirect_uri):
    u=urllib.parse.urlsplit(redirect_uri)
    if u.scheme!='http' or u.hostname!='127.0.0.1' or not u.port or u.path!='/callback':raise Refused('OAuth uses an explicit loopback callback only')
    verifier=secrets.token_urlsafe(64);state=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    q={'client_id':text(client_id),'redirect_uri':redirect_uri,'response_type':'code','scope':SCOPES['google'],
       'access_type':'offline','prompt':'consent','state':state,'code_challenge':challenge,'code_challenge_method':'S256'}
    return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(q),'state':state,'verifier':verifier}

def token_record(provider,client_id,body,client_secret=None,now=None):
    now=now or now_utc()
    if not body.get('access_token') or not body.get('refresh_token'):raise Refused('Provider did not return a renewable credential; no account configured')
    c={'provider':provider,'client_id':text(client_id),'access_token':text(body['access_token']),'refresh_token':text(body['refresh_token']),
       'expires_at':iso(now+timedelta(seconds=integer(body.get('expires_in'),'lifetime',60,172800)))}
    if client_secret:c['client_secret']=client_secret
    return c

def google_exchange(client_id,client_secret,code,redirect_uri,verifier,http=None):
    http=http or HTTPS({'oauth2.googleapis.com'},max_calls=1)
    form={'client_id':client_id,'code':code,'redirect_uri':redirect_uri,'code_verifier':verifier,'grant_type':'authorization_code'}
    if client_secret:form['client_secret']=client_secret
    status,b=http.request('POST','https://oauth2.googleapis.com/token',form=form)
    if status!=200:raise Refused('OAuth exchange refused; no credential stored')
    return token_record('google',client_id,b,client_secret)

def microsoft_device_start(client_id,http=None):
    http=http or HTTPS({'login.microsoftonline.com'},max_calls=1)
    status,b=http.request('POST','https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode',form={'client_id':client_id,'scope':SCOPES['microsoft']})
    if status!=200:raise Refused('Device authorization unavailable for this application/account')
    integer(b.get('interval',5),'poll interval',1,60);integer(b.get('expires_in'),'device lifetime',30,1800)
    for k in ('device_code','user_code'):text(b.get(k),k,4000)
    u=urllib.parse.urlsplit(b.get('verification_uri',''))
    if u.scheme!='https' or u.hostname not in {'microsoft.com','www.microsoft.com','login.microsoftonline.com'} or u.username or u.password:raise Refused('Unexpected verification destination')
    return b

def microsoft_device_finish(client_id,device,http=None,*,sleep=time.sleep,clock=time.monotonic):
    http=http or HTTPS({'login.microsoftonline.com'},max_calls=360,deadline_seconds=1800)
    stop=clock()+device['expires_in'];interval=device.get('interval',5)
    while clock()<stop:
        sleep(interval)
        status,b=http.request('POST','https://login.microsoftonline.com/consumers/oauth2/v2.0/token',form={
            'client_id':client_id,'device_code':device['device_code'],'grant_type':'urn:ietf:params:oauth:grant-type:device_code'})
        if status==200:return token_record('microsoft',client_id,b)
        # Transport only returns sanitized OAuth protocol error codes for this endpoint.
        err=b.get('error')
        if err=='authorization_pending':continue
        if err=='slow_down':interval=min(interval+5,60);continue
        raise Refused('Device authorization declined or expired')
    raise Refused('Device authorization expired')

def identify(credential,http=None):
    provider=credential['provider'];token=credential['access_token']
    if provider=='google':
        http=http or HTTPS({'gmail.googleapis.com'},max_calls=1)
        status,b=http.request('GET','https://gmail.googleapis.com/gmail/v1/users/me/profile',token=token)
        identity=b.get('emailAddress')
    elif provider=='microsoft':
        http=http or HTTPS({'graph.microsoft.com'},max_calls=1)
        status,b=http.request('GET','https://graph.microsoft.com/v1.0/me?$select=id',token=token)
        identity=b.get('id')
    else:raise Refused('Provider refused')
    if status!=200:raise Refused('Cannot verify the connected account')
    return text(identity,'verified account',500)
