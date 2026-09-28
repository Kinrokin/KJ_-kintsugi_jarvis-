# Narrow next work units — not another architecture rewrite

## Unit A: actual MCP/OAuth adapter

Use an established MCP SDK and external OAuth resource-server verification.
Translate authenticated issuer/subject/resource/scope into Identity on a trusted
server-side path, and route the two allowed producer operations to ProducerSurface.
Do not expose the consumer/history/monitor/operator methods as producer tools.
Enforce edge body/connection/timeout quotas before deserializing request data.
Persist queue data outside stateless compute. Preserve a separate producer token
from the Pi consumer and reporter tokens. Test client protocol negotiation.

Completion evidence: request/response traces with secrets removed; unauthorized,
wrong-resource and wrong-scope refusals; admitted receipt survives service
restart; producer cannot read another producer's status; real SDK tool listing
contains exactly two application tools. Until achieved: NOT_IMPLEMENTED.

## Unit B: real Pi consumer and monitor routes

Add an outbound authenticated client with strict peer pinning/allowlisting as
appropriate, TLS validation, bounded streamed response bytes, cancellation,
backoff/jitter and bounded batches. Do not follow candidate-supplied URLs.
Confine the importer to its own inbox state and approved outbound endpoint.
Do not mount the authority database or shell sockets in its process sandbox.
Run the monitor on a genuinely separate failure domain and configure only an
operator-approved generic alert destination.

Completion evidence: target-Pi test run, killed consumer recovery, lease/ack
loss across the actual network, idle-wait behavior, service resource measurements,
real Pi-off alert reaching the intended phone. The local condition-wait tests do
not substitute for these. No automatic public hosting or service installation.

## Unit C: source verification and private V3.2 handoff

Read exact allowed source references using the core's own account-bound reader.
Maintain retrieved fact versus cloud claim separately. Add a sidecar handoff to
V3.2's private-candidate interface after reviewing its actual API/schema. Retain
both gateway receipt and provider/source identity. No Family-calendar copy or
human-obligation completion based solely on receipt. Test the same source arriving
through Spark, direct mail and a permitted label fallback. Metadata label changes
are provider writes and require their own approved scope.

## Unit D: supervised Spark compatibility canary

Check current account features and other connected-app permissions. Test one
non-sensitive candidate with the declared write annotation. Record whether the
actual schedule requires manual confirmation, blocks, or supports a permitted
operation. Do not claim unattended behavior from documentation. Check consent,
revocation, duplicate delivery, final private review and separate phone receipt.
If every submission needs a tap, decide whether supervised use is worthwhile;
use the direct mail watcher rather than disguising the operation as read-only.

Only after these units and retention/restore policy review may a specific public
trial be proposed for authorization. No production rollout is scheduled here.
