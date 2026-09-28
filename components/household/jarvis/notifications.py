"""Opt-in Web Push delivery. Generic encrypted previews; no human completion side effects.
Real transport is optional pywebpush 2.5.0, never installed automatically.
Accepted by a push provider != displayed on a phone != read != obligation complete.
"""
from __future__ import annotations
import base64, json, secrets, urllib.parse, importlib.util, hmac
from datetime import timedelta
from .common import *

PUSH_HOSTS={'fcm.googleapis.com','updates.push.services.mozilla.com'}

def decode_key(v,size):
    if not isinstance(v,str) or len(v)>200 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=' for c in v):raise Refused('Invalid push key')
    try:b=base64.urlsafe_b64decode(v+'='*((-len(v))%4))
    except Exception:raise Refused('Invalid push key') from None
    if len(b)!=size:raise Refused('Invalid push key length')
    return b

def validate_subscription(value):
    keys(value,{'endpoint','keys'},{'expirationTime'})
    u=urllib.parse.urlsplit(text(value['endpoint'],'push endpoint',2000))
    if u.scheme!='https' or u.hostname not in PUSH_HOSTS or u.port not in (None,443) or u.username or u.password or u.fragment or u.query:
        raise Refused('Push destination outside tested provider allowlist')
    if not u.path.startswith(('/fcm/send/','/wp/','/wpush/')) or '\\' in u.path:raise Refused('Push endpoint path refused')
    keys(value['keys'],{'p256dh','auth'})
    if decode_key(value['keys']['p256dh'],65)[0]!=4:raise Refused('Invalid P-256 point encoding')
    decode_key(value['keys']['auth'],16)
    return {'endpoint':value['endpoint'],'keys':dict(value['keys'])}

def subscribe(store,value,now=None):
    now=now or now_utc();v=validate_subscription(value);sid=digest(v)
    with transaction(store.db):
        count=store.db.execute('SELECT count(*) FROM subscriptions WHERE active=1').fetchone()[0]
        if count>=5 and not store.db.execute('SELECT 1 FROM subscriptions WHERE id=? AND active=1',(sid,)).fetchone():raise Refused('At most five private devices may subscribe')
        store.db.execute('INSERT OR REPLACE INTO subscriptions VALUES(?,?,1,?)',(sid,canonical(v),iso(now)))
    return sid

def unsubscribe(store,sid):
    with transaction(store.db):
        store.db.execute('UPDATE subscriptions SET active=0 WHERE id=?',(sid,))
        store.db.execute("UPDATE notifications SET status='CANCELED' WHERE sub_id=? AND status='QUEUED'",(sid,))

def queue_event(store,event,now=None):
    now=now or now_utc();count=0
    if instant(event['expires'])<=now:return 0
    for sub in store.db.execute('SELECT * FROM subscriptions WHERE active=1').fetchall():
        if instant(sub['created'])>instant(event['created']):continue  # No historical reminders on opt-in.
        nid=digest({'event':event['id'],'sub':sub['id']});token=secrets.token_urlsafe(32)
        with transaction(store.db):
            count+=store.db.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,?,?,?,?,?,NULL,NULL)',
                (nid,'routine',event['id'],sub['id'],'QUEUED',iso(now),event['expires'],digest(token),token)).rowcount
    return count

def ack(store,nid,token,phase,now=None):
    now=now or now_utc()
    if phase not in {'displayed','opened'}:raise Refused('Acknowledgment phase refused')
    with transaction(store.db):
        r=store.db.execute('SELECT * FROM notifications WHERE id=?',(nid,)).fetchone()
        if not r or not isinstance(token,str) or len(token)>200 or not hmac.compare_digest(r['ack_hash'],digest(token)):
            raise Refused('Invalid notification acknowledgment')
        if r['status'] not in {'DISPATCHED','PUSH_ACCEPTED','UNKNOWN_DELIVERY','CLIENT_REPORTED_DISPLAYED','CLIENT_REPORTED_OPENED'}:
            raise Refused('Notification not dispatched')
        if now>instant(r['expires'])+timedelta(days=7):raise Refused('Acknowledgment expired')
        if r['status']=='CLIENT_REPORTED_OPENED':return {'status':r['status'],'completion_changed':False}
        status='CLIENT_REPORTED_OPENED' if phase=='opened' else 'CLIENT_REPORTED_DISPLAYED'
        store.db.execute('UPDATE notifications SET status=?,client_report=? WHERE id=?',(status,iso(now),nid))
    return {'status':status,'completion_changed':False}

class WebPushSender:
    def __init__(self,secret_store,contact):self.secrets=secret_store;self.contact=contact
    @staticmethod
    def available():return importlib.util.find_spec('pywebpush') is not None
    def send(self,subscription,payload,ttl):
        validate_subscription(subscription)
        if not self.contact.startswith('mailto:') or '\n' in self.contact:raise Refused('VAPID contact must be an approved mailto address')
        from pywebpush import webpush,WebPushException
        import requests
        class StrictSession(requests.Session):
            def request(self,method,url,**kwargs):
                u=urllib.parse.urlsplit(url)
                if method.upper()!='POST' or u.scheme!='https' or u.hostname not in PUSH_HOSTS or u.port not in (None,443) or u.username or u.password:
                    raise Refused('Push transport destination refused')
                kwargs['allow_redirects']=False;kwargs['verify']=True
                return super().request(method,url,**kwargs)
        with StrictSession() as session:
            session.trust_env=False
            try:
                response=webpush(subscription_info=subscription,data=canonical(payload),
                    vapid_private_key=self.secrets.get('vapid')['private_der'],vapid_claims={'sub':self.contact},
                    requests_session=session,timeout=10,ttl=max(1,min(ttl,3600)),
                    headers={'Topic':payload['id'][:32]},verbose=False)
                return response.status_code
            except WebPushException as e:
                return getattr(e,'status_code',None) or (e.response.status_code if e.response is not None else 0)

def dispatch(store,sender,now=None,limit=8,eligible=None):
    now=now or now_utc();out=[]
    if store.get('outbound_paused',False):return [{'status':'OUTBOUND_PAUSED'}]
    for raw in store.db.execute("SELECT * FROM notifications WHERE status='QUEUED' ORDER BY created LIMIT ?",(limit,)).fetchall():
        r=dict(raw)
        with transaction(store.db):
            if store.get('outbound_paused',False):break
            sub=store.db.execute('SELECT * FROM subscriptions WHERE id=? AND active=1',(r['sub_id'],)).fetchone()
            if not sub or instant(r['expires'])<=now or (eligible is not None and not eligible(r)):
                store.db.execute("UPDATE notifications SET status='EXPIRED_OR_DISABLED' WHERE id=?",(r['id'],));continue
            if not store.db.execute("UPDATE notifications SET status='DISPATCHED',attempted=? WHERE id=? AND status='QUEUED'",(iso(now),r['id'])).rowcount:continue
        payload={'version':1,'id':r['id'],'ack_token':r['ack_token'],'expires':r['expires']}
        try:code=sender.send(strict_json(sub['body']),payload,int((instant(r['expires'])-now).total_seconds()))
        except Exception:code=0
        status='PUSH_ACCEPTED' if code in (200,201,202) else 'ENDPOINT_EXPIRED' if code in (404,410) else 'UNKNOWN_DELIVERY' if code==0 or code>=500 else 'PUSH_REJECTED'
        with transaction(store.db):
            # A fast client acknowledgment must not be overwritten by a slow send return.
            store.db.execute("UPDATE notifications SET status=? WHERE id=? AND status='DISPATCHED'",(status,r['id']))
            if code in (404,410):store.db.execute('UPDATE subscriptions SET active=0 WHERE id=?',(r['sub_id'],))
        out.append({'id':r['id'],'status':status})
    return out
