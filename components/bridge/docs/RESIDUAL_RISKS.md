# Residual risk and nonclaims

## Release boundary

This is a useful local reference and testable contract, not a production bridge.
It has no network listener, no MCP wire implementation, no HTTP consumer and no
real identity provider. Authentication tests use explicitly fake opaque tokens.
The future OAuth verifier must enforce trusted issuer, intended resource/audience,
subject, scope, lifetime and revocation policy. An Identity object or supplied
actor name is not evidence of user approval.

## Isolation

The tests run gateway, inbox and monitor primarily in the same interpreter on
separate files. A few tests deliberately exit subprocesses. Neither proves OS
sandboxing or separate-host resilience. A process with authority to modify these
files/code can forge state. A Raspberry Pi alone is not a cryptographic root of
trust. Files are not encrypted by this package; POSIX creation modes are not a
complete Windows ACL or secret-management solution.

## Inputs and reasoning

Parameter binding and HTML escaping protect specific contexts. No model is
invoked, so no empirical claim of prompt-injection robustness of a future LLM
can be made. Syntactically valid, accurately signed data can be false. Candidate
source IDs must be independently verified before consequential promotion.
A compromised producer can cause misleading pending claims or consume its
quota. Correlation of an exact source set is not proof of factual agreement.

## Delivery

The retry/commit tests use local disks and synthetic clocks. Sudden real power
loss, corrupt SD/SSD firmware, concurrent backup tooling, broken wall clocks,
host resource starvation, attacker-controlled OS and catastrophic disk loss
were not exercised. Complete payload retention is finite and intentionally
stops admission at capacity. Redelivery stops after the bounded attempt policy;
rejected/expired candidates require operator attention, not an assumption of
household completion. Alert records alone do not notify anyone.

## Network and cloud

Public TLS/OAuth, body streaming, connection budgets, reverse-proxy behavior,
DNS/redirect safety, real long polling, independent monitor hosting and Spark
behavior are not implemented. Use a maintained MCP SDK/auth stack for those
layers, not a custom imitation of OAuth. An unsigned manifest does not defeat
an attacker replacing both payload and manifest; compare the separately retained
ZIP digest and preserve a trusted provenance channel.

A proposal-only custom tool cannot restrict Spark's separate native tools,
signed-in browser, other connected apps or disclosures. Inspect those grants.
Google documents confirmation for custom-app writes. Do not misrepresent a
submission as read-only to make scheduled automation appear to work.

## Integration with V3.2

V3.2 was preserved and hashed, not patched or rerun. Its prior test counts are
not this bridge's evidence. This package neither loads its authority.sqlite nor
calls runtime_operator.py. Connecting candidates to the active private household
UI requires a reviewed sidecar importer with source binding, explicit privacy,
receipt correlation, no authority promotion and no automatic obligation closure.
There is no bank, calendar, email-send, Home Assistant or notification actuator
in this reference. Existing safety equipment stays independent and authoritative.
