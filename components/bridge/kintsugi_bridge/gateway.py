"""Bounded, durable admission and at-least-once delivery (local reference).

Two producer methods: submit_candidate and get_submission_status. Consumer
methods are a different role/interface, never part of the producer tool list.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import secrets
import uuid
from .auth import GATEWAY_AUDIENCE, IdentityVerifier
from .common import BridgeError, Clock, Store, bounded_json, canonical, digest, integer
from .schema import validate

@dataclass(frozen=True)
class Limits:
    rows: int = 2000                    # Includes retained receipt/idempotency rows.
    bytes: int = 8 * 1024 * 1024        # Canonical payloads, not disk allocation.
    producer_rows: int = 500
    producer_pending: int = 100
    producer_daily: int = 200
    producer_daily_bytes: int = 512 * 1024
    burst: int = 20
    refill_per_second: float = 0.2
    batch: int = 5
    response_bytes: int = 180000
    lease_seconds: int = 30
    max_attempts: int = 5
    ttl_seconds: int = 7 * 86400
    db_pages: int = 4096
    operator_events: int = 256

class Gateway:
    def __init__(self, path: Path, verifier: IdentityVerifier, clock: Clock | None = None,
                 limits: Limits | None = None, consumers: dict[str, str] | None = None):
        self.clock = clock or Clock()
        self.verifier = verifier
        self.limits = limits or Limits()
        self.consumers = dict(consumers or {"demo_queue": "pi-demo"})
        self.store = Store(path, max_pages=self.limits.db_pages)
        with self.store.connection(True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO meta VALUES('gateway_id',?)", (str(uuid.uuid4()),))
            db.execute("INSERT OR IGNORE INTO meta VALUES('paused','0')")
            db.execute("""CREATE TABLE IF NOT EXISTS messages(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, receipt TEXT NOT NULL UNIQUE,
                producer TEXT NOT NULL, queue_id TEXT NOT NULL, submission_key TEXT NOT NULL,
                payload BLOB NOT NULL, sha TEXT NOT NULL, size INTEGER NOT NULL,
                created REAL NOT NULL, expires REAL NOT NULL, status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, lease_hash TEXT, lease_until REAL,
                consumer TEXT, received_at REAL,
                UNIQUE(producer,queue_id,submission_key))""")
            db.execute("CREATE INDEX IF NOT EXISTS message_queue ON messages(queue_id,status,seq)")
            db.execute("""CREATE TABLE IF NOT EXISTS quotas(
                actor TEXT NOT NULL, queue_id TEXT NOT NULL, lane TEXT NOT NULL,
                tokens REAL NOT NULL, sampled REAL NOT NULL,
                PRIMARY KEY(actor,queue_id,lane))""")
            db.execute("""CREATE TABLE IF NOT EXISTS usage(
                actor TEXT NOT NULL, queue_id TEXT NOT NULL, day INTEGER NOT NULL,
                admitted INTEGER NOT NULL, bytes INTEGER NOT NULL,
                PRIMARY KEY(actor,queue_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                receipt TEXT NOT NULL, created REAL NOT NULL)""")
            self.gateway_id = db.execute("SELECT v FROM meta WHERE k='gateway_id'").fetchone()[0]

    def _identity(self, token: str, scope: str, role: str):
        identity = self.verifier.verify(token, GATEWAY_AUDIENCE, scope)
        if identity.role != role or identity.queue not in self.consumers:
            raise BridgeError("FORBIDDEN")
        if role == "consumer" and self.consumers[identity.queue] != identity.subject:
            raise BridgeError("FORBIDDEN")
        return identity

    def _rate(self, identity, lane: str) -> None:
        with self.store.connection(True) as db:
            now = self.clock.now()
            row = db.execute("SELECT tokens,sampled FROM quotas WHERE actor=? AND queue_id=? AND lane=?",
                             (identity.subject, identity.queue, lane)).fetchone()
            capacity = self.limits.burst
            tokens = capacity if row is None else min(capacity, row[0] + max(0, now-row[1]) * self.limits.refill_per_second)
            if tokens < 1:
                raise BridgeError("RATE_LIMIT")
            db.execute("INSERT OR REPLACE INTO quotas VALUES(?,?,?,?,?)",
                       (identity.subject, identity.queue, lane, tokens-1, max(now, row[1]) if row else now))

    def _event(self, db, kind: str, receipt: str, now: float) -> None:
        db.execute("INSERT INTO events(kind,receipt,created) VALUES(?,?,?)", (kind,receipt,now))
        # Bounded diagnostic ring, NOT an authoritative audit history.
        db.execute("DELETE FROM events WHERE seq NOT IN (SELECT seq FROM events ORDER BY seq DESC LIMIT ?)",
                   (self.limits.operator_events,))

    def pause(self, value: bool = True) -> None:
        """Trusted local operator only; not exposed as a producer tool."""
        with self.store.connection(True) as db:
            db.execute("UPDATE meta SET v=? WHERE k='paused'", ("1" if value else "0",))

    def submit_candidate(self, token: str, raw: bytes, *, fault: str | None = None) -> dict:
        identity = self._identity(token, "candidate:submit", "producer")
        self._rate(identity, "producer")   # Invalid authenticated submissions consume quota too.
        candidate, encoded = validate(raw)
        for source in candidate["source_refs"]:
            if (source["kind"], source["account_alias"]) not in identity.sources:
                raise BridgeError("SOURCE_ACCOUNT_FORBIDDEN")
        sha = digest(encoded)
        with self.store.connection(True) as db:
            # Fresh authentication and time AFTER acquiring the write transaction.
            identity = self._identity(token, "candidate:submit", "producer")
            now = self.clock.now()
            if db.execute("SELECT v FROM meta WHERE k='paused'").fetchone()[0] != "0":
                raise BridgeError("ADMISSION_PAUSED")
            old = db.execute("SELECT receipt,sha,status,expires FROM messages WHERE producer=? AND queue_id=? AND submission_key=?",
                             (identity.subject,identity.queue,candidate["idempotency_key"])).fetchone()
            if old is not None:
                if old["sha"] != sha:
                    raise BridgeError("IDEMPOTENCY_CONFLICT")
                return {"submission_id": old["receipt"], "status": self._visible(old, now)}
            count, used = db.execute("SELECT COUNT(*),COALESCE(SUM(size),0) FROM messages").fetchone()
            own, pending = db.execute("SELECT COUNT(*),COALESCE(SUM(CASE WHEN status IN ('stored','leased') THEN 1 ELSE 0 END),0) FROM messages WHERE producer=? AND queue_id=?",
                                      (identity.subject,identity.queue)).fetchone()
            if (count >= self.limits.rows or used + len(encoded) > self.limits.bytes
                or own >= self.limits.producer_rows or pending >= self.limits.producer_pending):
                raise BridgeError("CAPACITY_LIMIT")
            day = int(now // 86400)
            usage = db.execute("SELECT day,admitted,bytes FROM usage WHERE actor=? AND queue_id=?",
                               (identity.subject,identity.queue)).fetchone()
            # Backward wall-clock movement cannot reset the daily budget.
            if usage and day <= usage["day"]:
                day, admitted, daily_bytes = usage
            else:
                admitted, daily_bytes = 0,0
            if admitted >= self.limits.producer_daily or daily_bytes + len(encoded) > self.limits.producer_daily_bytes:
                raise BridgeError("DAILY_LIMIT")
            receipt = secrets.token_hex(16)
            db.execute("INSERT INTO messages(receipt,producer,queue_id,submission_key,payload,sha,size,created,expires,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (receipt,identity.subject,identity.queue,candidate["idempotency_key"],encoded,sha,len(encoded),now,now+self.limits.ttl_seconds,"stored"))
            db.execute("INSERT OR REPLACE INTO usage VALUES(?,?,?,?,?)",
                       (identity.subject,identity.queue,day,admitted+1,daily_bytes+len(encoded)))
            if fault == "before_commit":
                raise BridgeError("INJECTED_BEFORE_COMMIT")
        # The receipt is returned only after commit has returned successfully.
        if fault == "after_commit":
            raise BridgeError("INJECTED_RESPONSE_LOSS")
        return {"submission_id": receipt, "status": "stored"}

    @staticmethod
    def _visible(row, now: float) -> str:
        if row["status"] in {"stored","leased"}:
            return "expired" if row["expires"] <= now else "stored"
        return row["status"]

    def get_submission_status(self, token: str, receipt: str) -> dict:
        identity = self._identity(token, "candidate:status", "producer")
        self._rate(identity, "producer")
        if type(receipt) is not str or len(receipt) != 32:
            raise BridgeError("NOT_FOUND")
        with self.store.connection() as db:
            row = db.execute("SELECT receipt,status,expires FROM messages WHERE receipt=? AND producer=? AND queue_id=?",
                             (receipt,identity.subject,identity.queue)).fetchone()
        if row is None:
            raise BridgeError("NOT_FOUND")  # Same response for absent / another principal.
        return {"submission_id": row["receipt"], "status": self._visible(row, self.clock.now())}

    def _sweep(self, db, queue: str, now: float) -> None:
        # Bounded by configured total store capacity. No silent deletions.
        rows = db.execute("SELECT receipt,status,expires,attempts,lease_until FROM messages WHERE queue_id=? AND status IN ('stored','leased')",(queue,)).fetchall()
        for row in rows:
            if row["expires"] <= now:
                terminal = "expired"
            elif row["status"] == "leased" and row["lease_until"] <= now and row["attempts"] >= self.limits.max_attempts:
                terminal = "rejected"
            else:
                continue
            db.execute("UPDATE messages SET status=? WHERE receipt=?", (terminal,row["receipt"]))
            self._event(db, terminal, row["receipt"], now)

    def lease(self, token: str, limit: int = 1) -> list[dict]:
        identity = self._identity(token,"delivery:lease","consumer")
        integer(limit, 1, self.limits.batch)
        self._rate(identity,"lease")
        result, response_bytes = [], 0
        with self.store.connection(True) as db:
            identity = self._identity(token,"delivery:lease","consumer")
            now = self.clock.now()
            self._sweep(db,identity.queue,now)
            rows = db.execute("SELECT * FROM messages WHERE queue_id=? AND (status='stored' OR (status='leased' AND lease_until<=?)) ORDER BY seq LIMIT ?",
                              (identity.queue,now,limit)).fetchall()
            for row in rows:
                lease_key = secrets.token_urlsafe(32)
                # Corruption is quarantined rather than thrown at the parser forever.
                if digest(bytes(row["payload"])) != row["sha"]:
                    db.execute("UPDATE messages SET status='rejected' WHERE receipt=?",(row["receipt"],))
                    self._event(db,"storage_digest_mismatch",row["receipt"],now)
                    continue
                envelope = {"gateway_id":self.gateway_id,"queue_id":identity.queue,
                            "consumer_id":identity.subject,"producer_id":row["producer"],
                            "submission_id":row["receipt"],"sha256":row["sha"],
                            "payload":bytes(row["payload"]).decode("utf-8"),
                            "lease_token":lease_key,"lease_until":now+self.limits.lease_seconds}
                size = len(canonical(envelope))
                if response_bytes + size > self.limits.response_bytes:
                    break
                response_bytes += size
                db.execute("UPDATE messages SET status='leased',lease_hash=?,lease_until=?,consumer=?,attempts=attempts+1 WHERE receipt=?",
                           (digest(lease_key.encode()),now+self.limits.lease_seconds,identity.subject,row["receipt"]))
                result.append(envelope)
        return result

    def acknowledge(self, token: str, receipt: str, lease_token: str, sha: str,
                    disposition: str = "locally_received", *, fault: str | None = None) -> dict:
        identity = self._identity(token,"delivery:ack","consumer")
        if type(disposition) is not str or disposition not in {"locally_received","rejected"}:
            raise BridgeError("DISPOSITION")
        if any(type(x) is not str or len(x)>128 for x in (receipt,lease_token,sha)):
            raise BridgeError("ACK_FORMAT")
        self._rate(identity,"ack")
        with self.store.connection(True) as db:
            identity = self._identity(token,"delivery:ack","consumer")
            now = self.clock.now()
            row = db.execute("SELECT * FROM messages WHERE receipt=? AND queue_id=?",(receipt,identity.queue)).fetchone()
            if (row is None or row["consumer"] != identity.subject or row["sha"] != sha
                or not secrets.compare_digest(row["lease_hash"] or "",digest(lease_token.encode()))):
                raise BridgeError("ACK_MISMATCH")
            if row["status"] == disposition:
                return {"submission_id":receipt,"status":disposition}
            if row["status"] != "leased" or row["lease_until"] <= now or row["expires"] <= now:
                raise BridgeError("STALE_LEASE")
            db.execute("UPDATE messages SET status=?,received_at=? WHERE receipt=?",(disposition,now,receipt))
            if disposition == "rejected":
                self._event(db,"consumer_rejected",receipt,now)
            if fault == "before_commit":
                raise BridgeError("INJECTED_BEFORE_ACK")
        if fault == "after_commit":
            raise BridgeError("INJECTED_ACK_RESPONSE_LOSS")
        return {"submission_id":receipt,"status":disposition}

    def received_history(self, token: str, cursor: int = 0, limit: int = 5) -> dict:
        """Consumer-only recovery feed; never on the producer/MCP tool surface."""
        identity = self._identity(token,"delivery:history","consumer")
        integer(cursor,0,2**63-1)
        integer(limit,1,self.limits.batch)
        self._rate(identity,"history")
        with self.store.connection() as db:
            rows = db.execute("SELECT * FROM messages WHERE queue_id=? AND seq>? ORDER BY seq LIMIT ?",
                              (identity.queue,cursor,limit)).fetchall()
            if any(digest(bytes(r["payload"])) != r["sha"] for r in rows):
                raise BridgeError("HISTORY_CORRUPTED")
            end = rows[-1]["seq"] if rows else cursor
            more = db.execute("SELECT 1 FROM messages WHERE queue_id=? AND seq>? LIMIT 1",(identity.queue,end)).fetchone() is not None
            items = [{"gateway_id":self.gateway_id,"queue_id":identity.queue,
                      "consumer_id":identity.subject,"producer_id":r["producer"],
                      "submission_id":r["receipt"],"sha256":r["sha"],
                      "payload":bytes(r["payload"]).decode("utf-8")}
                     for r in rows if r["status"] == "locally_received"]
        response = {"items":items,"next_cursor":end,"more":more}
        if len(canonical(response)) > self.limits.response_bytes:
            raise BridgeError("RESPONSE_LIMIT")
        return response

    def operator_snapshot(self) -> dict:
        """Local diagnostic, not an agent-callable tool. Contains no payloads."""
        with self.store.connection() as db:
            counts = {r[0]:r[1] for r in db.execute("SELECT status,COUNT(*) FROM messages GROUP BY status")}
            events = [dict(r) for r in db.execute("SELECT kind,receipt,created FROM events ORDER BY seq")]
        return {"counts":counts,"events":events,"diagnostic_ring_limit":self.limits.operator_events}
