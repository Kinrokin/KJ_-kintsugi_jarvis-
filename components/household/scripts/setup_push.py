#!/usr/bin/env python3
"""Generate VAPID only with explicit operator activation; installs nothing."""
import argparse,base64,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jarvis.runtime import *

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--contact',required=True);a=p.parse_args()
    if not sys.stdin.isatty() or input('Type ENABLE PRIVATE PUSH: ')!='ENABLE PRIVATE PUSH':raise Refused('Interactive permission required')
    c=load_config(a.config);original_config=digest(c)
    if not a.contact.startswith('mailto:') or any(x.isspace() for x in a.contact):raise Refused('Use a mailto contact for your VAPID sender')
    c['push']['enabled']=True;c['push']['contact']=a.contact;validate_config(c)
    from jarvis.notifications import WebPushSender
    if not WebPushSender.available():raise Refused('Optional pinned pywebpush dependency is not installed; no installation performed')
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    vault=SecretStore(Path(c['home'])/'secrets')
    with InstanceLock(c['home']):
        if digest(load_config(a.config))!=original_config:raise Refused('Config changed; review before enabling')
        if not vault.exists('vapid'):
            k=ec.generate_private_key(ec.SECP256R1());encode=lambda b:base64.urlsafe_b64encode(b).decode().rstrip('=')
            vault.put('vapid',{'private_der':encode(k.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())),
                              'public_key':encode(k.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))})
        atomic_private(a.config,canonical(c)+'\n')
    print('Transport enabled locally. Restart runtime; explicitly opt in from the trusted HTTPS phone page. Delivery remains unverified until handset testing.')
if __name__=='__main__':
    try:main()
    except (Refused,ImportError) as e:print(str(e),file=sys.stderr);sys.exit(1)
