# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Release gates — focused repair

Passing a local gate does not promote a live account or phone. This release performs no automatic authority promotion.

| Capability | Scope now | Remaining gate |
|---|---|---|
| private_routines | IMPLEMENTED_OFFLINE_TESTED | Physical phone and actual reminder delivery |
| private_obligations | IMPLEMENTED_OFFLINE_TESTED | One selected real email and actual household outcome |
| local_and_phone_ui | IMPLEMENTED_LOCAL_HTTP_HTTPS_AND_SYNTHETIC_DOM_TESTED | physical phone, trusted device route, native storage/service-worker lifecycle |
| calendar_broker | IMPLEMENTED_SYNTHETICALLY_TESTED | Separate operator boundary and real canary |
| google_https_adapter | IMPLEMENTED_MOCK_CONTRACT_TESTED | OAuth, actual provider conformance, not connected |
| gmail_outlook_ingestion | PLAYBOOK_AND_IMPORTER_ONLY | Authorized native reads, identity, pagination, durable sync proof |
| financial_forecast | IMPLEMENTED_SYNTHETICALLY_TESTED | Current actual Finances data and protected floor |
| subscription_cancellation | PLAYBOOK_ONLY | Specific selected service/approval/supported provider route |
| global_write_broker | NOT_ESTABLISHED | All automated external writers forced through trusted route |
| independent_watchdog | NOT_INSTALLED | Separate observation/notification deployment |
| scheduled_household_review | PROMPTS_AND_POLICY_PROBE_ONLY | Approved timing and later actual policy retrieval |
| mobile_wake_word_screen_control | NOT_IMPLEMENTED | Separate supported user-initiated integration only |
| dependency_risk_simulation | HELPERS_OFFLINE_TESTED | Actual complete household graph not built |
| opportunity_engine | SCREENING_HELPER_ONLY | Authoritative real research and consent |
| resource_governor | PER_RUN_HELPER_ONLY | No durable provider billing cap across processes |
| semantic_llm_redteam | NOT_EXECUTED | Realistic model-facing corpus and isolated supervised evaluation |
| anti_full_machine_rollback | NOT_ESTABLISHED | External trust/reconciliation after authority compromise/loss |
| measured_14_day_benefit | NOT_EXECUTED | Real baseline/reference set and completed trial |
| banking_legal_clinical_actions | NOT_IMPLEMENTED_OR_ENABLED | Human professional/provider workflows, not automatic graduation |
| kt_project_execution | EXPLICITLY_OUT_OF_SCOPE | Separate existing KT authorization/writer |
| push_and_always_on | NOT_IMPLEMENTED | separately approved notification and hosting integration |

The four reported failures have executed regression coverage in `evidence/FOCUSED_TRACEABILITY.json`. The physical-phone receipt remains NOT_RUN. Existing reminder routes should remain available; this prototype does not deliver background push.
