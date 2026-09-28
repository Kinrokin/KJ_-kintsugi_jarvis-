# Start here

## The shortest engineering-chat route

Upload the whole ZIP and send `DEPLOY_IN_WORK.txt` to your existing desktop engineering chat. It must verify the package, use a new candidate folder and run local checks before proposing activation. It must not merge earlier prototypes, overwrite global skills/AGENTS.md, alter KT/Ollama/Docker, buy services or pretend that upload installs anything.

## Local inspection — no accounts required

Extract to a new ordinary folder outside active repositories. Use an existing Python 3.10+; Python 3.13.5 was tested here. Windows may need an approved `tzdata` installation if doctor finds no IANA timezone database. No script installs Python or packages automatically.

From the candidate folder:

```powershell
python scripts/verify_package.py .
python scripts/run_tests.py --out "$HOME/Kintsugi-review-tests"
python scripts/runtime_operator.py --config "$HOME/KintsugiRuntime/runtime.json" init --home "$HOME/KintsugiRuntime/private"
python scripts/runtime_operator.py --config "$HOME/KintsugiRuntime/runtime.json" doctor
python scripts/runtime_operator.py --config "$HOME/KintsugiRuntime/runtime.json" run
```

Use `py -3` instead of `python` when that is your verified Windows interpreter. `init` refuses an existing config. Runtime state must be outside this package and repositories. These commands do not configure routine times or connect mail.

In a second **private interactive terminal**, show the local login code:

```powershell
python scripts/runtime_operator.py --config "$HOME/KintsugiRuntime/runtime.json" show-login
```

Open `http://127.0.0.1:8765` on that computer and enter the code there. Do not paste it in chat, screenshots, task prompts or logs. `show-login` refuses redirected output. Ctrl+C stops the foreground runtime.

Configure one ordinary routine using your chosen times/full/minimum steps. The examples are examples, not your commitments. The existing CLI accepts an explicitly reviewed routine JSON:

```powershell
python -m jarvis.cli --state "$HOME/KintsugiRuntime/private/household" routine MY_REVIEWED_ROUTINE.json
```

## Bring back existing household data deliberately

Do not initialize over existing state or copy a live SQLite file. Follow `docs/MIGRATION_AND_RETENTION.md`. Preserve original-context outboxes and any old authority/intents. Do not run two writers or two different household services over the same state.

## Optional operational features

- Autostart: `docs/OPERATIONS_AND_AUTOSTART.md`; generate a plan, review, explicitly apply on your target host.
- Phone: `docs/PHONE_AND_PUSH.md`; trusted private HTTPS route, device consent, then real acceptance.
- Personal mail: `docs/MAIL_AND_OAUTH.md`; registered OAuth client and local consent, no ChatGPT-token extraction.
- Skills: `docs/WORK_AND_SKILLS.md`; import only supported, reviewed narrow skills without overwriting existing work.

Keep the separate calendar writer disabled through the household trial. A genuine calendar canary requires its own approval and original-provider evidence; this build does not run it for you.
