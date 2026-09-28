"""Identity port plus LOCAL TEST FIXTURE, deliberately NOT an OAuth server.

Production needs a reviewed OAuth resource-server verifier. No network listener
or public-deployment flag exists here. In-process adversarial code can bypass
Python objects; process/OS isolation is an external deployment requirement.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
import hashlib
import secrets
import threading
from .common import BridgeError, Clock

GATEWAY_AUDIENCE = "urn:kintsugi:bridge:local-review"
MONITOR_AUDIENCE = "urn:kintsugi:monitor:local-review"

@dataclass(frozen=True)
class Identity:
    subject: str
    role: str
    queue: str
    scopes: frozenset[str]
    sources: frozenset[tuple[str, str]] = frozenset()

class IdentityVerifier(Protocol):
    def verify(self, token: str, audience: str, scope: str) -> Identity: ...

class FixtureIdentityVerifier:
    """Opaque, expiring, revocable test credentials. In-memory, no real identity.

    Instance replacement invalidates credentials rather than resurrecting them.
    Do not put this class behind a public server or use it to represent Robert.
    """
    def __init__(self, clock: Clock):
        self.clock = clock
        self._entries = {}
        self._lock = threading.RLock()
    def issue(self, identity: Identity, audience: str = GATEWAY_AUDIENCE,
              ttl: float = 3600) -> str:
        if ttl <= 0 or ttl > 86400:
            raise ValueError("fixture ttl outside bound")
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._entries[hashlib.sha256(token.encode()).hexdigest()] = (
                identity, audience, self.clock.now() + ttl)
        return token
    def revoke(self, token: str) -> None:
        with self._lock:
            self._entries.pop(hashlib.sha256(token.encode()).hexdigest(), None)
    def verify(self, token: str, audience: str, scope: str) -> Identity:
        if type(token) is not str or not 20 <= len(token) <= 256:
            raise BridgeError("UNAUTHENTICATED")
        with self._lock:
            entry = self._entries.get(hashlib.sha256(token.encode()).hexdigest())
            if entry is None or entry[1] != audience or self.clock.now() >= entry[2]:
                raise BridgeError("UNAUTHENTICATED")
            if scope not in entry[0].scopes:
                raise BridgeError("FORBIDDEN")
            return entry[0]
