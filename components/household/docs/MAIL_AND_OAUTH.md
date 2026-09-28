# Personal mail ingestion

The adapters are runnable read-only HTTP clients, tested with synthetic provider responses. No real mailbox has been connected/tested in this release. Connected ChatGPT Gmail/Outlook authorization is not an exportable credential for this local program.

## Two usable deployment paths

**Existing connected tools:** an authorized Work/chat task can read its own available connectors and prepare/review obligations. Use the bounded skill and self-contained task instructions. Do not claim those tools automatically feed this local database, share its locks, or have its OAuth credentials. A local engineering session may import a reviewed source-bound candidate through the existing `email` CLI; it is still not automatically accepted.

**Standalone worker:** requires a registered public/native OAuth app/client ID and explicit local consent. Google uses PKCE plus a localhost callback; Microsoft uses its personal-account device flow. These are personal-account flows, not an organizational deployment. Existing OAuth application restrictions/test-user lists/consent policies may block them. No registration, billing account or administrative consent is created by the helper.

Stop the runtime before changing its connection configuration. From a private interactive terminal:

```text
python scripts/connect_mail.py --config <private-config> --provider gmail --source-id personal-gmail --selector <personal-label-id>
python scripts/connect_mail.py --config <private-config> --provider outlook --source-id personal-hotmail --selector <personal-folder-id>
```

The helper verifies the account from the provider, displays the account identity for confirmation, stores tokens outside the package, and appends a **disabled** source. Review the exact identity and scope, then set its `enabled` field to true and restart. It refuses an existing source ID and configuration races. It does not read codes from email or paste credentials into chat. Do not connect employer/patient mail.

## Scope and behavior

Gmail initial scope is the selected label plus a bounded initial lookback (default 14 days). Later history processing stays in that selected scope and retains the original lookback floor. Graph delta is per selected folder; there is no claim to cover every folder, archive or second account. The OAuth read grants are broader than the metadata actually requested. This implementation downloads Subject, From, received time and identifiers; **not bodies or attachments**. Metadata itself is still sensitive and can contain clinical details. Use deliberately personal scopes; the code cannot perfectly classify PHI or every obligation from a title.

Gmail holds the initial anchor before enumeration; Graph preserves provider next/delta URLs after exact host/folder validation. Pages, calls, time, payload sizes and destinations are bounded. Failed/incomplete pagination commits neither partial candidates nor a new checkpoint. An expired history/delta cursor produces RESYNC_REQUIRED; it is not quietly replaced. Complete selected-scope coverage is not whole-inbox or whole-life coverage.

A message creates only a review candidate. The UI requires the actual outcome from a human review, preserves its source/hash, and still requires separate obligation acceptance. It does not infer dates, ownership or permission from a malicious subject. Marking source mail removed does not complete a household obligation. No send/delete/mark-read/forward tool is included.

## Recovery and costs

When a scope is too large for the bounded initial scan, choose a narrower personal scope or explicitly review a changed bound. Do not label a truncated scan complete. For an expired cursor, stop the worker, back up operations state, inspect the exact source, then use a new source ID/reviewed full scope; preserve prior candidates and reconcile duplicates. A future staged full-resync migration can improve this workflow but is not silently performed.

Polling defaults to 15 minutes; it is not an instant webhook. A source outage remains visible even if the worker runs. No paid AI calls, automatic natural-language extraction or promises to find every bill/appointment are made. Later model-based interpretation must retain source uncertainty and requires separate budget/permission review.
