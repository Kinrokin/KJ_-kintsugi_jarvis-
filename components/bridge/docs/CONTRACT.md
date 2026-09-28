# Capability, delivery, privacy and failure contract v1

## Trust and purpose

External agents create *untrusted administrative candidates*. They cannot read
household state, mutate authority, complete obligations, or cause calendar,
email, financial or smart-home effects through this component. The bridge does
not constrain tools Spark has outside it. Source text remains untrusted after
parsing, hashing, signing, correlating or storage. Source pointers are claims
until independently retrieved by a future account-bound reader.

## Producer capability

`jarvis.submit_candidate(candidate)` writes only the gateway candidate store.
Identity, destination queue and permitted source aliases come from verified
credentials, not candidate fields. `jarvis.get_submission_status(submission_id)`
returns only the authenticated producer's own opaque ID and transport status.
An absent receipt and another principal's receipt have the same public error.

The status vocabulary is stored / locally_received / rejected / expired. A
leased item still appears stored. Neither accepted nor locally_received means
reviewed, approved, scheduled, attended, paid or completed.

There is no get_household_brief, get_system_health, append-memory,
request-interruption, shell, SQL, arbitrary fetch or provider-effect tool.
Exact allowlisting replaces name-based "execution verb" blacklists.

## Candidate schema

Version 1 accepts schedule_change, deadline, billing_observation and
task_candidate. Each has exact fields and limits. JSON duplicate members,
unknown fields, nonfinite numbers, floating point values, overlarge/deep bodies,
control characters and type coercions are refused. Source aliases and object
IDs are bounded; they are never paths, SQL syntax or URLs to fetch.

Schedule claims carry local date, time, IANA zone and an absolute timestamp.
A deterministic roundtrip detects a mismatch, including the 14:15 UTC / 14:15
Missouri example. This validates consistency, not whether school announced it.
DST repeated local times require an explicit consistent absolute instant.

`urgency_hint` remains inert data. It cannot select priority queue order,
interrupt the human, bypass budgets or establish risk/delegation levels.

## Persistence and acknowledgment

Gateway submit returns a receipt only after the durable database transaction
commits. Receipt identity is random. Idempotency is scoped to authenticated
producer plus queue plus submission key. Same key and different canonical
payload is an error, never an overwrite. A lost response is retried with the
same key/payload, subject to quota; the stored receipt is reused.

Gateway lease retains the candidate and records a random lease token, consumer,
expiry and attempt count. The private inbox commits the receipt, canonical
payload and private review record atomically before the worker acknowledges.
The worker calls ack only after commit returns. Compromise of the trusted
consumer could forge acknowledgements; an ack is not remote disk attestation.

Lost local commits cause redelivery. Lost acknowledgements cause duplicate
receipt ingestion with no second record. Ack requires current consumer scope,
queue binding, receipt digest and lease token. The old token cannot acknowledge
a subsequently re-leased delivery. Current same-lease acknowledgements are
idempotent after a committed ack, even when the response was lost.

This is at-least-once delivery and local idempotency, not exactly-once global
execution. SQLite serialization applies only to users of this queue on its
supported local filesystem. It does not serialize other agents or providers.

## Bounded failure

Authenticated submit attempts and status reads consume a producer token bucket.
Different tokens for the same identity do not reset it. Successful admissions
also consume daily count/byte quotas and retained row/byte capacity. Consumers
have separate bounded lanes so producer quotas do not consume their allowance.

Rate limiting itself costs resources. A public edge must reject excessive
connections/bodies before they enter Python. No public edge is included. Disk
page limits bound the main SQLite database; journals, filesystem, backups and
host-wide resources need deployment quotas. Resource incidents return a fixed
error code, never a falsely successful receipt.

After delivery attempts or retention are exhausted, a candidate becomes a
visible rejected/expired tombstone; it is not deleted. A bounded local diagnostic
ring is available to the operator. The ring is not a permanent audit archive.
The consumer is not allowed to take action just because a candidate is valid.

## Privacy

Cloud producers receive no local titles, decisions, family details, source
retrieval results or health data. Minimal status can still reveal receipt timing
and therefore rough availability; decide whether even that metadata is
acceptable before deployment. The gateway can see the candidate data it stores.
TLS and encryption-at-rest are production requirements, not included guarantees.
Store only necessary summaries/references, never employer/patient information.
