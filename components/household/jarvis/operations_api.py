"""Authenticated household-only operational routes. No grant, payment or calendar routes."""
from __future__ import annotations
from pathlib import Path
from .common import *
from .service_store import ServiceStore
from .secret_store import SecretStore
from .household import Household

GET_ROUTES={'/api/operations','/api/inbox','/api/push-config'}
POST_ROUTES={'/api/mail-review','/api/mail-dismiss','/api/push-subscribe','/api/push-unsubscribe','/api/network-pause','/api/measure'}

def get(c,path):
    home=Path(c['home']).expanduser();s=ServiceStore(home/'operations')
    try:
        if path=='/api/operations':
            r=s.overview([x['id'] for x in c['sources'] if x['enabled']],max_age=c['mail_poll_seconds']*2,heartbeat_max_age=c['worker_seconds']*3+30)
            r['push_health']=s.get('push_health','NOT_ENABLED');r['outbound_paused']=s.get('outbound_paused',False)
            r['phone_acceptance']='NOT_ESTABLISHED';return r
        if path=='/api/inbox':
            count=s.db.execute("SELECT count(*) FROM mail WHERE state='REVIEW_CANDIDATE'").fetchone()[0]
            return {'items':s.mail_rows(),'remaining_candidates':count,'page_limit':100,'basis':'untrusted metadata, not accepted obligations','no_body_or_attachments':True}
        if path=='/api/push-config':
            v=SecretStore(home/'secrets');configured=c['push']['enabled'] and v.exists('vapid')
            return {'enabled':bool(configured),'public_key':v.get('vapid')['public_key'] if configured else None,
                    'preview':'Generic private reminder; never routine titles or email details','transport_health':s.get('push_health','UNKNOWN')}
        raise Refused('No such operational route')
    finally:s.close()

def post(c,path,b):
    home=Path(c['home']).expanduser();s=ServiceStore(home/'operations')
    try:
        if path=='/api/network-pause':
            keys(b,set());s.set('outbound_paused',True)
            return {'paused':'THIS_RUNTIME_NETWORK_ONLY','already_submitted':'may complete','independent_tools':'not controlled'}
        if path=='/api/push-subscribe':
            keys(b,{'subscription','consent'})
            if b['consent'] is not True or not c['push']['enabled']:raise Refused('Explicit enabled push consent required')
            from .notifications import subscribe
            return {'subscription_id':subscribe(s,b['subscription']),'status':'REGISTERED_NOT_DELIVERY_PROOF'}
        if path=='/api/push-unsubscribe':
            keys(b,{'subscription_id'});from .notifications import unsubscribe
            unsubscribe(s,text(b['subscription_id']));return {'status':'UNSUBSCRIBED','already_submitted':'may still arrive'}
        if path in {'/api/mail-review','/api/mail-dismiss'}:
            keys(b,{'id','metadata_hash'}, {'outcome','deadline'} if path=='/api/mail-review' else set())
            row=s.mail_item(text(b['id']))
            if b['metadata_hash']!=digest(row['metadata']):raise Conflict('Message changed since review; refresh the candidate')
            if path=='/api/mail-dismiss':s.set_mail_state(b['id'],'DISMISSED');return {'status':'DISMISSED_LOCAL_ONLY'}
            if row['state']=='SOURCE_REMOVED':raise Conflict('Source no longer in selected scope; review original mailbox')
            outcome=text(b.get('outcome'),'outcome',1000);deadline=b.get('deadline')
            if deadline is not None:instant(deadline)
            h=Household(home/'household')
            try:
                oid=h.import_email(row['source'],row['provider_id'],{'title':row['metadata']['subject'] or 'Review email','outcome':outcome,'deadline':deadline})
            finally:h.close()
            s.set_mail_state(b['id'],'IMPORTED')
            return {'obligation_id':oid,'status':'CANDIDATE_NOT_ACCEPTED','provider_effects':0}
        if path=='/api/measure':
            keys(b,{'kind','value','event_id'});h=Household(home/'household')
            try:h.measure(b['kind'],b['value'],b['event_id'])
            finally:h.close()
            return {'status':'USER_RECORDED_NOT_INDEPENDENTLY_VERIFIED'}
        raise Refused('No such operational route')
    finally:s.close()

def push_ack(c,b):
    keys(b,{'id','token','phase'})
    from .notifications import ack
    s=ServiceStore(Path(c['home']).expanduser()/'operations')
    try:return ack(s,text(b['id'],limit=100),text(b['token'],limit=200),b['phase'])
    finally:s.close()
