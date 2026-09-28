# Phone and notification deployment

## Private route

The default computer-only URL is localhost. Your phone cannot use the computer's localhost address. Use the existing private-LAN TLS path only after choosing an approved RFC1918 address, port and exact HTTPS origin, with an existing matching certificate/key and a certificate chain trusted by the phone. No public/wildcard listener, reverse-proxy bypass, certificate-warning bypass, automatic firewall change or public tunnel is supplied.

Set `host`, `port`, `origin`, `tls_cert` and `tls_key` explicitly in the external runtime config, then restart and test. A VPN/remote route is not inferred from private-LAN support; it needs its own approved network/hostname controls. Using the phone away from that route is not certified.

The local UI is a private household prototype built on Python's standard-library HTTP server with bounded connections, Host/Origin/session/CSRF checks. It is not a hardened public Internet application. Use a reviewed deployment platform/reverse proxy before any broader exposure; that is outside this release.

## Optional push

Install nothing merely by opening the package. With approval, use a dedicated existing/new virtual environment and the pinned optional `requirements-push.txt`. Review the resolved dependency versions and record a local freeze/hash inventory. This package pins its direct dependency, not every transitive wheel. The exact pywebpush API is coded and source-reviewed; it was not installed/executed against a push provider in this environment.

Use `scripts/setup_push.py --config <private-config> --contact mailto:<your-contact>` from a trusted interactive terminal. It creates VAPID key material in the separate local secret store and enables the transport only if HTTPS is configured and the library is installed. Do not copy private keys into chat. On the phone, sign in at the trusted origin and choose **Enable private reminders**. Browser permission is a separate consent step.

The initial provider allowlist supports the named FCM and Mozilla endpoints only. Unsupported endpoints are refused; do not broaden hosts based on a webpage instruction. Additional browser ecosystems need an adapter/contract review.

Push sends only a generic private reminder, never an obligation title, diagnosis, amount, message body or source link. The encrypted payload includes a limited notification receipt token; it cannot mark any obligation complete. The phone may show a generic lock-screen cue, but physical locked-screen/background delivery still must be tested. There is no delivery guarantee or priority/emergency service.

## Truthful delivery states

`QUEUED -> DISPATCHED -> PUSH_ACCEPTED / UNKNOWN_DELIVERY / PUSH_REJECTED / ENDPOINT_EXPIRED`

Client reports may separately say `CLIENT_REPORTED_DISPLAYED` or `CLIENT_REPORTED_OPENED`. A resolved `showNotification` promise is not proof that a person saw it. No state implies human completion. A timeout does not cause a blind retry. A later independently scheduled cue can still occur within the routine's limit. Budgets are caps, not promises that every cue arrives.

Queued reminders are suppressed after a later Done, Snooze, routine change, quiet window, expiration, unsubscribe or local network pause. A request already submitted may still arrive after any of those changes. No test claims otherwise.

## Offline privacy and multiple tabs

Original time, occurrence, definition, timezone, full/minimum variant and observed user revision remain bound to the queued command. Old queues missing that context require review. Offline storage is opt-in and contains ordinary routine data/captures/queued actions, not provider tokens or source-email bodies. It is **not encrypted browser storage**. Erase the offline copy before sharing a device. Logging out does not magically erase a deliberately retained offline copy.

Where Web Locks is available, one tab owns the editable outbox; another is read-only until it is reloaded after the owner closes. Browsers without that API must use a single editing tab; cross-tab protection is not claimed. This logic is tested through a synthetic browser bridge, not certified on Robert's handset.

Complete `config/LIVE_ACCEPTANCE.json` on the actual device: capture, foreground cue, explicit push, locked-screen behavior, Done/Undo/Snooze, offline minimum completion across a real day boundary, restart, no duplicate completion, and no Family-calendar disclosure. Leave NOT_RUN where no evidence exists.
