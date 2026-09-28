# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Trust, authority and recovery — 3.1.1

## Trusted boundary
The Python broker, provider adapter, authority database, operator authentication and host OS are trusted components. The model and incoming content are not. The proposer cannot originate grants or provider evidence through household commands. Approval signs the canonical proposal plus prepared destination/audience/provider context, expiry, epoch and startup generation. The operator enters credentials only in a separate trusted terminal.

This does not establish OS separation merely by naming two directories. A process that can read the operator token/password or rewrite the broker can bypass local rules. The package does not intercept native ChatGPT connectors, arbitrary browser actions, other computers or manual provider operations. No global single writer is claimed until the actual deployment restricts all relevant automated writers.

## Dispatch and stop semantics
The final callback rechecks authorization using fresh time inside the acquired authority transaction, after slow provider preparation. It records durable intent and single-use consumption immediately before transport submission. Before-submission refusal is not an external effect. After submission, uncertainty remains UNKNOWN_EXTERNAL; it never automatically returns to execute.

A kill switch blocks NEW submissions through this route. Requests already sent may finish. Transport time and provider commit cannot be made atomic with the local grant. Provider-account identity is rechecked using the current credential; matching payloads on another environment/account do not verify the original request. [R1,R2]

## Recovery provenance
Intent identity includes provider, contract, environment, account, connection/instance, target and operation key. Reconciliation uses the same namespace. A simulator receipt is synthetic evidence forever. A mock transport cannot graduate a receipt to live evidence. Missing legacy identity is a manual-review condition, not an invitation to infer an account.

Provider readback verifies only the relevant computer operation. An actual household obligation remains separate. User-reported routine completion remains sufficient for an ordinary habit and is labeled self-report. Local logs are inspectable, not tamper-proof against the filesystem owner.

## Restore
Ordinary household backups exclude the authority store. Supported restore pauses writes. Broker startup invalidates old grants through a new generation. Durable consumed grants and dispatch intents remain in authority storage. Do not restore or replace that store from an old copy to make a pending operation work. Full-machine rollback, joint database loss or operator compromise requires stopping all writes and independently reconciling external state.

Existing authority rows without provider_binding remain unknown/quarantined. No automated script silently upgrades them to verified. Preserve old state and evidence. Start with the local household-only trial, not real provider credentials.

## Privacy
Personal tasks/routines are private. A calendar item may leave the private store only with exact destination/audience/field authorization through the bounded operator route. Group, domain, public or unknown audiences and unsupported event fields are refused. Future ACL changes can still disclose previously private data; this implementation cannot guarantee permanent secrecy.

The device cache is optional and unencrypted, as is the local SQLite household store. Use protected personal devices. A pending capture may contain private text. No patient data, credentials, banking details or medical decision workflows belong here. Semantic PHI detection is not claimed.

## Phone surface
Default loopback HTTP remains available. Explicit private-LAN HTTPS trial uses a separately trusted certificate and strict Host/Origin/CSRF/session controls. It exposes household commands only, never authority/provider writes. It is not production Internet hosting, independent monitoring or reliable background notification delivery. [R5]
