# Reproduce the public edition

## Environment

Python 3.11+; a working IANA timezone database; standard-library test dependencies.
The publication was assembled and tested on Linux with Python 3.13.5. Optional
mail/push/calendar integrations require separate dependencies and permissions;
they are not enabled by the default reproduction command.

## Commands

```bash
python tools/verify_manifest.py
python tools/reproduce.py --out local-evidence
python tools/demo.py
```

The runner launches the household and bridge suites in separate processes to avoid
module-name collisions, writes individual result records, runs CLI and synthetic
workflow checks, and emits `SUMMARY.json`. It does not collect personal accounts,
request API keys, install dependencies, create cloud schedules, or mutate providers.
Temporary test state is used for all demonstrations. `local-evidence/` is gitignored.

Reference results in `evidence/reference/` are one captured run; CI results are new
runs and may differ in duration/platform. Counts are per test identifier, not per
mutation iteration. Passing the synthetic suite does not certify a live adapter.

## Optional checks

Inside `components/household`, `scripts/check_operations_runtime.py` exercises a
real local HTTP/subprocess supervisor with synthetic state. It binds loopback only.
`check_private_https.py` requires OpenSSL; DOM checks require Playwright and a browser.
Their baseline reports are not silently relabeled as rerun checks. Default CI covers
the dependency-free suites and synthetic workflows; see workflow definitions for
actual scope. No scheduled user/account actions are created by repository CI.

## Rebuild artifacts

```bash
python tools/package.py --out dist
```

The output ZIP includes source, docs and reference evidence. An importable Spark
skill ZIP has `SKILL.md` at its root. No screenshots, credentials, live state, nested
old release archives or `.git` directory are included. SHA-256 digests are produced.
An unsigned digest is an integrity aid, not publisher authentication.
