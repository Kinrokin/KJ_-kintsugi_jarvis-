# Health without household-data readback

The separate monitor database tracks opaque node ID, operator enrollment epoch,
strictly increasing sequence, received time, progress sequence and coarse source
coverage. Reports are HMAC-authenticated by an out-of-band enrolled key and a
separate reporter credential. Timestamp bounds and persisted sequence floors
reject replays. Re-enrollment rotates epoch/key; a prior signed report cannot
become current merely by being replayed.

A valid signature only proves possession of the reporting key. It cannot prove
that a compromised reporter's claims are truthful. An eventual independent
behavioral canary is a separate control.

States: AWAITING_REPORT, HEALTHY, DEGRADED, STALLED, UNREACHABLE and
CLOCK_UNVERIFIED. Missing first report after the enrollment grace interval
becomes UNREACHABLE; it is not allowed to wait forever. A fresh heartbeat with
stalled progress is not healthy. A successfully completed empty scan may advance
progress; an empty queue need not indicate failure. Partial/unknown source
coverage is not an all-clear. Backward clock movement is not healthy.

Transitions create generic NOT_SENT alert records in a finite diagnostic
outbox. **No messages are actually sent.** No independent host or notification
channel has been provisioned or tested. The operator must approve and then test
that separate route, including delivery while the Pi is off. A local Python
unit test cannot establish an independent failure domain or phone receipt.

Network reachability, processing progress, source coverage, alert submission,
phone display and human acknowledgement are different milestones. Even a read
receipt does not prove the underlying obligation is complete. This channel is
not an emergency alarm or security interlock.
