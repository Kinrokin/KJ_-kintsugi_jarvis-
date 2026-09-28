# Case study: an assistant that must know what “done” means

**Author/project lead:** Robert King. **Edition:** public portfolio 1.0.
**Method:** AI-assisted implementation; local synthetic tests; single-operator
field calibration reported during development. See the evidence register rather
than treating every statement in this narrative as a separately reproduced result.

## 1. The problem was not a shortage of reminders

The original need was a household assistant that reduced open loops: messages to
review, routine tasks, follow-ups, scheduling conflicts, and financial administration.
The failure to avoid was an assistant that made attractive plans while leaving the
human responsible for remembering whether any of those plans actually happened.

A naive implementation gives one language model mail, calendars, finance, and a
browser, then asks it to be proactive. That combines untrusted inputs, broad tools,
uncertain reasoning, private information, and real-world side effects in one place.
It also creates a misleading success metric: the model can report a successful
API operation even when the person receives no useful assistance.

Kintsugi's working question became: **How much useful work can be completed without
allowing interpretation, notification, authorization, and completion to collapse
into the same state?**

## 2. Three states replaced one success flag

The first consequential distinction is between an obligation, a software action,
and a routine occurrence. An appointment may need review; a calendar entry may have
been edited; the person may still not have arranged transportation or attended.
A reminder can be dismissed without the underlying call having occurred.

For an ordinary household task, explicit user-reported completion is acceptable.
It must be recorded as that kind of evidence, not as independently observed reality.
Higher-consequence operations require their own confirmation and provider evidence;
the architecture does not make banking or medical decisions autonomous.

Minimum mode likewise changes the planning burden, not the truth of completion.
It simplifies or defers optional activities while leaving fixed commitments visible.
A suggestion that another person take a task is not evidence that they accepted it.
These distinctions are represented in the household implementation and exercised
in its test suite, rather than existing only as prose instructions.

## 3. Controls had to live outside the persuasive component

The local reference separates household records from an operator-controlled action
lane. It binds approvals to proposed content, rechecks validity at dispatch, and
keeps uncertain outcomes unresolved until reconciliation. The browser-facing
household application does not expose the calendar operator or payments.

The bridge extends a different boundary: an external producer can submit a bounded
candidate and ask for its own minimal transport status. It cannot ask for a household
brief, read private schedules, execute a shell, or directly promote persistent
preferences. Its local reference provides admission limits, durable storage,
leases, a local inbox commit before acknowledgement, and duplicate recognition.

These are narrow, testable mechanisms. They are not a globally enforced gateway
over every native app or agent the user might separately authorize. The test
authenticator is deliberately a fixture, not deployable public authentication.

## 4. Review found concrete failures

The household repair cycle recorded four especially instructive defects:

| Failure | Repair represented in current source | Why it matters |
|---|---|---|
| Approval expired during slow preparation | Fresh authorization/time check near dispatch | Earlier approval validation is not sufficient forever. |
| A different provider could validate uncertain work | Bind reconciliation to original provider/account/environment | Similar content is not the same external outcome. |
| Offline completion used reconnection time/mode | Preserve original occurrence, reported tap time and displayed mode | Yesterday's minimum routine is not today's full routine. |
| A calendar edit reset reminders | Send only approved fields and preserve omitted fields | Hidden side effects can exceed the user's approval. |

The current regression suite tests the repaired behavior. Earlier review summaries
are historical claims unless independently reproduced; this publication does not
pretend to have rerun unavailable prior V3 source. The current source lineage and
new reproduction results are published separately.

## 5. Native-platform calibration challenged the architecture

The early architecture leaned toward a custom backend for nearly everything.
Field calibration provided a useful counterargument. In the operator's reported
Spark environment, explicit invocation of a Kintsugi skill could help distinguish
sender claims, assumptions, and user decisions. Keep records were reportedly
created, rediscovered, updated, and left unchanged when already satisfied.

Human edits and duplicate titles were deliberately introduced. In the reported
runs, the workflow identified the ambiguity rather than choosing a convenient
record, overwriting the change, or deleting a duplicate. A synthetic obligation
was accepted, reminded, cleared at the reminder level, completed by explicit user
report, closed, and later left closed.

Those observations support continued evaluation of native tools for low-consequence
administration. They do not prove exactly-once behavior, concurrency safety, an
always-on service, or general resistance to prompt injection. Several early tests
included the expected rule in the prompt; passing them does not isolate the skill's
causal contribution. Automatic skill selection was not established from UI telemetry.

## 6. The notification failure changed the release decision

The project encountered an uncomfortable result: a record could exist with the
expected displayed time while no phone alert arrived. Manual task creation and an
interactive agent-created task were followed by notifications in observed examples.
Some background-created review tasks were not. Editing the time manually was then
followed by an alert. Longer lead time and separate creation/update instructions did
not establish a fix.

The public Tasks API documents that its due value preserves the date, not a writable
due time. That is a relevant integration caveat, **not proof of which internal route
Spark used or what caused the field failure**. The device's configuration, sync path,
creation mechanism, and platform behavior were not isolated in a controlled experiment.
See [the incident record](NOTIFICATION_INCIDENT.md) and [primary sources](SOURCES.md).

The proper release response is to keep the attention path unqualified for important
unattended use. A Calendar-based alert path was proposed; no successful end-to-end
Calendar replacement trial is claimed here. Two Google apps are not automatically
independent notification channels.

## 7. Simpler is a valid outcome

The Pi was an optional host, not the objective. The custom bridge was an optional
control boundary, not a prerequisite to useful planning. If a native workflow
returns more time than it costs and its consequences are low, a more complex backend
may be the wrong product decision.

Conversely, familiarity and a handful of successful note edits do not justify
sensitive autonomous writes. The project favors consequence-specific controls over
one global autonomy switch. It also resists turning each personal habit into a
surveillance problem: for ordinary routines, the person's own Done signal is enough.

## 8. What this portfolio demonstrates

The work demonstrates problem framing, state modeling, source provenance, testable
permission boundaries, recovery design, local implementation, field calibration,
and willingness to revise claims when evidence changes. It does not establish
novelty over all agent research, independent certification, general production
reliability, clinical suitability, or a measured reduction in household cost/time.
The 30-day value trial is an open acceptance gate, not a completed result.

The most important result is a design habit: **verify the outcome the person needs,
not merely the operation the software can report.**
