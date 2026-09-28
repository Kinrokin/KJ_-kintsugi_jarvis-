"""Separately stored health monitor reference; no notification sender attached.

HMAC authenticates a report from an enrolled reporter. It does NOT prove that
reported health is truthful. Enrollments are operator-provisioned, not self-issued.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import hmac
import secrets
import uuid
from .auth import MONITOR_AUDIENCE
from .common import BridgeError, Clock, Store, bounded_json, canonical, exact, integer, string

REPORT_FIELDS={"node_id","enrollment_epoch","sequence","sent_at","progress_sequence","coverage"}

def sign_report(key:bytes,body:dict)->bytes:
    return canonical({"report":body,"mac":hmac.new(key,canonical(body),hashlib.sha256).hexdigest()})

class Monitor:
    def __init__(self,path:Path,verifier,clock:Clock|None=None,*,missing_after:int=90,stalled_after:int=90):
        self.store=Store(path,max_pages=1024)
        self.verifier,self.clock=verifier,clock or Clock()
        self.missing_after,self.stalled_after=missing_after,stalled_after
        self._keys={}
        with self.store.connection(True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS nodes(
                node TEXT PRIMARY KEY, epoch TEXT NOT NULL, key_hash TEXT NOT NULL,
                sequence INTEGER NOT NULL, received REAL, progress INTEGER NOT NULL,
                progress_at REAL, coverage TEXT NOT NULL, state TEXT NOT NULL, enrolled REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS alerts(
                id INTEGER PRIMARY KEY AUTOINCREMENT, node TEXT NOT NULL,
                state TEXT NOT NULL, text TEXT NOT NULL, created REAL NOT NULL,
                delivery TEXT NOT NULL)""")
    def enroll(self,node_id:str)->tuple[str,bytes]:
        """Trusted operator only. Rotation intentionally invalidates old reports."""
        string(node_id,64)
        key,epoch=secrets.token_bytes(32),str(uuid.uuid4())
        with self.store.connection(True) as db:
            count=db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            exists=db.execute("SELECT 1 FROM nodes WHERE node=?",(node_id,)).fetchone()
            if count>=16 and not exists:
                raise BridgeError("ENROLLMENT_LIMIT")
            db.execute("INSERT OR REPLACE INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (node_id,epoch,hashlib.sha256(key).hexdigest(),0,None,0,None,"UNKNOWN","AWAITING_REPORT",self.clock.now()))
        self._keys[node_id]=key
        return epoch,key
    def load_key(self,node_id:str,key:bytes)->None:
        """Trusted secret-store injection after restart; never from a cloud candidate."""
        with self.store.connection() as db:
            row=db.execute("SELECT key_hash FROM nodes WHERE node=?",(node_id,)).fetchone()
        if row is None or not secrets.compare_digest(row[0],hashlib.sha256(key).hexdigest()):
            raise BridgeError("KEY_MISMATCH")
        self._keys[node_id]=key
    def _transition(self,db,node,state,now):
        prior=db.execute("SELECT state FROM nodes WHERE node=?",(node,)).fetchone()[0]
        if state!=prior:
            text="JARVIS bridge monitoring needs attention." if state!="HEALTHY" else "JARVIS bridge monitoring is reporting healthy."
            db.execute("INSERT INTO alerts(node,state,text,created,delivery) VALUES(?,?,?,?,?)",
                       (node,state,text,now,"NOT_SENT"))
            db.execute("DELETE FROM alerts WHERE id NOT IN (SELECT id FROM alerts ORDER BY id DESC LIMIT 256)")
            db.execute("UPDATE nodes SET state=? WHERE node=?",(state,node))
    def _state(self,row,now):
        if row["received"] is None:
            return "UNREACHABLE" if now-row["enrolled"]>=self.missing_after else "AWAITING_REPORT"
        if now<row["received"]:
            return "CLOCK_UNVERIFIED"
        if now-row["received"]>=self.missing_after:
            return "UNREACHABLE"
        if row["progress_at"] is None or now-row["progress_at"]>=self.stalled_after:
            return "STALLED"
        return "HEALTHY" if row["coverage"]=="COMPLETE" else "DEGRADED"
    def receive(self,token:str,raw:bytes)->dict:
        identity=self.verifier.verify(token,MONITOR_AUDIENCE,"health:report")
        if identity.role!="reporter":
            raise BridgeError("FORBIDDEN")
        wrapper=bounded_json(raw,2048)
        exact(wrapper,{"report","mac"})
        body=exact(wrapper["report"],REPORT_FIELDS)
        for name in ("node_id","enrollment_epoch","coverage"):
            string(body[name],64)
        if body["node_id"]!=identity.subject or body["coverage"] not in {"COMPLETE","PARTIAL","UNKNOWN"}:
            raise BridgeError("REPORT_BINDING")
        integer(body["sequence"],1,2**63-1)
        integer(body["progress_sequence"],0,2**63-1)
        integer(body["sent_at"],0,2**63-1)
        string(wrapper["mac"],64)
        key=self._keys.get(body["node_id"])
        if key is None or not secrets.compare_digest(hmac.new(key,canonical(body),hashlib.sha256).hexdigest(),wrapper["mac"]):
            raise BridgeError("REPORT_AUTHENTICATION")
        with self.store.connection(True) as db:
            identity=self.verifier.verify(token,MONITOR_AUDIENCE,"health:report")
            now=self.clock.now()
            row=db.execute("SELECT * FROM nodes WHERE node=?",(body["node_id"],)).fetchone()
            if row is None or row["epoch"]!=body["enrollment_epoch"]:
                raise BridgeError("REPORT_EPOCH")
            if body["sequence"]<=row["sequence"] or body["progress_sequence"]<row["progress"]:
                raise BridgeError("REPORT_REPLAY")
            if not now-60<=body["sent_at"]<=now+5:
                raise BridgeError("REPORT_STALE")
            if row["received"] is not None and now-row["received"]<5:
                raise BridgeError("REPORT_RATE_LIMIT")
            progressed=body["progress_sequence"]>row["progress"]
            db.execute("UPDATE nodes SET sequence=?,received=?,progress=?,progress_at=?,coverage=? WHERE node=?",
                       (body["sequence"],now,body["progress_sequence"],now if progressed else row["progress_at"],body["coverage"],body["node_id"]))
            updated=db.execute("SELECT * FROM nodes WHERE node=?",(body["node_id"],)).fetchone()
            state=self._state(updated,now)
            self._transition(db,body["node_id"],state,now)
        return {"received":True}
    def evaluate(self)->dict:
        """Operator/independent watchdog call, never a Spark producer tool."""
        states={}
        with self.store.connection(True) as db:
            now=self.clock.now()
            for row in db.execute("SELECT * FROM nodes").fetchall():
                state=self._state(row,now)
                self._transition(db,row["node"],state,now)
                states[row["node"]]=state
        return states
    def alert_outbox(self)->list[dict]:
        with self.store.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM alerts ORDER BY id")]
