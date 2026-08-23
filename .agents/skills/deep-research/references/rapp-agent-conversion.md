# Convert Deep Research into a RAPP Agent

`rapp-skills` targets systems that implement the Agent Skills convention.
Inside RAPP, capabilities are single-file agents, never runtime skills.

The conversion target is:

```text
deep_research_agent.py
```

## Mapping

| Skill element | RAPP agent element |
|---|---|
| Frontmatter `name` and `description` | Agent manifest identity and discovery description |
| Research contract | Agent policy/system instructions |
| Eight strategy tracks | Fan-out plan created by the agent |
| Track result schema | Typed result returned by each child agent |
| Evidence ledger | Structured `data_slush` payload and persisted artifact |
| Adversarial verification | Independent verifier phase |
| Output contract | Agent's final result schema |
| Resume rules | Durable run/journal state |
| Host-specific tools | Explicit adapters invoked by `perform()` |

## Single-file boundary

The converted file should contain:

1. the actual agent manifest;
2. input and result schemas;
3. track planning and validation logic;
4. orchestration logic for parallel workers;
5. evidence-ledger normalization;
6. verification and synthesis logic;
7. persistence hooks or artifact serialization;
8. the public execute/perform entrypoint.

Do not leave core behavior in an external prompt file. If the deployment is
Dataverse-native, store the actual `deep_research_agent.py` source and manifest
in Dataverse so the agent remains inspectable and portable.

## Behavioral requirements

- Default to eight distinct strategies for substantial research.
- Reject duplicate strategy IDs or overlapping assignments.
- Give comparison agents identical normalized evidence.
- Require structured results and independently verify high-impact claims.
- Track facts, inference, contradictions, and confidence separately.
- Preserve source provenance through synthesis.
- Retry only failed nodes and invalidate dependent synthesis.
- Treat side effects as at-least-once and require idempotency.
- Stop admitting work on global quota/authentication failures.
- Never promote majority agreement into evidence.

## Suggested tests

1. Eight unique tracks are generated for a complex query.
2. A duplicate strategy assignment is rejected.
3. Results remain associated with strategy IDs despite completion order.
4. One failed track is disclosed and retried without rerunning successes.
5. A disputed claim survives synthesis until independently resolved.
6. A fabricated citation is rejected.
7. A stale current-events source triggers a freshness failure.
8. Resume reuses unchanged validated results.
9. A verifier cannot approve its own original claim.
10. Final output distinguishes observed facts from inference.

The skill directory is a design input and interoperability artifact. It should
not become a runtime dependency of the RAPP agent.
