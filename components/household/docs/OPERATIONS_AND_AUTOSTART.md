# Runtime, autostart, health and shutdown

`runtime_operator.py run` hosts the private UI and the optional ingestion/reminder worker. It has one OS-held lock per runtime directory; the lock releases on process termination. Two processes cannot own this same local runtime directory at once. This is not a distributed lease and does not prevent a separate program or human from acting on a provider.

The default is loopback, no mail sources, push off, no calendar/bank writer. Household/push and mailbox polling use separate worker lanes, so a slow mailbox request cannot directly block routine materialization. Push sends at most one queued notification per cycle with a bounded transport timeout. Both share the same local database/disk failure domain. The workers use bounded loops with no paid model calls. It records start and completion separately. Health distinguishes worker age, selected source coverage, transport state and user-reported completion. It never infers 'all clear' from metadata.

## Plan first

On the target computer:

```powershell
python scripts/plan_autostart.py --config "$HOME/KintsugiRuntime/runtime.json" --out "$HOME/KintsugiAutostartPlan"
```

The resulting Windows script does nothing on invocation except inspect/show its plan. It is scoped to the current user, uses a deterministic per-home name, refuses an unrelated existing task, and has explicit `-Apply`, `-Start`, `-Remove` switches. Inspect its exact executable, arguments, directory, task ownership and configuration first. Run only the individually authorized switches. No admin, password registration or global startup mutation is required by the plan. An OS policy may still prevent installation; do not bypass it.

**Windows limitation:** the generated task is at interactive user logon. It cannot work while the machine is powered off, and does not promise operation while logged out or asleep. It does not change your power settings. It allows battery operation, which consumes battery; review this choice. Linux output is a user-systemd unit, not an installed service. Copy/enable only after inspection and authorization; no linger/root settings are created.

`doctor` checks local configuration, installed modules and TLS key-pair loading. Loading a certificate is not evidence that a phone trusts it. Windows DPAPI/task execution and Linux systemd installation were not exercised here.

## Pause and recover

The phone has a **pause network** button. It stops new mail/push attempts made by this runtime, not already dispatched operations or other tools. Resume requires an interactive operator command `resume-network`. Local routines/capture remain available while network is paused.

`watchdog` emits a status and exits nonzero if the heartbeat is stale. Run it from a separately configured observer to detect process failure. An observer on the same machine is not independent of power, disk or host failure. No secondary notification channel is preconfigured. `health.json` and `continuity.txt` are private local outputs, not shared dashboards.

On shutdown, the HTTP server stops accepting requests and the worker is asked to stop. A blocked network call may outlive the request to stop; its already reserved notification is not retried automatically. On crash, notification records left DISPATCHED are uncertain, not successful. Restart releases stale OS locks and invalidates HTTP sessions. The persisted local login code stays in the secret store until deliberately rotated. No password appears in task arguments or worker logs.
