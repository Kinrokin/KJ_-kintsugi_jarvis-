# Primary sources and scope

Reviewed for the public edition on **2026-09-28**. These are provider/standards
references, not claims that a particular connector implements every documented
feature. Only short claim summaries are reproduced; source pages are not bundled.

| ID | Source | Relevance and limitation |
|---|---|---|
| S1 | [Google Tasks resource](https://developers.google.com/workspace/tasks/reference/rest/v1/tasks) | Public API's scheduled-date field discards time. Does not establish Spark's internal implementation or the notification incident's root cause. |
| S2 | [Google Tasks notification help](https://support.google.com/tasks/answer/13486720?hl=en) | User-facing notification behavior and device prerequisites; no guarantee of this project's automation route. |
| S3 | [Google Calendar versioned resources](https://developers.google.com/workspace/calendar/api/guides/version-resources) | ETag/If-Match conditional changes and stale-version failure; active connector capability must be checked separately. |
| S4 | [Google Gemini skills](https://support.google.com/gemini/answer/17094296?hl=en) | Saved instructions, root SKILL.md import, and current script/network restrictions. Instruction adherence is not a security boundary. |
| S5 | [MCP authorization, version 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) | Resource-specific authorization requirements. Not implemented by the bridge fixture authenticator. |
| S6 | [AWS SQS at-least-once delivery](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html) | Explains why duplicate-safe consumers are needed; does not imply this project runs on SQS. |
| S7 | [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html) | Crash consistency depends on assumptions about the OS/storage; process exit tests do not certify hardware power loss. |
| S8 | [Google SRE monitoring](https://sre.google/sre-book/monitoring-distributed-systems/) | Actionable monitoring and external behavior checks; the bridge's local monitor is not independently hosted. |
| S9 | [OWASP prompt-injection prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | Untrusted inputs, least privilege and layered mitigation; no claim of eliminating prompt injection. |
| S10 | [Google custom apps documentation](https://support.google.com/gemini/answer/17209137?hl=en) | Historically referenced for MCP/custom-app approvals. This page was not retrievable by the publication-time web tool; current confirmation/eligibility must be checked in the actual account. No new live compatibility claim. |

Component documentation includes additional references retained from its release.
Some product names/settings are time-sensitive; prefer current provider documentation
and actual capability tests over historical prose. This repository makes no current
model-ranking, product-pricing or subscription recommendation.
