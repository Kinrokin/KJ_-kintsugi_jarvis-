"""Bounded parsing, clocks and local durable stores. No network operations."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator
import hashlib
import json
import math
import sqlite3
import time

class BridgeError(Exception):
    """Safe public error code. Never include rejected data or credentials."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

class Clock:
    def now(self) -> float:
        return time.time()
    def monotonic(self) -> float:
        return time.monotonic()

class FakeClock(Clock):
    def __init__(self, timestamp: float = 1790424000.0):
        self.timestamp = timestamp
    def now(self) -> float:
        return self.timestamp
    def monotonic(self) -> float:
        return self.timestamp
    def advance(self, seconds: float) -> None:
        self.timestamp += seconds

def canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise BridgeError("INVALID_JSON") from None

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def bounded_json(raw: bytes, maximum: int = 32768, depth_limit: int = 8) -> dict:
    """Reject before parsing, including excessive nesting and duplicate members."""
    if type(raw) is not bytes or len(raw) > maximum:
        raise BridgeError("BODY_LIMIT")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise BridgeError("INVALID_UTF8") from None
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > depth_limit:
                raise BridgeError("DEPTH_LIMIT")
        elif char in "]}":
            depth -= 1
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BridgeError("DUPLICATE_FIELD")
            result[key] = value
        return result
    def invalid_number(value):
        raise BridgeError("INVALID_NUMBER")
    try:
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_constant=invalid_number, parse_float=invalid_number)
    except (ValueError, RecursionError):
        raise BridgeError("INVALID_JSON") from None
    if type(value) is not dict:
        raise BridgeError("OBJECT_REQUIRED")
    return value

def exact(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise BridgeError("FIELD_SET")
    return value

def string(value: object, maximum: int, *, empty: bool = False) -> str:
    if type(value) is not str or (not empty and not value) or len(value) > maximum:
        raise BridgeError("STRING_LIMIT")
    # Newlines and tabs are data; forbid other controls and Unicode surrogates.
    if any((ord(c) < 32 and c not in "\n\r\t") or ord(c) == 127
           or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise BridgeError("INVALID_CHARACTER")
    return value

def integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise BridgeError("INTEGER_RANGE")
    return value

class Store:
    """One local disk per instance, not a distributed database or trust anchor.

    DELETE+EXTRA avoids an unbounded WAL and requests durable commits. Actual
    power-loss guarantees still depend on OS/filesystem/device correctness.
    """
    def __init__(self, path: Path | str, *, max_pages: int = 4096):
        self.path = Path(path)
        self.max_pages = max_pages
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise BridgeError("SYMLINK_STATE")
        if not self.path.exists():
            with self.path.open("xb"):
                pass
            self.path.chmod(0o600)
    @contextmanager
    def connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path, timeout=0.25, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("PRAGMA synchronous=EXTRA")
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA trusted_schema=OFF")
            con.execute("PRAGMA cache_size=-2048")
            con.execute("PRAGMA max_page_count=%d" % int(self.max_pages))
            if write:
                con.execute("BEGIN IMMEDIATE")
            yield con
            if write:
                con.commit()
        except sqlite3.Error as exc:
            if con.in_transaction:
                con.rollback()
            name = getattr(exc, "sqlite_errorname", "")
            raise BridgeError("STORE_BUSY" if "BUSY" in name or "LOCKED" in name
                              else "STORE_UNAVAILABLE") from None
        except BaseException:
            if con.in_transaction:
                con.rollback()
            raise
        finally:
            con.close()
    def backup(self, destination: Path) -> None:
        if destination.exists():
            raise BridgeError("BACKUP_EXISTS")
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connection() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
        destination.chmod(0o600)
