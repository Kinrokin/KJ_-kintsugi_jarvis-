# Architecture and boundaries

## Native methodology track

Spark + explicitly selected Kintsugi skill + supported native apps. The skill guides
interpretation and user interaction. Native records can hold low-consequence state.
The platform's permissions, persistence, timing, and confirmations remain external
dependencies. This track does not inherit the local broker's enforcement.

## Local household track

`components/household/jarvis/household.py` owns private routines and obligation state.
`runtime.py` supervises the local web and mailbox workers; `web.py` and
`operations_api.py` expose the household interface. Optional read-only mail adapters
and push code have separate setup/acceptance requirements. `calendar.py` and
`authority.py` implement a distinct operator lane, not a phone-exposed general writer.

## Offline proposal bridge

`components/bridge/kintsugi_bridge/schema.py` validates bounded candidates.
`gateway.py` persists them before issuing receipts. `inbox.py` commits locally before
acknowledgement; `worker.py` bounds each ingestion tick. `monitor.py` models freshness,
replay, progress and coverage with generic alert records. Fixture authentication is
in `auth.py`; it must never become production authentication by changing a flag.

### Delivery sequence

```
Producer -> authenticated fixture -> validate -> durable queue commit -> receipt
Queue -> lease -> local inbox commit + deduplication -> acknowledgement
Lost acknowledgement -> lease expiry -> redelivery -> existing inbox record -> ack
```

This is at-least-once delivery with idempotent local ingestion, not end-to-end
exactly-once execution. Local receipt does not mean review, acceptance or completion.

## Trust rules

External prose and schema-valid strings remain untrusted. SQL values are bound as
parameters; input does not become shell commands. Source references do not authorize
arbitrary fetches. A signature can establish origin/integrity, not factual truth.
Sensitive outbound data requires separate purpose and audience checks. Every
consequential external lane needs its own real authentication and provider readback.

## What the local controls cannot enforce

They cannot govern a separate Spark tool, another host, a user manually editing an
account, or a process with the same filesystem/secret access. Pause prevents new
submissions through the controlled path; it cannot undo an already submitted action.
Restoring all stores together from an older backup is not solved by a monotonic
counter inside that same backup. See component residual-risk documents.

No network link between the bridge and the household app is claimed. No Pi,
Home Assistant, Google Home, custom MCP endpoint, or production OAuth service is
installed by checking out this repository.
