# Incident KJ-NOTIFY-001: stored task, missing attention

**Status: OPEN / root cause unconfirmed / important unattended use not qualified.**
**Evidence class: operator-reported field calibration, with selected screenshots
observed in private development. Raw screenshots and account identifiers are not published.**

## Observations

Some manual and interactive-agent Tasks tests produced phone notifications. Some
background email-triggered review Tasks existed with a displayed time but did not
produce a noticed alert. In a later trial, manually editing the existing task time
was followed by delivery. A longer lead time and a separate create/update procedure
did not establish a repeatable correction. The first successful alert's originating
app was initially uncertain; later screenshots showed Tasks in specific instances.

## Rejected conclusions

- Not proven that Spark calls the public Tasks API for this path.
- Not proven that manual editing “arms” a particular hidden reminder flag.
- Not proven that device permissions are universally correct or incorrect.
- Not proven that a 15–20 minute minimum lead time is a fix.
- Not proven that a second create/update call fixes delivery.
- Not proven that Calendar will be reliable because it exposes reminder fields.
- No failure-rate estimate: the runs were neither randomized nor fully instrumented.

## Documented caveat

Google's public Tasks resource says the due value records date information and
discards time when setting it. Google's user help separately describes timed task
notifications. Those facts justify capability testing, not root-cause attribution.
References [S1] and [S2] in [SOURCES](SOURCES.md).

## Containment

Do not rely on this unqualified Spark-created Task path for safety-critical or
otherwise essential time-sensitive attention. Keep state tracking separate from
delivery. Continue using independently established personal reminders for real
commitments. A fallback must be tested on the actual device and must not silently
share private items to a Family calendar.

## Next experiment (not run here)

One specifically authorized synthetic event in a private test calendar, verified
reminder settings, a recorded creation route, scheduled time, source timezone, and
physical-device receipt. Include a second run and a late/failed-delivery case.
Do not create a real event, notification, or schedule as part of repository tests.
