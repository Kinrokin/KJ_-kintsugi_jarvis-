# Publication operations

The main CI is read-only and runs synthetic reproduction on Python 3.11 and 3.13.
The optional Pages workflow deploys only `site/` and has the minimum Pages/id-token
permissions. Action references are pinned to commit IDs resolved from their official
repositories during this publication; pinning reduces drift but is not an audit.

No runtime secrets, account access, paid model calls, or persistent household service
are required for the default tests. Workflow evidence is separate from the captured
local reference run. Generated artifacts include clean source and Skill ZIPs.

A one-time materialization step may be used for the initial bulk source transfer;
it must validate a separately fixed archive digest, reject unsafe paths, preserve
existing git history, and use non-force updates. It is publication plumbing, not
JARVIS infrastructure. It must not install an agent or access unrelated repositories.

The static site is included even when repository settings prevent Pages activation.
A successful local rendering is not proof of a deployed website. Report the actual
Pages run and URL only after verifying them.
