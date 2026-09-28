# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Migration and maintenance

## Preserve the parent
This is a patch of V3.1, not a rewrite of the unavailable V3 research source. Keep the original ZIP and external digest. Use a new code directory and new demo state. Do not overwrite active code, Ollama, Docker, KT, repositories, account settings or native scheduled tasks.

Pause an existing writer before any real-state review. Back up household state using the supplied supported backup procedure. Keep authority storage separate and do not clone an old authority snapshot into an active writer. Only one designated operator route may be enabled after the trial and explicit canary approval.

## Schema and approvals
Household schema remains 3.1 with additive fields (`user_revision`, original client event context and separate receipt times). Runtime/client protocol is 3.1.1. Opening 3.1 state adds only needed metadata; it does not infer old offline tap times. Broker startup rotates approval generation, requiring new reviewed grants. The authority intent table gains nullable provider_binding; legacy rows remain unbound and cannot be automatically reconciled through an arbitrary current adapter.

An operator must independently establish the historical provider/account and outcome for legacy uncertain operations. Do not alter database rows or delete uncertain intents just to unlock execution. Preserve a separate incident record and choose a reviewed recovery strategy. This release intentionally does not automate that high-risk history reconstruction.

## Browser migration
Close old app tabs. Old V3.1 queued commands lack original context; V3.1.1 retains them for export/review/discard and refuses automatic replay. A blocked queue is not lost: export it privately, resolve with the user's actual report, and discard only after review. A new routine-view cache requires fresh opt-in; old consent is not expanded to cache more data.

Service-worker updates do not force-activate over open pages. Verify the 3.1.1 footer and current protocol after reopening. The native cache lifecycle was not demonstrated in this build. Never claim that clearing a browser cache also deletes server records or vice versa.

## Rollback
Stop the new foreground process and retain its state and unknown-operation evidence. Running V3.1 on the new authority or outbox is not a supported rollback. For household-only recovery use supported backups and explicit review of commands recorded since the backup. Any rollback affecting authority requires all writes paused and external reconciliation. A user or OS administrator with access to all stores remains outside rollback-resistance claims.

## Maintenance budget
Do not add model agents, paid APIs, a public service or daemon to make the four fixes appear more powerful. First measure an ordinary private phone trial. Record review minutes, unnecessary cues, lost/duplicated actions and time to recover. If maintaining the trial costs more effort than it saves, simplify it. There is no standing invitation to modify household commitments.
