from __future__ import annotations
import contextlib, hashlib, json, math, sqlite3
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
UTC = timezone.utc

class Refused(ValueError):
    """Explicitly invalid or unauthorized operation; not an unknown provider outcome."""

class Conflict(Refused):
    pass

class UnknownOutcome(RuntimeError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def strict_json(text):
    if len(text) > 1_000_000:
        raise Refused('Input exceeds 1 MB')
    def pairs(p):
        d = {}
        for k, v in p:
            if k in d: raise Refused('Duplicate JSON key')
            d[k] = v
        return d
    def reject(x): raise Refused('Non-finite JSON number')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)

def iso(dt):
    if dt.tzinfo is None: raise Refused('Timezone required')
    return dt.astimezone(UTC).isoformat()

def instant(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None: raise Refused('Timezone required')
    return d.astimezone(UTC)

def now_utc(): return datetime.now(UTC)

def text(x, name='text', limit=4000):
    if not isinstance(x, str) or not x.strip() or len(x)>limit:
        raise Refused(f'Invalid {name}')
    return x

def integer(x, name='integer', minimum=None, maximum=None):
    if type(x) is not int or (minimum is not None and x < minimum) or (maximum is not None and x>maximum):
        raise Refused(f'Invalid {name}')
    return x

def keys(d, required, optional=()):
    if not isinstance(d, dict) or not set(required)<=d.keys() or d.keys()-set(required)-set(optional):
        raise Refused('Unexpected or missing fields')

def private_root(path):
    p=Path(path).expanduser().absolute()
    for a in [p,*p.parents]:
        if a.is_symlink() or (a/'.git').exists() or a.name.casefold() in {'kt','.git'}:
            raise Refused('State must be outside repositories, KT and symlink paths')
    p.mkdir(parents=True,exist_ok=True)
    try: p.chmod(0o700)
    except OSError: pass
    return p.resolve()

def connect(path):
    p=Path(path)
    if p.is_symlink(): raise Refused('Symlink database refused')
    c=sqlite3.connect(p,timeout=10,isolation_level=None)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA synchronous=FULL')
    c.execute('PRAGMA journal_mode=DELETE')
    try: p.chmod(0o600)
    except OSError: pass
    return c

@contextlib.contextmanager
def transaction(db):
    db.execute('BEGIN IMMEDIATE')
    try: yield
    except BaseException:
        db.execute('ROLLBACK');raise
    else: db.execute('COMMIT')

def local_instant(day, wall_time, tz, fold=0, gap='shift_forward'):
    """Select explicit fold; nonexistent times shift to first valid minute or are refused.
    No silent host-timezone dependence. Returns UTC.
    """
    z=ZoneInfo(tz); day=date.fromisoformat(day) if isinstance(day,str) else day
    wall=time.fromisoformat(wall_time)
    if wall.tzinfo or wall.second or wall.microsecond: raise Refused('HH:MM local time required')
    if fold not in (0,1) or gap not in {'shift_forward','reject'}: raise Refused('Invalid DST policy')
    naive=datetime.combine(day,wall)
    for minute in range(181):
        candidate=naive+timedelta(minutes=minute)
        aware=candidate.replace(tzinfo=z,fold=fold)
        back=aware.astimezone(UTC).astimezone(z).replace(tzinfo=None)
        if back==candidate: return aware.astimezone(UTC)
        if gap=='reject': raise Refused('Nonexistent local time')
    raise Refused('No valid local time in bounded DST search')
