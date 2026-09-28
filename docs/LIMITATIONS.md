# Current limitations and non-goals

This is a research prototype, not a production service. Passing tests does not
remove these limitations.

## Known release blockers

- Background-created native Task notifications are not qualified for important
  unattended use. Root cause remains unconfirmed.
- Native field evidence is operator-reported, not a complete provider-trace dataset.
- Automatic skill selection is not verified; workflow prompts should name the skill.
- Fixture bridge authentication, local queue, and monitor do not supply production
  OAuth, MCP wire transport, TLS edge, independently hosted monitoring or delivery.
- Pi hardware/OS behavior, power-loss durability and a production phone route remain
  separate NOT_RUN acceptance items. No Pi is needed for offline review.
- The bridge is not connected to the household application or a Spark account.
- The local lock is not a distributed single-writer service.
- POSIX secret storage and browser offline copies are not encrypted by this software.
  Windows DPAPI behavior is platform-dependent and not certified by Linux tests.
- No protection is claimed against an actor who can replace the code and read its
  operator secrets, or against simultaneous rollback of every trusted state store.
- Optional Web Push dependency/provider path was not exercised in the baseline;
  standard tests intentionally use synthetic transports.
- Source labels, signatures, public product documentation, and self-reported tool
  success do not establish genuine approval or real-world outcome.

## Out of scope

Autonomous banking, new credit, insurance termination, legal/tax decisions,
clinical decisions, employer/patient records, physical security control, permanent
cloud autonomy, invisible microphone/screen surveillance, or an “always remembers”
guarantee. No claim of novelty or formal proof of King's Theorem is made.

## Product outcomes not measured yet

Long-term missed-obligation rate, true household savings, daily review burden,
maintenance burden, notification-delivery service level, and a multi-user household
trial. The value plan is a proposed measurement design, not a measured result.
