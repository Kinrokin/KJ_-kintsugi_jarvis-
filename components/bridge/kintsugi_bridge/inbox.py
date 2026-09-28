"""Separate private staging inbox. It cannot write to the JARVIS authority store.

A transport acknowledgement says ONLY that this inbox durably stored a record.
No candidate is promoted to a household obligation or trusted preference here.
"""
from __future__ import annotations
from pathlib import Path
import html
import math
from .common import BridgeError, Clock, Store, bounded_json, canonical, digest, exact, string
from .schema import validate

BASE_FIELDS = {"gateway_id","queue_id","consumer_id","producer_id","submission_id","sha256","payload"}

class LocalInbox:
    def __init__(self, path: Path, gateway_id: str, queue_id: str, consumer_id: str,
                 source_bindings: dict[tuple[str,str,str],str], *, rows: int = 1000,
                 bytes_limit: int = 4*1024*1024, clock: Clock | None = None):
        self.store = Store(path, max_pages=2048)
        self.gateway_id,self.queue_id,self.consumer_id = gateway_id,queue_id,consumer_id
        self.bindings = dict(source_bindings)
        self.rows,self.bytes_limit = rows,bytes_limit
        self.clock = clock or Clock()
        with self.store.connection(True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
            for k,v in (("gateway",gateway_id),("queue",queue_id),("consumer",consumer_id),
                        ("recovering","0"),("history_cursor","0"),("history_complete","0")):
                db.execute("INSERT OR IGNORE INTO meta VALUES(?,?)",(k,v))
            actual = dict(db.execute("SELECT k,v FROM meta"))
            if (actual["gateway"],actual["queue"],actual["consumer"]) != (gateway_id,queue_id,consumer_id):
                raise BridgeError("INBOX_BINDING_MISMATCH")
            db.execute("""CREATE TABLE IF NOT EXISTS inbox(
                submission_id TEXT PRIMARY KEY, sha TEXT NOT NULL, producer TEXT NOT NULL,
                payload BLOB NOT NULL, bytes INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
                received REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS candidates(
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_key TEXT NOT NULL,
                claim_sha TEXT NOT NULL, claims BLOB NOT NULL, kind TEXT NOT NULL,
                state TEXT NOT NULL, UNIQUE(source_key,claim_sha))""")
            db.execute("""CREATE TABLE IF NOT EXISTS quarantine(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, submission_id TEXT NOT NULL,
                digest TEXT NOT NULL, reason TEXT NOT NULL, received REAL NOT NULL)""")

    def _check(self, envelope: dict, history: bool = False) -> tuple[dict,bytes,str,str]:
        exact(envelope, BASE_FIELDS if history else BASE_FIELDS | {"lease_token","lease_until"})
        for f in BASE_FIELDS-{"payload"}:
            string(envelope[f],256)
        if (envelope["gateway_id"],envelope["queue_id"],envelope["consumer_id"]) != (self.gateway_id,self.queue_id,self.consumer_id):
            raise BridgeError("DELIVERY_BINDING_MISMATCH")
        if not history:
            string(envelope["lease_token"],128)
            if (type(envelope["lease_until"]) not in (int,float)
                or not math.isfinite(envelope["lease_until"])):
                raise BridgeError("LEASE_FORMAT")
        payload = string(envelope["payload"],32768).encode("utf-8")
        if digest(payload) != envelope["sha256"]:
            raise BridgeError("DELIVERY_DIGEST_MISMATCH")
        candidate, encoded = validate(payload)
        if encoded != payload:
            raise BridgeError("NONCANONICAL_DELIVERY")
        resolved_sources = []
        for src in candidate["source_refs"]:
            mapping = (envelope["producer_id"],src["kind"],src["account_alias"])
            if mapping not in self.bindings:
                raise BridgeError("SOURCE_BINDING_UNKNOWN")
            resolved_sources.append([src["kind"],self.bindings[mapping],src["object_id"]])
        source_key = digest(canonical(sorted(resolved_sources)))
        claim_sha = digest(canonical({"candidate_type":candidate["candidate_type"],"claims":candidate["claims"]}))
        return candidate,encoded,source_key,claim_sha

    def _insert(self, db, envelope, checked, *, restored: bool = False) -> dict:
        c,encoded,source_key,claim_sha = checked
        old = db.execute("SELECT sha,candidate_id,producer FROM inbox WHERE submission_id=?",(envelope["submission_id"],)).fetchone()
        if old:
            if old["sha"] != envelope["sha256"] or old["producer"] != envelope["producer_id"]:
                raise BridgeError("RECEIPT_REUSED")
            return {"state":"duplicate","candidate_id":old["candidate_id"]}
        count,total = db.execute("SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM inbox").fetchone()
        if count >= self.rows or total + len(encoded)>self.bytes_limit:
            raise BridgeError("INBOX_CAPACITY")
        matching = db.execute("SELECT id FROM candidates WHERE source_key=? AND claim_sha=?",(source_key,claim_sha)).fetchone()
        if matching:
            cid = matching[0]
            if restored:
                db.execute("UPDATE candidates SET state='RESTORE_REVIEW' WHERE id=?",(cid,))
        else:
            conflicts = db.execute("SELECT id FROM candidates WHERE source_key=?",(source_key,)).fetchall()
            state = "RESTORE_REVIEW" if restored else "CONTRADICTED" if conflicts else "UNVERIFIED"
            if conflicts:
                db.execute("UPDATE candidates SET state=? WHERE source_key=?",(state,source_key))
            cur = db.execute("INSERT INTO candidates(source_key,claim_sha,claims,kind,state) VALUES(?,?,?,?,?)",
                             (source_key,claim_sha,canonical(c["claims"]),c["candidate_type"],state))
            cid = cur.lastrowid
        db.execute("INSERT INTO inbox VALUES(?,?,?,?,?,?,?)",
                   (envelope["submission_id"],envelope["sha256"],envelope["producer_id"],encoded,len(encoded),cid,self.clock.now()))
        return {"state":"staged","candidate_id":cid}

    def accept(self, envelope: dict, *, fault: str | None = None) -> dict:
        checked = self._check(envelope)
        with self.store.connection(True) as db:
            if db.execute("SELECT v FROM meta WHERE k='recovering'").fetchone()[0] != "0":
                raise BridgeError("RESTORE_RECONCILIATION_REQUIRED")
            if self.clock.now() >= envelope["lease_until"]:
                raise BridgeError("DELIVERY_LEASE_EXPIRED")
            result = self._insert(db,envelope,checked)
            if fault == "before_commit":
                raise BridgeError("INJECTED_BEFORE_LOCAL_COMMIT")
        if fault == "after_commit":
            raise BridgeError("INJECTED_AFTER_LOCAL_COMMIT")
        return result

    def quarantine(self, receipt: str, sha: str, reason: str) -> None:
        # Only finite internal codes; do not persist raw rejected content.
        reason = reason if reason in {"DELIVERY_DIGEST_MISMATCH","NONCANONICAL_DELIVERY",
                                     "SOURCE_BINDING_UNKNOWN","SCHEMA_REJECTED"} else "SCHEMA_REJECTED"
        with self.store.connection(True) as db:
            db.execute("INSERT INTO quarantine(submission_id,digest,reason,received) VALUES(?,?,?,?)",
                       (receipt[:64],sha[:64],reason,self.clock.now()))
            db.execute("DELETE FROM quarantine WHERE seq NOT IN (SELECT seq FROM quarantine ORDER BY seq DESC LIMIT 128)")

    def enter_restore_reconciliation(self) -> None:
        """Mandatory immediately after SUPPORTED restore, before any new intake.
        Raw file replacement cannot be detected reliably by this method alone.
        """
        with self.store.connection(True) as db:
            db.execute("UPDATE meta SET v='1' WHERE k='recovering'")
            db.execute("UPDATE meta SET v='0' WHERE k IN ('history_cursor','history_complete')")
            db.execute("UPDATE candidates SET state='RESTORE_REVIEW'")

    def recovery_cursor(self) -> int:
        with self.store.connection() as db:
            return int(db.execute("SELECT v FROM meta WHERE k='history_cursor'").fetchone()[0])

    def reconcile_page(self, page: dict, *, fault: bool = False) -> None:
        exact(page,{"items","next_cursor","more"})
        if type(page["items"]) is not list or len(page["items"])>5 or type(page["more"]) is not bool:
            raise BridgeError("HISTORY_FORMAT")
        if type(page["next_cursor"]) is not int or page["next_cursor"]<0:
            raise BridgeError("HISTORY_CURSOR")
        if len(canonical(page))>180000:
            raise BridgeError("RESPONSE_LIMIT")
        checked = [self._check(item,True) for item in page["items"]]
        with self.store.connection(True) as db:
            meta = dict(db.execute("SELECT k,v FROM meta"))
            if meta["recovering"]!="1" or page["next_cursor"]<int(meta["history_cursor"]):
                raise BridgeError("RESTORE_STATE")
            for item, data in zip(page["items"],checked):
                self._insert(db,item,data,restored=True)
            if fault:
                raise BridgeError("INJECTED_PAGE_FAILURE")
            db.execute("UPDATE meta SET v=? WHERE k='history_cursor'",(str(page["next_cursor"]),))
            db.execute("UPDATE meta SET v=? WHERE k='history_complete'",("0" if page["more"] else "1",))

    def finish_restore_reconciliation(self) -> None:
        with self.store.connection(True) as db:
            if db.execute("SELECT v FROM meta WHERE k='history_complete'").fetchone()[0]!="1":
                raise BridgeError("RESTORE_INCOMPLETE")
            db.execute("UPDATE meta SET v='0' WHERE k='recovering'")
        # RESTORE_REVIEW candidates are deliberately NOT promoted.

    def summary(self) -> dict:
        with self.store.connection() as db:
            return {"receipts":db.execute("SELECT COUNT(*) FROM inbox").fetchone()[0],
                    "candidates":db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0],
                    "states":{r[0]:r[1] for r in db.execute("SELECT state,COUNT(*) FROM candidates GROUP BY state")},
                    "recovering":db.execute("SELECT v FROM meta WHERE k='recovering'").fetchone()[0]=="1"}

    def private_html(self) -> str:
        """Static local review, escaped text; no scripts, remote images, or links."""
        rows=[]
        with self.store.connection() as db:
            for r in db.execute("SELECT id,claims,state FROM candidates ORDER BY id LIMIT 100"):
                c=bounded_json(bytes(r["claims"]))
                rows.append(f'<li><strong>{html.escape(c["title"])}</strong><p>{html.escape(c["summary"])}</p><small>{html.escape(r["state"])}</small></li>')
        return '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'none\'"><title>Private unverified candidates</title><h1>Private unverified candidates</h1><ul>'+''.join(rows)+'</ul>'
