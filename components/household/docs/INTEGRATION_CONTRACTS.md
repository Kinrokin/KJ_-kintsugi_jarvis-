# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Actual integration contracts

| Surface | Code delivered | Tested scope | Still required |
|---|---|---|---|
| Household routines/obligations | Persistent local SQLite, original-event offline protocol | Unit tests, actual local HTTP/HTTPS and synthetic DOM | Physical phone, real browser persistence and usable daily trial |
| Google Calendar adapter | Allowlisted one-off create/PATCH; current token subject check; ACL/readback; bound recovery | Simulator and mocked HTTP including real-HTTPS code path with fake opener | Operator OAuth, consented OpenID/Calendar/ACL access, exact account, host separation and real canary |
| Native Calendar connector | Not wrapped or intercepted by this Python | No new connector calls | Inspect the actual tool interface; never assume it exposes If-Match/client IDs or this broker |
| Gmail/Hotmail | Structured claim importer and read/propose playbook | Synthetic input only | Selected authorized native reads, identity/coverage/pagination, future runtime retrieval |
| Finance | Pure forecast/classification helpers carried forward | Synthetic data only | Current connected data and explicit cash-floor inputs; no payment route |
| Phone listener | Explicit private-LAN HTTPS foreground option | Local TLS client/server with temporary test certificate; boundary tests | Already-trusted certificate, permitted network route and physical-device trial |
| Service worker | Static shell cache only | Static contract inspection, not native lifecycle | Actual browser registration/cache/update/offline reopening |
| Reminders | Foreground authenticated UI cues | Local endpoint/logic, not proof of human receipt | Actual visible-phone trial; push/lock-screen delivery is not supplied |
| Scheduled tasks | Versioned prompts/probe | No future task run | Authorized schedule plus saved state/readback and later actual policy retrieval |
| Browser exception | No integrated provider browser writer | None | Human-supervised external operation; no broker guarantees implied |

## Google setup, only for a separately authorized canary
`GoogleCalendar` now requires an expected Google OpenID subject. Real calls query Google's UserInfo endpoint using the current token and refuse a different subject. Google identifies `sub` as the stable account identifier; do not substitute an unverified email string. OAuth consent/scopes and token provision are not auto-configured. [R2]

Operator command shape:

```sh
python scripts/calendar_operator.py --authority <protected-authority-directory> \
  --provider google --allow-calendar <exact-private-calendar-id> \
  --google-account-sub <verified-Google-sub> execute --proposal <reviewed-file.json>
```

Use `--help` and initialize authority in the operator terminal first. A host-owned token provider uses the existing `KINTSUGI_GOOGLE_ACCESS_TOKEN` environment integration or a reviewed callback. Do not paste tokens into chat. Token acquisition/refresh service is not bundled. No new API key or paid subscription is required for synthetic tests.

The adapter creates only one-off private/no-reminder canaries, without attendees. Existing Kintsugi 3.1/3.1.1 canaries may be updated if not recurring/attended. It does not reschedule a clinic, modify arbitrary existing events, edit reminders, handle recurring series or accept invitations. Update PATCH omits reminder/metadata fields and retains If-Match. [R4,R6]

Mock HTTP bindings require their own connection ID and cannot verify live operations. Old unbound intent records are refused. A valid original-provider recovery reads rather than resubmits.

## Ingestion and schedules
Do not use a blanket assumption about Project-file access. The particular future run must retrieve the intended current policy bytes. Until a real scheduler/connector is demonstrated, these are handoff instructions, not deployed daemons. Preserve existing filters, dates, timezone, recurrence and enabled states. Discover existing tasks before proposing duplicates. No schedule is created by this ZIP.

## Coverage
A completed local run does not certify Gmail/Outlook/bank coverage. Unsupported, incomplete and stale sources remain visibly unknown or degraded. No new money, consent or account status is inferred from synthetic test data.
