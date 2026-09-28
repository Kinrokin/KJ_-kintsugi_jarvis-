# KINTSUGI JARVIS 3.2 — Operations Review Build

A private household application plus optional read-only personal-mail ingestion and generic Web Push. This is a tested local candidate, not a remotely installed assistant or a claim of perfection.

**Start with `00_START_HERE.md`. For your existing engineering/Work chat, give it `DEPLOY_IN_WORK.txt` with this entire ZIP.**

The original private routines, minimum mode, Done/Undo/Snooze, original-context offline queue, human obligations and separate calendar control remain. New code adds a supervised foreground runtime, same-host instance lock, explicit OAuth onboarding, metadata-only Gmail/Outlook adapters, durable notification records, opt-in Web Push adapter, current-user autostart plans, health/continuity outputs and four narrow skill folders.

## What this is not

It is not an autonomous bank/payment service, a global gate around every ChatGPT tool, an always-listening microphone, a tested Android app, or a claim that provider permissions exist. No actual account is configured in this package. `pywebpush` is optional and was not installed/exercised against a real push provider in this build environment. No Windows task/service was installed here. No paid model/API integration is present.

## Normal design

1. Keep personal routines in private household state; no automatic Family-calendar entry.
2. A reminder delivery, user report, obligation outcome and provider action are different records.
3. Metadata is untrusted; the operator reviews the original message and accepts an obligation separately.
4. The new runtime has no calendar-writer, financial-writer or permission-granting HTTP route.
5. Network pause prevents new attempts in this runtime; already dispatched requests may finish. It cannot stop unrelated tools.
6. A push provider accepting a request is not evidence that your phone showed it or you completed anything.
7. Passing local tests earns local evidence only. Real account and physical-phone acceptance remains explicit.

See `RELEASE_RECEIPT.json`, `evidence/`, `docs/GAP_CLOSURE.md`, and `docs/SECURITY_AND_RESIDUAL_RISK.md` for precise claims.
