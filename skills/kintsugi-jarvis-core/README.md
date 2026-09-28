# Kintsugi JARVIS Core — Gemini Spark Calibration Skill

This package deliberately tests Spark before any custom stateful backend is introduced.

Files:
- `SKILL.md` — reusable stateless Kintsugi reasoning protocol.
- `CALIBRATION_TESTS.md` — synthetic calibration sequence.
- `EVALUATION_RUBRIC.md` — scoring guide.

Do not place credentials, account secrets, private household data, financial data, or employer/clinical information in this package.

The skill does not create durable state, authority, transactional guarantees, or external network access for its scripts. Any such capability must come from the Spark task's supported tools or a separately engineered backend.
