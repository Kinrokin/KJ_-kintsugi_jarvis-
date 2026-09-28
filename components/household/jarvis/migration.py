from __future__ import annotations
import shutil, sqlite3, json, uuid
from pathlib import Path
from .common import *

def backup_household(household,destination):
    dest=Path(destination)
    if dest.exists() or dest.is_symlink():raise Refused('Backup destination must be new')
    db=sqlite3.connect(dest)
    try:household.db.backup(db)
    finally:db.close()
    return {'path':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'contains_authority':False}

def restore_household(snapshot,new_root,authority):
    """Never restores/overwrites the external authority/intent store. Always pauses it."""
    p=Path(snapshot)
    if p.is_symlink() or not p.is_file():raise Refused('Invalid snapshot')
    target=Path(new_root).absolute()
    if target.exists():raise Refused('Restore into a NEW directory; do not overwrite live state')
    if target==authority.root or target in authority.root.parents or authority.root in target.parents:raise Refused('Authority must be outside restore target')
    authority.pause()
    src=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise Refused('Snapshot integrity failed')
        row=src.execute("SELECT v FROM meta WHERE k='schema'").fetchone()
        if not row or row[0]!='3.1':raise Refused('Explicit migration required for this schema')
        root=private_root(target);dst=connect(root/'household.sqlite3')
        try:src.backup(dst)
        finally:dst.close()
    finally:src.close()
    return {'restored':str(target),'write_state':'PAUSED','authority_restored':False,'reconciliation_required':True}

def inspect_v2_database(path):
    """Read-only legacy migration inventory. No imported permission or assumed completion."""
    p=Path(path)
    if p.is_symlink() or not p.is_file():raise Refused('Invalid V2 source')
    db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'tickets' not in tables:raise Refused('Not a recognized V2 ledger')
        tickets=[{'legacy_id':r['id'],'reported_action_state':r['status'],'body':json.loads(r['body']),
                  'obligation_state':'UNKNOWN','trust':'LEGACY_UNVERIFIED'} for r in db.execute('SELECT * FROM tickets')]
        return {'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'candidate_records':tickets,
                'permissions_imported':0,'provider_receipts_promoted':0,'review_required':True}
    finally:db.close()
