# Build notes and self-review corrections

The first suite run executed 139 tests. One generated-crash test stopped because
its 250 advances of a virtual clock outlasted a one-hour test credential. The
authenticator correctly refused the expired credential. The fixture for that
long simulation was changed to request an explicit longer test lifetime. The
expiry/revocation tests remain. No expiry check was removed to make it pass.
First-pass output is preserved in evidence/.

Further source review added an enrollment grace deadline for a reporter that
never starts; a local lease-expiration check inside the acquired inbox write
transaction; digest validation of restore history; and exact tuple comparison
for duplicate sources regardless of JSON object member order. Added tests cover
those behaviors, real SQLite page-limit refusal, bounded lock contention,
producer quota persistence, and positive operation after recoverable failure.

These are same-author development tests and self-review, not an independent
security assessment. Hardware, browser, network, OAuth and external provider
certification are explicitly outside this release.
