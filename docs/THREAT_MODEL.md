# Threat model

Assets: private household state, approval material, provider credentials, attention,
available compute/storage, correct obligation history, and the ability to stop.
Attackers may control emails, documents, source strings, duplicate delivery, timing,
and a legitimate but compromised producer identity. Host compromise remains outside
what this in-process prototype can contain.

| Attack/failure | Reference control | Residual boundary |
|---|---|---|
| External instructions claim user approval | Candidate namespace; model cannot mint local approvals | Native cloud tools remain outside the broker |
| SQL/shell/HTML strings | Parameterization, no shell in bridge, text rendering | Not proof against every dependency vulnerability |
| Flood by authenticated producer | Bounded admission, storage, batch and retry budgets | Public edge/DDoS mitigation not implemented |
| Receipt enumeration | Producer-scoped opaque status | Timing and traffic metadata can still reveal activity |
| Timeout after submission | Unknown outcome requires reconciliation | Arbitrary third-party provider guarantees are not supplied |
| Crash before inbox commit | Retain leased candidate, redeliver | Power loss of actual storage not tested |
| Lost acknowledgement | Deduplicate already committed receipt | Ordinary recovery does not solve every catastrophic rollback |
| Stale or replayed heartbeat | Freshness, sequence and progress checks | Independent hosting and phone delivery not provided |
| Approval expiration during preparation | Recheck at dispatch | Cannot cancel work already dispatched |
| Wrong provider used to verify | Provider/account/environment binding | Real adapter identity must still be configured correctly |
| Old backup restores permission | Supported recovery invalidates/reviews authority | All-state rollback requires an outside trust anchor |
| Task created without phone alert | Separate delivery state and field acceptance | Native unattended notification path remains unresolved |
| False all-clear after source loss | Coverage separate from job success | Silence is not proof that all outside sources are healthy |
| Prompt claims all private data should be shared | Private-by-default policy and narrow destinations | Skill text alone is not an enforcement boundary |

Test safety as both refusal and liveness: an allowed operation must still succeed,
recovery must return to useful operation, and a backlog must not consume the household
routine worker. Every new adapter needs a capability contract and target acceptance.
