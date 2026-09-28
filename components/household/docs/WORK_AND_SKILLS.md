# Integrating with the chat that creates skills and agents

Yes: the existing desktop engineering/Work/Codex chat is the intended deployment host if it actually has your permitted local access. Upload this ZIP plus DEPLOY_IN_WORK.txt there. Do not rely on its recollection of an older JARVIS. Ask it to run the local checks and setup, not synthesize another agent constitution.

`AGENTS.md` belongs only to this extracted candidate. The four optional skill folders under `skills/` are narrow instruction bundles: deployment, private household review, daily brief and recovery. They are not installed by extraction. Use your target product's currently supported skill workflow; inspect collisions and do not overwrite a same-named existing skill or global AGENTS.md. Unsupported Skills UI is not a blocker to using the local application/hand-off.

Before updating actual recurring ChatGPT tasks, inventory existing tasks through the actual available task tools. Do not trust task counts in old conversation text. Reuse narrowly equivalent monitors, and wait for permission before changing schedules. This package creates zero ChatGPT tasks. The separate local runtime tick is not a ChatGPT scheduled task.

Scheduled monitor text should be self-contained about no writes, source scope, privacy and what to do with unavailable state. Each target environment must demonstrate that a FUTURE RUN can retrieve the exact policy and current household state; not just the version number or a description of its file. Project-file accessibility differs by product/task experience and must be measured in the target run. A chat-only monitor cannot assume access to the local filesystem.

No secret/credential is placed in a skill or task. No filesystem path becomes an authorization. Native connector writes and cloud-browser effects do not automatically pass through this application. Keep monitors read/propose-only. This build does not install a cloud gateway or scrape one chat's credentials for another.
