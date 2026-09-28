"""A separate local authority/intent store, not a global identity service.
A production proposer must have neither this module's management interface, the
operator password, nor access to the authority filesystem. Same-OS-user/root
compromise and joint rollback of all stores are explicitly outside this boundary.
"""
from __future__ import annotations
import hashlib, hmac, secrets, uuid, json
from datetime import timedelta
from .common import *

class Authority:
    def __init__(self, root):
        self.root=private_root(root);self.db=connect(self.root/'authority.sqlite3')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS config(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS grants(id TEXT PRIMARY KEY,body TEXT NOT NULL,signature TEXT NOT NULL,used INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS intents(opkey TEXT PRIMARY KEY,target TEXT NOT NULL,proposal TEXT NOT NULL,grant_id TEXT UNIQUE NOT NULL,status TEXT NOT NULL,receipt TEXT);
        CREATE TABLE IF NOT EXISTS locks(target TEXT PRIMARY KEY,opkey TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY,body TEXT NOT NULL);
        ''')
        # Legacy intents remain unbound and quarantined; never infer their provider.
        columns={r['name'] for r in self.db.execute('PRAGMA table_info(intents)')}
        if 'provider_binding' not in columns:
            self.db.execute('ALTER TABLE intents ADD COLUMN provider_binding TEXT')
    def close(self): self.db.close()
    def _cfg(self,k):
        row=self.db.execute('SELECT v FROM config WHERE k=?',(k,)).fetchone();return row['v'] if row else None
    def _set(self,k,v):self.db.execute('INSERT OR REPLACE INTO config VALUES(?,?)',(k,str(v)))
    def _log(self,kind,body): self.db.execute('INSERT INTO audit(body) VALUES(?)',(canonical({'at':iso(now_utc()),'kind':kind,'details':body}),))
    def initialize(self,password):
        if not isinstance(password,str) or len(password)<14: raise Refused('Use at least 14 characters for the local operator password')
        with transaction(self.db):
            if self._cfg('password_hash'):raise Refused('Authority already initialized')
            salt=secrets.token_bytes(16)
            h=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()
            for k,v in {'salt':salt.hex(),'password_hash':h,'key':secrets.token_hex(32),'epoch':1,'paused':1,'generation':secrets.token_hex(16),'principal':'local_operator'}.items():self._set(k,v)
    def authenticate(self,password):
        h=self._cfg('password_hash')
        if not h or not isinstance(password,str):raise Refused('Local operator authentication required')
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(self._cfg('salt')),n=16384,r=8,p=1).hex()
        if not hmac.compare_digest(h,actual):raise Refused('Local operator authentication failed')
        return self._cfg('principal')
    def restart_boundary(self):
        """Called on each broker startup. Old grants invalid; reconciliation still permitted."""
        with transaction(self.db):
            if not self._cfg('epoch'):raise Refused('Initialize authority first')
            self._set('epoch',int(self._cfg('epoch'))+1);self._set('paused',1)
            self._set('generation',secrets.token_hex(16))
            self._log('STARTUP_QUARANTINE',{})
    def pause(self):
        # Anyone able to request a pause may reduce authority, never expand it.
        with transaction(self.db):
            self._set('paused',1);self._set('epoch',int(self._cfg('epoch'))+1);self._log('PAUSED',{})
    def resume(self,password):
        self.authenticate(password)
        with transaction(self.db):
            if self.db.execute("SELECT 1 FROM intents WHERE status IN ('DISPATCH_INTENT','UNKNOWN_EXTERNAL')").fetchone():
                raise Refused('Reconcile uncertain dispatches before resuming writes')
            self._set('paused',0);self._log('RESUMED',{})
    def grant(self,proposal,prepared_context,password,*,now=None,ttl_seconds=600,sharing=None):
        now=now or now_utc();principal=self.authenticate(password)
        integer(ttl_seconds,'ttl',1,3600)
        keys(prepared_context,{'audience_hash','provider','target','risk','adapter_contract','provider_binding'})
        body={'id':str(uuid.uuid4()),'proposal_hash':digest(proposal),'context':prepared_context,
              'epoch':int(self._cfg('epoch')),'generation':self._cfg('generation'),'principal':principal,
              'not_before':iso(now),'expires':iso(now+timedelta(seconds=ttl_seconds)),
              'delegation':'case_specific','sharing':sharing}
        signature=hmac.new(bytes.fromhex(self._cfg('key')),canonical(body).encode(),hashlib.sha256).hexdigest()
        with transaction(self.db):
            if self._cfg('paused')!='0':raise Refused('Broker paused; resume after reconciliation first')
            self.db.execute('INSERT INTO grants VALUES(?,?,?,0)',(body['id'],canonical(body),signature))
            self._log('GRANTED',{'id':body['id'],'proposal_hash':body['proposal_hash'],'principal':principal})
        return {'body':body,'signature':signature}
    def inspect_grant(self,token,proposal,context,now):
        keys(token,{'body','signature'});body=token['body']
        expected=hmac.new(bytes.fromhex(self._cfg('key')),canonical(body).encode(),hashlib.sha256).hexdigest()
        if not isinstance(token['signature'],str) or not hmac.compare_digest(expected,token['signature']):raise Refused('Invalid authority signature')
        row=self.db.execute('SELECT * FROM grants WHERE id=?',(body.get('id'),)).fetchone()
        if not row or row['body']!=canonical(body) or row['signature']!=token['signature'] or row['used']:raise Refused('Unknown, modified, or consumed grant')
        if self._cfg('paused')!='0' or body['epoch']!=int(self._cfg('epoch')) or body['generation']!=self._cfg('generation'):raise Refused('Paused or revoked authority')
        if not instant(body['not_before'])<=now<instant(body['expires']):raise Refused('Grant not valid at this time')
        if body['proposal_hash']!=digest(proposal) or body['context']!=context:raise Refused('Approved action or integration context changed')
        return body
    def reserve(self,token,proposal,context,now):
        """Single durable commit boundary for grant consumption + dispatch intent + local target lock.
        Revocation AFTER this boundary cannot guarantee a request will not complete.
        """
        with transaction(self.db):
            # Sample the clock AFTER acquiring the write transaction, not before a slow lock.
            checked_at=now() if callable(now) else now
            b=self.inspect_grant(token,proposal,context,checked_at)
            key=proposal['operation_key'];target=proposal['target']
            if self.db.execute('SELECT 1 FROM intents WHERE opkey=?',(key,)).fetchone():raise Refused('Operation already attempted; reconcile, do not retry')
            if self.db.execute('SELECT 1 FROM locks WHERE target=?',(target,)).fetchone():raise Refused('Target has an unresolved writer')
            self.db.execute('UPDATE grants SET used=1 WHERE id=?',(b['id'],))
            self.db.execute('INSERT INTO intents(opkey,target,proposal,grant_id,status,receipt,provider_binding) VALUES(?,?,?,?,?,NULL,?)',
                            (key,target,canonical(proposal),b['id'],'DISPATCH_INTENT',canonical(context['provider_binding'])))
            self.db.execute('INSERT INTO locks VALUES(?,?)',(target,key))
            self._log('DISPATCH_BOUNDARY',{'operation_key':key,'checked_at':iso(checked_at),'provider_binding':context['provider_binding']})
    def intent(self,key):
        row=self.db.execute('SELECT * FROM intents WHERE opkey=?',(key,)).fetchone()
        if not row:raise Refused('No dispatch intent')
        return dict(row)
    def finish(self,key,status,receipt):
        if status not in {'UNKNOWN_EXTERNAL','PROVIDER_VERIFIED','REJECTED_NO_EFFECT'}:raise Refused('Invalid adapter result')
        with transaction(self.db):
            self.db.execute('UPDATE intents SET status=?,receipt=? WHERE opkey=?',(status,canonical(receipt),key))
            if status!='UNKNOWN_EXTERNAL':self.db.execute('DELETE FROM locks WHERE opkey=?',(key,))
            self._log(status,{'operation_key':key})
    def report(self):
        return {'principal_type':'local_password_holder_NOT_remote_identity_proof','paused':self._cfg('paused')!='0',
                'epoch':self._cfg('epoch'),'intents':[dict(r) for r in self.db.execute('SELECT opkey,target,status FROM intents')],
                'scope':'single_authority_database; not cross-host/global enforcement'}
