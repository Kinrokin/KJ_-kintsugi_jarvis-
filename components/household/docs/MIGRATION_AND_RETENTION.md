# Migration, recovery and data lifecycle

This is an additive candidate based on the verified V3.1.1 archive, not a merge of unavailable V3 source. Older artifacts/docs are under provenance and are NOT active instructions.

1. Preserve the old package, household database, original outbox exports and separately held authority/intents. Do not run old/new writers together.
2. Stop the old service. Create a SQLite backup through the backup API/CLI, not an unsynchronized live-file copy. Verify its integrity and store it privately.
3. Initialize a new runtime home. Put a reviewed household-only snapshot into its `household` directory while the runtime is stopped. Let Household create additive delivery tables on open. Confirm the same household instance/occurrence identities, times and user reports. Use only one intentional runtime home.
4. Do not restore an old authority/approval database into authority. Preserve/reconcile uncertain original-provider intents. Restore invalidates delegation; obtain fresh authority separately.
5. New operational sources/subscriptions start unconfigured. New subscriptions cannot receive historical cues created before opt-in. Do not copy credential files across OS/user boundaries or assume DPAPI portability. Use the original same-user OS secret store or reauthorize explicitly.
6. Old queued commands without original context remain review items. Export before destructive cleanup. Never substitute reconnection time or reinterpret minimum as full.

Operational state and subscriptions are sensitive. The household backup does NOT include OAuth/VAPID/authority. A comprehensive machine backup may contain those, but its handling/restore is outside this helper. In particular, restoring notification state from before dispatch could forget an external attempt; freeze networking and reconcile, do not automatically replay all queues. This release does not supply a universal full-runtime restore command.

`retention-plan --days 90` lists old dismissed/source-removed mail metadata only. Save the plan in a private external file; review and back up before `retention-apply --plan ... --confirm "DELETE REVIEWED METADATA"`. The apply path rechecks current state and cutoff and cannot delete active household obligations. It is deliberately not an automatic delete-all-memory job. Secure erasure on flash/backups is not claimed.

Rollback means stop the new runtime, keep its private state for reconciliation, remove only an exact owned task through its generated plan, and return to the preserved prior application after reviewing schema/queue compatibility. No scripts uninstall unrelated software or delete prior packages.
