# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Primary sources checked for this focused repair
Checked 2026-09-24. These establish provider/protocol facts, not successful operation in the user's environment. Paraphrases below are deliberately bounded. No old source citation is evidence of a current connector permission.

| ID | Source | Relevance |
|---|---|---|
| R1 | https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html | Execution must remain tied to valid transaction authorization and protected data; a stale early check is insufficient. |
| R2 | https://developers.google.com/identity/openid-connect/openid-connect | Google account subject and UserInfo/OAuth identity semantics; additional access requires consented scopes. |
| R3 | https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API | Service-worker secure contexts and static caching; registration/lifecycle must be proven in the browser. |
| R4 | https://developers.google.com/workspace/calendar/api/v3/reference/events/patch | Omitted fields are preserved; specified arrays replace the old arrays. |
| R5 | https://docs.python.org/3/library/http.server.html | http.server is not recommended for production; private trial code is not Internet hosting certification. |
| R6 | https://developers.google.com/workspace/calendar/api/guides/version-resources | ETag/If-Match version-bound updates and stale-write behavior. |

Prior V3.1 source notes and product documentation are historical provenance. Any live ChatGPT/Work/task capability must be discovered and demonstrated in the target session, not inferred from this document. Source docs are not tests of this implementation.
