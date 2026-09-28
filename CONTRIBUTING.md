# Contributing

Open an issue to discuss proposed contributions and rights before submitting code;
this publication has not selected an open-source license or blanket contribution
license. Do not include third-party code without its terms and provenance.

Keep changes narrow. Run `python tools/reproduce.py --out local-evidence` and include
both allowed-path and blocked-path tests. Document every runtime dependency, new
permission, outbound destination, resource budget and recovery change. Do not expand
scope to payments or clinical/physical-security control as an incidental feature.

Do not publish private test data. Prefer synthetic fixtures and minimal evidence.
Distinguish reported field behavior, reproduced local results and proposed features.
Regenerate manifests only after intentional source changes and review the diff.
The protected user state lives outside the repository. Never migrate it implicitly.
