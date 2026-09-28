"""Durable operations state; separate from authority and household completion."""
from __future__ import annotations
import json, secrets
from datetime import timedelta
from .common import *

class ServiceStore:
    def __init__(self,root):
        self.root=private_root(root);self.db=connect(self.root/'operations.sqlite3')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, binding TEXT NOT NULL, cursor TEXT, status TEXT NOT NULL, checked_at TEXT, as_of TEXT, error TEXT, scope TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mail(id TEXT PRIMARY KEY,source TEXT NOT NULL,provider_id TEXT NOT NULL,body TEXT NOT NULL,state TEXT NOT NULL,seen_at TEXT NOT NULL,UNIQUE(source,provider_id));
        CREATE TABLE IF NOT EXISTS subscriptions(id TEXT PRIMARY KEY,body TEXT NOT NULL,active INTEGER NOT NULL,created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,topic TEXT NOT NULL,object_id TEXT NOT NULL,sub_id TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,expires TEXT NOT NULL,ack_hash TEXT NOT NULL,ack_token TEXT NOT NULL,attempted TEXT,client_report TEXT,UNIQUE(topic,object_id,sub_id));
        CREATE TABLE IF NOT EXISTS worker_events(seq INTEGER PRIMARY KEY,at TEXT NOT NULL,kind TEXT NOT NULL,code TEXT NOT NULL);
        ''')
    def close(self):self.db.close()
    def set(self,k,v):self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(k,canonical(v)))
    def get(self,k,default=None):
        r=self.db.execute('SELECT v FROM settings WHERE k=?',(k,)).fetchone();return strict_json(r['v']) if r else default
    def source(self,name):
        r=self.db.execute('SELECT * FROM sources WHERE id=?',(name,)).fetchone();return dict(r) if r else None
    def begin_source(self,name,binding,scope,now):
        with transaction(self.db):
            r=self.source(name)
            if r and (r['binding']!=canonical(binding) or r['scope']!=canonical(scope)):
                raise Refused('SOURCE_BINDING_CHANGED_USE_NEW_SOURCE_ID')
            self.db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,NULL,?,NULL,NULL,NULL,?)',(name,canonical(binding),'NEVER_SYNCED',canonical(scope)))
            self.db.execute('UPDATE sources SET status=?,checked_at=?,error=NULL WHERE id=?',('SYNCING',iso(now),name))
    def commit_source(self,name,items,cursor,now,*,full=False):
        if not isinstance(cursor,str) or not cursor:raise Refused('Final cursor required')
        with transaction(self.db):
            if not self.source(name):raise Refused('Source not initialized')
            for item in items:
                mid=item['id'];oid=digest({'source':name,'message':mid})
                if item.get('removed'):
                    self.db.execute("UPDATE mail SET state='SOURCE_REMOVED',seen_at=? WHERE id=?",(iso(now),oid));continue
                body=dict(item,trust='EXTERNAL_METADATA_NOT_AUTHORITY',source_id=name)
                r=self.db.execute('SELECT state FROM mail WHERE id=?',(oid,)).fetchone()
                state=r['state'] if r and r['state'] in {'DISMISSED','IMPORTED'} else 'REVIEW_CANDIDATE'
                self.db.execute('INSERT OR REPLACE INTO mail VALUES(?,?,?,?,?,?)',(oid,name,mid,canonical(body),state,iso(now)))
            self.db.execute("UPDATE sources SET cursor=?,status='COMPLETE',checked_at=?,as_of=?,error=NULL WHERE id=?",(cursor,iso(now),iso(now),name))
    def fail_source(self,name,code,now):
        self.db.execute("UPDATE sources SET status='DEGRADED',checked_at=?,error=? WHERE id=?",(iso(now),code,name))
    def mail_rows(self,limit=100):
        return [dict(id=r['id'],state=r['state'],metadata=strict_json(r['body'])) for r in self.db.execute("SELECT * FROM mail WHERE state='REVIEW_CANDIDATE' ORDER BY seen_at DESC,id LIMIT ?",(limit,))]
    def set_mail_state(self,oid,state):
        if state not in {'DISMISSED','IMPORTED'}:raise Refused('Mail state refused')
        if not self.db.execute('UPDATE mail SET state=? WHERE id=?',(state,oid)).rowcount:raise Refused('Mail item not found')
    def mail_item(self,oid):
        r=self.db.execute('SELECT * FROM mail WHERE id=?',(oid,)).fetchone()
        if not r:raise Refused('Mail item not found')
        return dict(r,metadata=strict_json(r['body']))
    def event(self,kind,code,now=None):
        # Codes only. No exception bodies, source content, tokens or HTTP URLs.
        self.db.execute('INSERT INTO worker_events(at,kind,code) VALUES(?,?,?)',(iso(now or now_utc()),kind,code))
    def overview(self,required,now=None,max_age=1800,heartbeat_max_age=120):
        now=now or now_utc();sources=[]
        for name in required:
            r=self.source(name)
            age=(now-instant(r['as_of'])).total_seconds() if r and r['as_of'] else None
            sources.append({'id':name,'status':r['status'] if r else 'NOT_CONFIGURED','as_of':r['as_of'] if r else None,
                            'covered':bool(r and r['status']=='COMPLETE' and age is not None and 0<=age<=max_age),
                            'scope':strict_json(r['scope']) if r else None,'error_code':r['error'] if r else None})
        hb=self.get('heartbeat'); age=(now-instant(hb['at'])).total_seconds() if hb else None
        return {'worker':'RUNNING_RECENTLY' if age is not None and 0<=age<=heartbeat_max_age else 'STALE_OR_NOT_RUNNING',
                'heartbeat_age_seconds':age,'sources':sources,'all_required_sources_covered':bool(required) and all(r['covered'] for r in sources),
                'all_clear':False,'note':'No global all-clear from metadata coverage. No independent watchdog unless separately deployed.',
                'notifications':dict(self.db.execute('SELECT status,count(*) FROM notifications GROUP BY status').fetchall())}
    def retention_plan(self,days,now=None):
        integer(days,'days',7,3650);cut=iso((now or now_utc())-timedelta(days=days))
        rows=list(self.db.execute("SELECT id FROM mail WHERE state IN ('DISMISSED','SOURCE_REMOVED') AND seen_at<?",(cut,)))
        return {'mail_ids':[r['id'] for r in rows],'cutoff':cut,'deletes_active_obligations':False,'automatic':False}
    def apply_retention(self,plan):
        # Only closed source metadata. Never delete household records, grants or uncertain intents.
        with transaction(self.db):
            for oid in plan['mail_ids']:
                self.db.execute("DELETE FROM mail WHERE id=? AND state IN ('DISMISSED','SOURCE_REMOVED') AND seen_at<?",(oid,plan['cutoff']))
