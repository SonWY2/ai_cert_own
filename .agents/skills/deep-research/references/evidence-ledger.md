# Evidence Ledger

Use a ledger when research has multiple tracks, disputed claims, or
decision-changing recommendations.

## Claim record

```json
{
  "id": "C-001",
  "claim": "A precise, falsifiable statement",
  "kind": "observed",
  "status": "confirmed",
  "confidence": "high",
  "track": "experimental",
  "evidence": [
    {
      "source": "URL, repository path, artifact path, or experiment ID",
      "locator": "section, line range, commit, timestamp, or command",
      "date": "2026-07-16",
      "supports": true,
      "notes": "Why this evidence bears on the claim"
    }
  ],
  "conflicts": [],
  "qualifiers": ["Version or environment limitations"],
  "verified_by": "independent-verifier"
}
```

## Allowed values

`kind`:

- `observed` - directly reproduced or read from a primary artifact;
- `documented` - stated by an authoritative first-party source;
- `inferred` - the minimum explanation consistent with observations;
- `reported` - credible secondary evidence not independently reproduced.

`status`:

- `candidate`
- `confirmed`
- `disputed`
- `refuted`
- `unknown`

`confidence`:

- `high` - direct/reproducible evidence or multiple independent primary
  sources;
- `medium` - strong indirect evidence with a meaningful untested assumption;
- `low` - plausible lead that should not drive a decision.

## Track result

Each research track should return:

```json
{
  "strategy_id": "artifact",
  "scope": "The unique assignment",
  "claims": [],
  "sources": [],
  "experiments": [],
  "contradictions": [],
  "unknowns": [],
  "recommended_followups": []
}
```

## Synthesis rules

1. Deduplicate semantically identical claims.
2. Preserve provenance from every contributing track.
3. Prefer reproducible evidence over source count.
4. Treat majority agreement as a signal to inspect, never as evidence itself.
5. Require an independent verifier for high-impact conclusions.
6. Keep a disputed claim visible when it changes the recommendation.
