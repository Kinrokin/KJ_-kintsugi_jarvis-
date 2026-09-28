# What changed, and what is still a boundary

| Prior gap | Concrete 3.2 change | Remaining acceptance |
|---|---|---|
| Program must stay open | Runtime supervisor, worker loop, OS instance lock, current-user Windows task and Linux user-unit plans | Target OS installation/startup/reboot/sleep trial; no installed service here |
| Multiple independent writers | No account-write endpoints in new runtime; single-host runtime lock; separate operator calendar path retained | Not a global gate over native tools, other hosts, a browser or the human |
| Phone experience | Existing original-context outbox plus generic Web Push service worker, opt-in controls, optional transport, private HTTPS path | Actual handset HTTPS/native persistence/push/closed-screen trial |
| Background email | Runnable account-bound Gmail history / Graph delta adapters, OAuth setup, token refresh, scoped background polling | Registered app, consent, real-account read-only canary; only metadata, not a semantic mail assistant |
| Reminder delivery | Durable cue outbox, subscription opt-in, one transport attempt, generic payload, receipt states, stale Done/Snooze suppression | Optional pywebpush dependency and actual phone delivery; unknown outcomes never retried blindly |
| Secrets/identity | OS user-scoped DPAPI envelope on Windows, owner-only files on POSIX; OAuth stays local | Windows execution untested here; POSIX files not encrypted; no protection from same-principal/root |
| Drift and outages | Doctor, source binding, pinned optional adapter release, bounded requests, separate worker/source health, watchdog exit status | Independent observer/alert route not configured; host-level failure can stop both worker and local checker |
| Retention | Explicit preview/apply of old dismissed/removed metadata; active obligations preserved; no silent deletion | Other state/receipts kept; comprehensive archive/crypto-erasure remains a separate approved operation |
| Family ownership | Existing proposed/accepted ownership and completion conditions retained, documented as reported acceptance | No access to another adult's accounts; no implied agreement or automatic family assignments |
| Value vs maintenance | Existing measurement engine exposed through authenticated operations and CLI; 30-day trial receipt | Actual daily review time/maintenance/savings not yet measured |
| Skills/agent deployment | AGENTS.md scoped only to candidate plus four opt-in SKILL.md workflows and precise handoff | Target workspace support and explicit import/install; no global file overwrite |

No new model department, paid AI backend, surveillance, automatic money movement or public broker was added. The simpler native-calendar/reminder option remains a valid fallback when operating this prototype costs more effort than it saves.
