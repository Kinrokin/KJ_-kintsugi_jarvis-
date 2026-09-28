# KINTSUGI Bridge 1.0 — Local Review Candidate

**A separate runnable candidate-delivery test harness. Not a replacement JARVIS,
not an installed Spark connector, and not an Internet-facing MCP server.**

This package implements the first local bridge increment and several local
failure/abuse controls from the capability-and-delivery specification. It keeps
V3.2 intact. No dependency download, network connection, permanent service,
account change, notification send or model call is performed by its demo/tests.
Python 3.11+ with SQLite and an IANA timezone database is required. The tested
interpreter/OS is recorded in `evidence/test_results.json`. Windows/Pi are untested.

## Start here

From this extracted directory:

```sh
python scripts/verify_manifest.py
python scripts/run_tests.py
python -m kintsugi_bridge demo
```

Use `python3` when that is your installed Python command. The demo creates and
removes synthetic temporary state. It does not read your Gmail, other databases,
credentials, routine state, or financial information. Do not install packages
merely to run this. If the timezone database is absent, stop and record that
prerequisite rather than silently guessing offsets or installing software.

## What exists

- Strict bounded candidate parsing and explicit source/identity bindings.
- Two producer application operations, with a draft future MCP tool manifest.
- Local-only fixture credentials, audience/scope/role checks, expiry/revocation.
- A durable SQLite gateway queue, opaque owner-scoped receipts, idempotency,
  quota/capacity checks, non-destructive leases and explicit acknowledgements.
- A separate private inbox that stages unverified claims, correlates exactly
  matching source sets, and retains conflicting claims without auto-resolving.
- Bounded consumer ticks, restart recovery, consumer-only receipt history,
  supported restore reconciliation, and no automatic action replay.
- A separately stored monitor with enrolled HMAC reports, freshness/replay
  checks, progress/coverage states, and a generic NOT_SENT alert outbox.
- Reproducible tests, including real subprocess exits against local SQLite.

## What does not exist

**No OAuth deployment, MCP HTTP/stdio transport, public listener, real outbound
HTTP worker, TLS tunnel, real Spark connection, independent monitoring host,
phone-alert sender, or V3.2 runtime adapter is supplied or certified.** These are
hard gates in `contracts/live_acceptance.json`, not configuration flags you can
set to true. No test fixture may be exposed to the Internet as authentication.

The Python object boundaries are not OS security boundaries. Malicious code with
the same file/process permissions can bypass them. All three databases are local
in tests; their separation is logical/durable, not evidence of independent
failure domains. No claim of cryptographic isolation, bulletproof operation,
exactly-once delivery, or hardware root of trust is made.

Read `00_START_HERE.md` and `docs/RESIDUAL_RISKS.md` before any integration.
