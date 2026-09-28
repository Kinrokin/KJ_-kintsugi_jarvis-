# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Four-finding repair review

## Evidence provenance
The parent ZIP was extracted separately and matched its external digest and all 77 manifest entries. Its original 156 Python tests and 14 command-line checks passed. `scripts/reproduce_v3_1_findings.py --source <extracted V3.1 directory> --out <report.json>` reproduced all four findings. The script targets the OLD API deliberately and is not the repaired regression runner. Use `scripts/run_tests.py` for this candidate.

See `evidence/V3_1_REPRODUCTIONS.json`. All sources/events/accounts in those probes are synthetic. No connected accounts were queried or mutated.

## F01 — fresh authorization at submission
Previously Broker.execute captured `now` before slow preparation and reused it. The new callback is invoked immediately before the adapter submits a write, after ACL/event reads, OAuth token retrieval, subject verification, request serialization and construction. Authority.reserve acquires its transaction and then samples the clock, rechecking validity, signature, epoch, generation, revocation, pause and single-use consumption. Rejection before dispatch creates no write intent. A monotonic elapsed-time floor prevents a backwards wall-clock change during preparation from extending the approved duration.

Tests include expiration in ACL/preflight/token work, expiry while waiting for authority storage, revocation, backward clock, and a legitimate still-valid write. The real HTTPS path cannot accept an arbitrary historical caller timestamp. A changed payload still requires new approval.

Boundary: the check governs local submission time, not the remote provider's eventual commit time. There is no distributed atomic transaction with Google. A pause/revocation after submission cannot retract the packet or guarantee reversal. Already-dispatched requests remain subject to readback; an ambiguous outcome is not a retry authorization. Root/clock/adapter compromise is not solved by this change. [R1]

## F02 — original provider/account custody
Each approved context and durable intent now retains provider name, adapter contract, account identity, execution environment and connection/instance identity. Reconciliation compares the selected adapter against the original journal before any provider read and again afterwards. Matching calendar contents on a different account or simulator cannot close the intent.

The simulator stores an instance UUID durably; another database is another provider context. Mock HTTP and LIVE_HTTPS are distinct. The real Google adapter requires the expected Google OpenID subject (`sub`) and verifies the current access token against UserInfo over HTTPS before requests. Token refresh that changes accounts therefore cannot silently recover or modify the wrong account. OAuth setup/consent/token refresh is still an operator prerequisite; existing ChatGPT connector credentials are not a Python token. [R2]

Old V3.1 intent rows have no reliable account binding. They remain quarantined for operator-assisted reconciliation. Never fill a missing binding from the provider that happens to be selected today. Ordinary restoration still pauses writes and excludes the authority store. Full-machine rollback or an attacker controlling both code and credentials remains outside the local protection.

## F03 — original human report, not reconnection inference
The browser records a versioned event at the actual user tap: occurred_at, household instance, occurrence ID, definition version, timezone, observed user revision, and displayed full/minimum variant. Server receipt time is stored separately. The timestamp is explicitly self-reported device time, not an authentication claim. A device clock more than five minutes ahead is held for review, not rewritten.

A delayed minimum completion remains minimum on the original occurrence. Completion-anchored successors are based on the reported completion. A delayed mode command changes the original local day, not today's mode. A delayed snooze retains its original target; an already elapsed snooze is labeled as such. Exact replay is deduplicated; changed data with the same command ID is refused. Automatic nudge/expiry revisions can be rebased while human changes, routine redefinitions and wrong-household queues require review. Undo remains available and dependent occurrences retain their correction semantics.

A legacy queue missing context cannot be honestly repaired from guesswork. Both UI and HTTP boundary hold it for export/review/discard. The local synchronous CLI remains usable with server time; it is not a compatible substitute for replaying old offline commands. Pending queue changes are never shown as server-confirmed completion.

The optional browser routine cache excludes API credentials, CSRF, emails, captures, other obligations and provider receipts. Pending commands may contain the user's captured text and are clearly disclosed as unencrypted device data. It is not suitable for patient records or shared devices. Native browser durability/service-worker lifecycle needs the physical-phone trial. [R3]

## F04 — field-preserving calendar updates
Google PATCH now receives only the fields present in the exact approved payload. Existing reminders, visibility and private metadata are not sent or replaced. An unmentioned description is preserved; readback compares the approved subset. The If-Match precondition remains.

Google documents omitted fields remaining unchanged, while specified arrays replace existing arrays. Tests emulate that provider behavior and verify both custom overrides and default reminders survive edits. This is mock contract evidence, not a live result on Robert's calendar. [R4]

Creation is different: this narrow canary still deliberately creates private events with no reminders and no attendees. Those fixed defaults are disclosed. It is NOT the routine-reminder delivery engine. Explicit reminder changes remain outside the allowed proposal schema rather than being quietly accepted.

## Positive operation and scope
The repaired suite must allow valid calendar creation, field-limited updates, original-provider recovery without resubmission, and legitimate offline completion. No previous household behavior is replaced with blanket refusal. Production providers, physical phones, semantic model attacks and source-ingestion daemons were not exercised.

The four issues are repaired in the tested local reference implementation. This is not proof that every threat or timing interleaving has been eliminated. `docs/RELEASE_GATES.md` lists what cannot yet be claimed.
