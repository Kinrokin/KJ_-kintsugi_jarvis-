"""Strict version-one candidate contract; strings NEVER become authority."""
from __future__ import annotations
from datetime import datetime, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
from .common import BridgeError, bounded_json, canonical, exact, integer, string

KINDS = {"schedule_change", "deadline", "billing_observation", "task_candidate"}
URGENCY = {"LOW", "NORMAL", "HIGH", "CRITICAL"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@=+/-]{0,255}\Z")
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,95}\Z")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")

def identifier(value: object) -> str:
    value = string(value, 256)
    if not ID.fullmatch(value):
        raise BridgeError("INVALID_ID")
    return value

def instant(value: object) -> datetime:
    value = string(value, 40)
    if not STAMP.fullmatch(value):
        raise BridgeError("TIMESTAMP_REQUIRED")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BridgeError("INVALID_TIME") from None
    if result.utcoffset() is None:
        raise BridgeError("TIMESTAMP_REQUIRED")
    return result

def timezone(value: object) -> ZoneInfo:
    value = string(value, 64)
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise BridgeError("TIMEZONE_UNAVAILABLE") from None

def validate(raw: bytes) -> tuple[dict, bytes]:
    c = bounded_json(raw)
    exact(c, {"version", "idempotency_key", "candidate_type", "source_refs",
              "observed_at", "urgency_hint", "claims"})
    if type(c["version"]) is not int or c["version"] != 1:
        raise BridgeError("UNSUPPORTED_VERSION")
    if type(c["idempotency_key"]) is not str or not KEY.fullmatch(c["idempotency_key"]):
        raise BridgeError("INVALID_KEY")
    if type(c["candidate_type"]) is not str or c["candidate_type"] not in KINDS:
        raise BridgeError("CANDIDATE_TYPE")
    if type(c["urgency_hint"]) is not str or c["urgency_hint"] not in URGENCY:
        raise BridgeError("URGENCY_TYPE")
    instant(c["observed_at"])
    refs = c["source_refs"]
    if type(refs) is not list or not 1 <= len(refs) <= 4:
        raise BridgeError("SOURCE_LIMIT")
    seen = set()
    for ref in refs:
        exact(ref, {"kind", "account_alias", "object_id"})
        if type(ref["kind"]) is not str or ref["kind"] not in {"gmail", "outlook", "drive"}:
            raise BridgeError("SOURCE_KIND")
        identifier(ref["account_alias"])
        identifier(ref["object_id"])
        if (ref["kind"],ref["account_alias"],ref["object_id"]) in seen:
            raise BridgeError("DUPLICATE_SOURCE")
        seen.add((ref["kind"],ref["account_alias"],ref["object_id"]))
    claims = c["claims"]
    fields = {
        "schedule_change": {"title", "summary", "local_date", "local_time", "time_zone", "reported_instant"},
        "deadline": {"title", "summary", "due_at", "time_zone"},
        "billing_observation": {"title", "summary", "amount_minor", "currency", "due_at"},
        "task_candidate": {"title", "summary"},
    }
    exact(claims, fields[c["candidate_type"]])
    string(claims["title"], 200)
    string(claims["summary"], 2048, empty=True)
    if c["candidate_type"] == "schedule_change":
        string(claims["local_date"], 10)
        string(claims["local_time"], 5)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", claims["local_date"]) or not re.fullmatch(r"\d{2}:\d{2}", claims["local_time"]):
            raise BridgeError("LOCAL_TIME_FORMAT")
        tz = timezone(claims["time_zone"])
        stamp = instant(claims["reported_instant"])
        local = stamp.astimezone(tz)
        # Roundtrip binds local civil time to absolute time, including DST folds.
        if (local.strftime("%Y-%m-%d") != claims["local_date"]
            or local.strftime("%H:%M") != claims["local_time"]
            or local.second != 0 or local.microsecond != 0):
            raise BridgeError("TIME_CONTRADICTION")
    elif c["candidate_type"] == "deadline":
        instant(claims["due_at"])
        timezone(claims["time_zone"])
    elif c["candidate_type"] == "billing_observation":
        integer(claims["amount_minor"], 0, 100_000_000)
        if type(claims["currency"]) is not str or claims["currency"] != "USD":
            raise BridgeError("CURRENCY_UNSUPPORTED")
        if claims["due_at"] is not None:
            instant(claims["due_at"])
    encoded = canonical(c)
    if len(encoded) > 32768:
        raise BridgeError("CANONICAL_BODY_LIMIT")
    return c, encoded

def example_candidate(key: str = "school-change-0001") -> dict:
    """Entirely synthetic, not a real appointment or obligation."""
    return {"version": 1, "idempotency_key": key,
            "candidate_type": "schedule_change", "urgency_hint": "HIGH",
            "observed_at": "2026-09-25T12:00:00-05:00",
            "source_refs": [{"kind": "gmail", "account_alias": "demo_mail", "object_id": "demo-message-1"}],
            "claims": {"title": "DEMO: school pickup", "summary": "Synthetic source claim; not verified.",
                       "local_date": "2026-09-26", "local_time": "14:15",
                       "time_zone": "America/Chicago", "reported_instant": "2026-09-26T19:15:00Z"}}
