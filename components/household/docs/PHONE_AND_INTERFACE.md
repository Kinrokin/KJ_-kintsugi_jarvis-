# Retained component reference

For version 3.2 deployment, README.md, SECURITY_AND_RESIDUAL_RISK.md, GAP_CLOSURE.md, PHONE_AND_PUSH.md and MAIL_AND_OAUTH.md override obsolete statements about unavailable features. The following describes the inherited component; its historical test totals are not this release's totals.

# Private phone trial — implemented path, uncompleted acceptance

## What is included
The default stays local HTTP on 127.0.0.1. An optional explicit private-LAN HTTPS trial listener is supplied, along with a static app-shell service worker, opt-in routine-view/outbox caching, foreground cue polling and the repaired offline event protocol. No provider or authorization endpoints are exposed to the phone UI.

This is not a push service, native Android application, automatic background email reader or always-running installation. Python's http.server is not recommended as a production server; this use is a bounded local/private test surface, not Internet hosting. [R5]

## Prerequisites for the optional LAN trial
Use a trusted private network, a specific RFC1918 IPv4 address belonging to the computer, and an existing certificate/key whose name and trust chain are already accepted by the phone for the chosen HTTPS origin. Both devices must have an authorized route to that listener. No certificate, DNS, router, firewall, tunnel or startup-service changes are made by the program. Do not bypass certificate warnings, administrative blocks or use a public port-forward.

If the trusted connection does not already exist, stop this route and record that prerequisite. Do not make the household service public to avoid setup friction. Keep local use available while a separately approved secure deployment is arranged.

With those prerequisites already satisfied, run from the candidate folder (replace placeholders with reviewed real values; these are not credentials):

```sh
python -m jarvis.cli --state <private-trial-state> phone-trial \
  --host <computer-private-IPv4> --port 8766 \
  --cert <existing-certificate.pem> --key <existing-private-key.pem> \
  --origin https://<matching-private-hostname>:8766 --ack-private-lan
```

PowerShell users may enter this as one line. Use an initialized trial state with synthetic data or an explicitly chosen private routine. Open the HTTPS origin on the phone. Enter the local login code directly; do not send login codes, private keys or provider tokens to the assistant. Keep the server process running. Ctrl+C stops it. No automatic restart is installed.

The private-LAN option intentionally refuses wildcard/public listeners, non-TLS remote connections and mismatched origins. The endpoint checks Host/Origin and CSRF; sessions are HttpOnly and Secure under TLS. These controls do not make a home computer a hardened production host.

## Offline trial semantics
While online, opt in to browser storage only on your own protected device. The displayed routine view can be cached; pending commands retain the original timestamp, household, occurrence and full/minimum variant. A pending action is visibly unacknowledged. Other obligations are not cached as current data.

The service worker caches static shell files only, never /api, cookies or tokens. It does not implement push or Background Sync. It does not force an update into an already open client; close old tabs and verify the displayed 3.1.1 version during migration. Service workers require a secure context; source code and a manifest do not prove successful installation or offline operation on the phone. [R3]

While the app is visible and connected, it offers private routine cues. No guarantee is made while the screen is locked, tab suspended, app closed, host asleep or network absent. Do not rely on this release alone for medical, legal or other critical notifications. Use an already-established human/native reminder path for those until a separately approved reliable notification integration is demonstrated.

## Actual evidence versus remaining test
Actual Python HTTP and HTTPS clients exercised local endpoints, including certificate validation, Secure cookies, CSRF, origin checks, context-aware commands and logout. The HTTPS test generated temporary synthetic credentials solely for the test and deleted them; it made no device trust changes.

Normal navigation from the managed Chromium browser to the local server was blocked with ERR_BLOCKED_BY_ADMINISTRATOR. That block was not bypassed. Thirteen offline DOM checks used a synthetic fetch/storage bridge: seven inherited UI checks and six new offline-context checks. They do not establish native localStorage persistence, service-worker cache lifecycle, browser-to-server connectivity or a physical handset installation.

Use `config/PHONE_TRIAL_RECEIPT_TEMPLATE.json` for the real trial. Every field starts NOT_RUN. The acceptance sequence is capture -> visible cue -> snooze or Done -> disconnect/reconnect -> same occurrence/time/variant acknowledged once -> undo where appropriate -> no Family sharing. Test across a real day boundary without changing the phone's clock. Test app/tab closure separately from an open-tab connection interruption. Expected lock-screen/push result in this release is UNSUPPORTED, not a hidden failure to dismiss.
