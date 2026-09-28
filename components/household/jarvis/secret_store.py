"""Host-side secrets. Windows DPAPI CurrentUser; POSIX owner-only files.
Not a defense against the same OS principal/root. No secrets in config, reports or logs.
"""
from __future__ import annotations
import base64, ctypes, json, os, re, stat, tempfile
from pathlib import Path
from .common import private_root, Refused, canonical, strict_json

def _dpapi(blob, decrypt=False):
    from ctypes import wintypes
    class BLOB(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buf=ctypes.create_string_buffer(blob); inp=BLOB(len(blob),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte))); out=BLOB()
    crypt=ctypes.windll.crypt32
    ptr=ctypes.POINTER(BLOB)
    crypt.CryptProtectData.argtypes=[ptr,wintypes.LPCWSTR,ptr,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ptr]
    crypt.CryptProtectData.restype=wintypes.BOOL
    crypt.CryptUnprotectData.argtypes=[ptr,ctypes.POINTER(wintypes.LPWSTR),ptr,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ptr]
    crypt.CryptUnprotectData.restype=wintypes.BOOL
    ctypes.windll.kernel32.LocalFree.argtypes=[ctypes.c_void_p]
    ctypes.windll.kernel32.LocalFree.restype=ctypes.c_void_p
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    # CRYPTPROTECT_UI_FORBIDDEN; CurrentUser, not LocalMachine.
    desc=None if decrypt else 'Kintsugi local credential'
    ok=fn(ctypes.byref(inp),desc,None,None,None,1,ctypes.byref(out))
    if not ok: raise Refused('OS credential protection failed')
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:ctypes.windll.kernel32.LocalFree(out.pbData)

class SecretStore:
    def __init__(self,root): self.root=private_root(root)
    def _path(self,name):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',name): raise Refused('Invalid secret reference')
        p=self.root/(name+'.secret')
        if p.is_symlink(): raise Refused('Secret symlink refused')
        return p
    @property
    def protection(self): return 'WINDOWS_DPAPI_CURRENT_USER' if os.name=='nt' else 'OWNER_ONLY_FILES_NOT_ENCRYPTED'
    def put(self,name,value):
        raw=canonical(value).encode()
        if len(raw)>65536: raise Refused('Secret value too large')
        if os.name=='nt': raw=b'DPAPI1:'+base64.b64encode(_dpapi(raw))
        else: raw=b'POSIX1:'+raw
        p=self._path(name);fd,tmp=tempfile.mkstemp(prefix='.secret-',dir=self.root)
        try:
            with os.fdopen(fd,'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
            os.chmod(tmp,0o600);os.replace(tmp,p)
        finally:
            if Path(tmp).exists():Path(tmp).unlink()
    def get(self,name):
        p=self._path(name)
        if not p.is_file():raise Refused('Required local secret unavailable')
        if os.name!='nt' and (p.stat().st_mode & 0o077):raise Refused('Secret permissions must be owner-only')
        raw=p.read_bytes()
        if len(raw)>100000:raise Refused('Secret file too large')
        if raw.startswith(b'DPAPI1:'):
            if os.name!='nt':raise Refused('Windows-protected secret cannot be loaded on this host')
            raw=_dpapi(base64.b64decode(raw[7:]),decrypt=True)
        elif raw.startswith(b'POSIX1:') and os.name!='nt':raw=raw[7:]
        else:raise Refused('Unrecognized secret envelope')
        return strict_json(raw.decode())
    def exists(self,name): return self._path(name).is_file()
    def delete(self,name): self._path(name).unlink(missing_ok=True)
