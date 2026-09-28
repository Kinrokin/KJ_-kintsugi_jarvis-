# Recovery and restore semantics

## Ordinary restart

Gateway receipt/payload/idempotency/lease state survives process restart on the
same durable database. Local inbox receipt/candidate state survives restart.
Monitor freshness/sequence floors survive restart, but signing keys must be
reintroduced from a trusted secret store. Fixture identity registry replacement
invalidates all opaque test tokens; it does not restore stale credentials.

## Failure points

- Before gateway commit: no accepted candidate; retry with same key.
- After gateway commit, response lost: retry returns stored receipt.
- After download, before local commit: lease expires and redelivers.
- After local commit, before ack: redelivery is locally idempotent.
- After ack commit, response lost: ack is already recorded; do not invent another
  obligation. Current same-lease acknowledgement can be retried.
- Schema/binding/storage uncertainty: no successful local receipt is claimed.
  A bounded attempt policy eventually reports rejection, not endless retries.

## Supported local inbox restoration

Use a SQLite-consistent backup, not a blind copy of a live database. Stop the
consumer before restoring. Call `enter_restore_reconciliation()` immediately,
before leasing new work. This holds normal intake and resets the recovery
cursor. Retrieve bounded consumer-only received-history pages from the retained
gateway store. `reconcile_page()` validates and commits a whole page plus cursor
atomically. A bad/incomplete page does not advance the cursor.

After the final page succeeds, `finish_restore_reconciliation()` permits new
intake. Recovered candidates remain RESTORE_REVIEW. Even an exact source match
is not permission to repeat a historical calendar action or human obligation.
No provider execution exists in this bridge.

## Honest limits

Arbitrary rollback of both gateway and inbox, rollback of monitor sequence state,
lost gateway disks, and an operator skipping this restore path cannot be solved
by the same backups or by a checksum kept beside them. Independent rollback
witnesses, retained history, backup validation and host recovery drills remain
production gates. This reference detects mismatched fresh gateway IDs but not
every restored clone with the same identity.

The gateway currently retains rows until its finite configured cap, including
acknowledged/expired receipts. It deliberately refuses admission at capacity.
There is no automatic retention rotation or lossy reset button. A reviewed
archive/tombstone policy preserving deduplication must precede indefinite
operation. Export/rotation must never silently erase unresolved candidates.
