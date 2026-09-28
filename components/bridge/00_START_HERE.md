# Local engineering handoff

1. Preserve V3.2 and every active runtime. Extract this ZIP to a new sibling
   review directory, not inside KT, a skill directory or an authority store.
2. Verify the ZIP digest against the separately delivered receipt, then run
   `python scripts/verify_manifest.py`. A co-located unsigned manifest is only
   an integrity check, not publisher authentication.
3. Run `python scripts/run_tests.py` and `python -m kintsugi_bridge demo` in the
   current user environment. Do not elevate privileges or bind a network port.
4. Inspect `docs/CONTRACT.md`, `docs/RECOVERY.md`, `docs/RESIDUAL_RISKS.md` and
   `contracts/live_acceptance.json`. Rerun the tests on the actual target Pi
   before stating that it works there.
5. Leave all existing services, skills, AGENTS.md files, schedules, app grants,
   calendars and payment controls unchanged. This does not merge into V3.2.
6. Record LOCAL_CODE_VERIFIED, DEMO_REPRODUCED and each unmet LIVE gate separately.
   Do not convert a successful demo into permission to expose a gateway.

## Safe next integration increment

Build a reviewed provider adapter around `IdentityVerifier`, `ProducerSurface`
and `Gateway`, using a conforming MCP SDK and external OAuth resource-server
verification. The two producer tools must remain the entire producer surface.

Deploy neither that adapter nor a tunnel until the user approves the specific
host, cost, OAuth permissions, data retention and operational ownership. Bind
producer, consumer and monitor credentials separately. Configure process/OS
isolation and an independent notification channel. Inspect the actual Spark
confirmation behavior without relabeling `submit_candidate` as read-only.

This handoff authorizes local engineering review only. Unmet live gates are
specific work units, not permission to invent credentials or leave listeners on.
