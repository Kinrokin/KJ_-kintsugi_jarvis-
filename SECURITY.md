# Security policy

This project is experimental; no security certification or production support SLA
is offered. Do not connect fixture authentication to a public listener, expose a
local operator port, or test real payments/clinical/physical-security operations.

Report non-sensitive defects through the repository issue template with a synthetic
reproduction. Do not post secrets, tokens, personal data, private schedules, or a
live exploit against an account. For a sensitive finding, use GitHub's private
vulnerability-reporting option **only if the repository exposes it**. Otherwise
open a minimal issue asking the maintainer for a private route, without disclosure
of exploit details or credentials. Do not assume an unverified reporting address.

Priority goes to unauthorized effects, lost obligations, wrong-provider verification,
replayed authority, private-data disclosure, false completion and silent delivery
failure. Include the commit, environment, expected invariant, observed behavior,
and recovery outcome. A failing regression test is preferred over a screenshot of
an assistant claiming success.

Disclosure and fixes should preserve evidence, contain the affected lane, add a
regression, and re-test legitimate work. The maintainers will not describe a
model-only prompt change as a complete security boundary.
