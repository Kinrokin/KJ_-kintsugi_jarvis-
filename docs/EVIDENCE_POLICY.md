# Evidence policy

Use these classes rather than a single PASS label:

| Class | Meaning | Does not establish |
|---|---|---|
| REPRODUCED_LOCAL | Named test was rerun against this source in a recorded environment | Production reliability or independent review |
| SYNTHETIC_CONTRACT | Fake provider/clock/storage behavior was exercised | Real provider guarantees |
| OPERATOR_REPORTED | The developer reported a result in the development conversation | Raw provider telemetry or a controlled benchmark |
| SCREENSHOT_OBSERVED | A screenshot was available during development | Continuous delivery, origin authentication, or hidden tool behavior |
| DOCUMENTED_PROVIDER | A primary source specifies a product/API property | That the active connector exposes it |
| PROPOSED | Design or remedy not yet accepted | Implementation or demonstrated effectiveness |
| NOT_RUN | An acceptance property has not been tested | Failure or impossibility |
| NOT_IMPLEMENTED | Required code/service is absent | Future feasibility |

The field register is a redacted synthesis, not a full export of private conversations.
Tests with strong hints in their instructions are calibration, not proof of causal
skill invocation or general injection resistance. Manual Run now is not equivalent
to a timer firing without interaction. An assistant saying OBSERVED is a claim;
provider readback, user observation, and the report should be labeled separately.

Success metrics remain distinct: object creation, persisted state, attention requested,
provider accepted, device displayed, user acknowledged, obligation completed. A
single successful notification demonstrates that instance, not channel reliability.
A single miss is enough to withhold critical-use qualification, but not enough to
identify its root cause or estimate a population failure rate.

Publication receipts contain command lines, time, interpreter/platform, source
identity and individual results. Generated mutations are counted within parent
tests. A hash manifest proves consistency with that manifest, not publisher identity.
No number in this portfolio is labeled an independent audit result.
