# Primary references checked for this build

Retrieved/rechecked 2026-09-25. These establish provider/API concepts, not live functionality in this user's environment. Local code/test evidence lives separately in evidence/.

- Google, Synchronize clients with Gmail: https://developers.google.com/workspace/gmail/api/guides/sync — full/partial history synchronization and expired history IDs. Used for read-only selected-label ingestion and explicit RESYNC_REQUIRED.
- Microsoft, Delta queries for messages: https://learn.microsoft.com/en-us/graph/delta-query-messages — per-folder scope, opaque next/delta links, complete-round checkpoint and filtering limits. Used for bounded folder ingestion.
- Google, OAuth for native apps: https://developers.google.com/identity/protocols/oauth2/native-app — public/native registration, browser consent, loopback redirect and PKCE.
- Microsoft, Device authorization: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code — operator-owned browser/device flow, pending/slow-down behavior. No credential harvesting.
- MDN, Push API: https://developer.mozilla.org/en-US/docs/Web/API/Push_API — browser permission/service worker/push subscription model. Registration is not physical delivery evidence.
- pywebpush maintainer: https://github.com/web-push-libs/pywebpush and https://pypi.org/project/pywebpush/ — documented webpush parameters and 2.5.0 release. Wheel SHA256 shown by index: b5f5d45024223a04e73fe17f7a8e62540f35bbcc62b49e64d0a1080ff2dc26f2. Library was not installed in this execution environment; no real-provider claim.
- Microsoft, ScheduledTask settings: https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset — settings used by generated, uninstalled current-user plan. Windows runtime acceptance still required.
- OpenAI, Skills: https://help.openai.com/en/articles/20001066-skills-in-chatgpt — reusable workflow packaging and availability; not an execution/security guarantee.
- OpenAI, Work/Codex: https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex — differing execution surfaces and permissions. The target session is the source of capability truth.
- OpenAI/Codex skills: https://learn.chatgpt.com/docs/build-skills — SKILL.md format. Do not infer installation from packaging.

No page was copied wholesale. Suggested defaults (poll interval, push count, review-time targets) are design choices rather than externally established optimal values.
