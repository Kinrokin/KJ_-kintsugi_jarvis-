# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Everyday household behavior

## Objects and evidence
An obligation stores desired outcome, source, deadline, owner, acceptance, privacy, conditions and completion basis. An occurrence stores one routine's anchor, definition version, timezone, window, nudge state, completion version and basis. An automation report is separate and cannot complete either. The local action-report import deliberately marks caller reports `REPORTED_UNVERIFIED`; authoritative receipts stay with the trusted adapter/broker.

For ordinary habits, Done is sufficient user evidence. Silence becomes UNKNOWN after a clock window; never infer failure, illness or consent. Skip is not completion. Undo preserves history. A delayed notification response refers to its original occurrence ID, not the latest routine. Conflicting revisions refuse rather than overwrite. Exact duplicate commands are idempotent.

## Recurrence
**Clock:** local calendar day + configured wall time, with explicit timezone/fold/gap. A late completion does not shift tomorrow. The tick generates the current day's occurrence only; it does not fabricate every missed historical occurrence after a long outage. Existing elapsed clock windows become UNKNOWN and stop prompting. Counts of missed obligations cannot assume unobserved days were all checked.

**Completion:** next elapsed-hour or wall-calendar-day interval follows actual qualifying completion, not a reminder. Only one successor is generated. Undo invalidates an uncompleted derived successor; a successor already reported done is marked NEEDS_REVIEW, not erased. Calendar-day anchors preserve configured local clock semantics; seconds are normalized to minute precision by this implementation.

**Event:** requires a user-reported or independently established event ID/time. Passing scheduled shift end is not evidence work actually ended. The CLI helper/API can record an event; no external event subscriber is installed.

DST policy is explicit: ambiguous time uses fold 0 or 1. Nonexistent time may reject, or shift to the first valid minute (02:30 in a spring gap becomes 03:00, not 03:30). This is a product choice, not a universal calendar rule. [S7]

## Reminder behavior
Snooze changes the next cue, never a provider appointment or a hard deadline. Ordinary routines permit at most three local cues per occurrence and honor quiet hours. The helper records a local cue only; OS/push delivery, reading, and actual completion remain different evidence. Equal quiet start/end currently means all-day quiet, so use distinct times for active cues.

The dashboard shows due/next-cue state. It does not create native notifications or tasks by itself. No cloud automation per toothbrushing step. A native private task surface can provide actual reminders after its capability is proven; the household ledger still records the correct occurrence.

## Minimum, late and recovery modes
Minimum day picks a subset of the approved ordinary full routine. It resets on the home date and does not alter external appointments or obligations. Home timezone is America/Chicago for this candidate; individual routines can have IANA zones. Changing the household's home timezone is a reviewed code/configuration change, not inferred from a device clock.

A separate planning helper previews flexible work around fixed commitments; it is not a general automatic rescheduler or travel API. Critical deadlines stay open. If the day is too full, present the smallest useful next action and identify what can wait. No shame, no punitive backlog and no fabricated streak statistics.

## Capture and obligation closure
Capture → private inbox → Use as my next action creates an accepted self-owned task. A structured email import creates a CANDIDATE with source mailbox and message ID. Accept establishes ownership and optionally explicit conditions. Delegation is not accepted responsibility until reported acceptance is recorded. A candidate not accepted remains visible without pretending the user committed.

Changed source evidence requires review. The user can select one source version and explain the basis; the history stays available. This selection does not make the sender's assertion a new global policy. An already completed obligation with a conflicting new source reappears for review. No source conflict can automatically mark it done. Completion can be undone.

A clinic reschedule can have separate conditions: clinic confirmed, calendar updated, transportation accepted. Attendance and subsequent paperwork may be separate obligations. Self-report of attendance is appropriate; an event edit alone is not.

## Privacy
Private is the default for every personal task/routine. A general request to help the family is not permission to publish. Shared calendar operations require exact audience/target/field scope. Personal source-email links, descriptions, attachments, diagnoses, account data and private preparation notes stay out of shared output. The narrow shared calendar route permits only selected summary/start/end fields, even when someone tries to grant a broader description.

## 3.1.1 offline-context correction
Browser commands retain original tap time, occurrence/definition/household identity, displayed full/minimum variant and user revision. Server receipt is separate. Delayed completion never adopts reconnection-day mode; completion-anchored successors use the reported original time. Late snooze retains its original target. Legacy queued commands with insufficient context are held for review. Foreground cue offers are not proof of notification delivery or task completion. See REPAIR_NOTES.md.

Historical [S*] source identifiers, where present, resolve to provenance/V3_1_DOCUMENTS/SOURCES.md and are not a fresh live product verification.
