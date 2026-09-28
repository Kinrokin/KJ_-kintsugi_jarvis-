# Research grounding and design choices

Primary source identifiers and exact URLs are in SOURCES.json.

S1/S2 establish the difference between resource-server authorization and an MCP
transport. The supplied Python IdentityVerifier port and tool manifest implement
neither OAuth negotiation nor wire framing. They are explicit extension points.

S3 documents custom MCP apps and confirmation for writes. It also describes
information sharing from other available sources. Consequently a constrained
bridge is not proof of a constrained Spark account or unattended submission.

S4/S5 inform the lease/acknowledgement pattern. This reference does not use SQS or
claim its infrastructure. Local receipt commit precedes acknowledgement; retries
are idempotent. That is not a distributed exactly-once guarantee.

S6 explains held waits versus periodic empty polling. Our condition wait only
exercises local wake/timeout behavior; a real network adapter is still missing.

S7 informs storage pragmas. They request SQLite durability and size controls;
actual device and filesystem behavior need target-host tests. Row and byte caps
also keep this reference finite rather than making indefinite storage promises.

S8/S9/S10 distinguish injection and exposure mechanisms. Parameterized SQL,
non-executing text storage, safe display and no arbitrary source fetch remove
specific execution paths. They do not prove external text safe for a future LLM.

S11 informs progress/coverage/alert separation. Our monitor persists evidence and
queues NOT_SENT alerts; it is not an independent service or actual notification
route until those have been configured and tested.

All specific quotas and freshness intervals are engineering trial defaults,
not values established as optimal by these publications. No safety guarantee is
borrowed from a standard merely because the implementation cites it.
