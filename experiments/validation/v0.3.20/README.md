# GhostQA v0.3.20 — Strong fresh composite validation

**Preregistered before any target generation and before any fresh target-policy evaluation.**
`executed` is `false` at this commit.

Date: 2026-09-24
Starting HEAD: `7e730565d043fd5e8744e1882e44686f566a7276`

## Research question

Does the completely frozen v0.3.19 composite structural candidate transfer to multiple new application shapes while:

1. resolving nested handoff and return opportunities,
2. activating Return-Entry Drain only from finding-terminal provenance,
3. bypassing horizon-only return-entry opportunities,
4. preserving Guard-confirmed bugs,
5. staying inactive or selective on fresh negative controls?

This is stronger than v0.3.15 because it validates the full repaired lifecycle, not only Horizon Handoff. It is still not universal generalization.

## What v0.3.19 already means

v0.3.19 Outcome A is inspected repair evidence. It is not fresh generalization evidence. The product default stayed unchanged.

Candidate, frozen and not edited in this round:

- identity: `ghost-structural-finding-return-entry-drain-guard`
- policy: `FindingReturnEntryDrainGuardGhostPolicy`
- controller: `FindingReturnEntryDrainSequenceController`
- source: `ghostqa/exploration/finding_return_entry_guard.py`
- sha256: `0bfec3c7bd2811f154daa83bc81fde632976b8ab6e1da9ee6a208cf81c4bb42c`
- freeze: `experiments/frozen/ghost-finding-return-entry-v0.3.19/freeze.json`

Frozen semantics stay: v0.3.9 exact-repeat return-cycle escape, v0.3.14 Horizon Handoff, v0.3.16 Early Parent Re-entry and Structural Frontier Lease, v0.3.17 post-witness Local Action Drain, v0.3.18 Return-Entry Drain after a valid trigger, and v0.3.19 finding-terminal provenance. An ordinary horizon-only return entry uses the v0.3.17 fallback and does not start Return-Entry Drain.

## Three different claims

| term | meaning |
|---|---|
| static qualified | The declared graph contains the preregistered structural opportunities. |
| actual evaluable | A budget-120 trace reaches those opportunities. Bug counts do not define this. |
| full transfer | The composite transfer gate passed on a composite-evaluable positive target. |

## Fresh identities

Seed rule: `uint32` of the first 8 hex digits of `SHA256("ghostqa-v0.3.20:" + app_name)`. One graph per identity. No seed search.

| target | class | family | seed hex | seed | port |
|---|---|---|---|---:|---:|
| buggy-campus | positive | hierarchical_learning_assessment_review | 8e5a4335 | 2388280117 | 3951 |
| buggy-warehouse | positive | inventory_batch_transfer_audit | 84bb020a | 2226848266 | 3952 |
| buggy-studio | positive | project_scene_asset_render_review | 85e3eacd | 2246306509 | 3953 |
| buggy-booking | positive | venue_calendar_reservation_guest_workflow | 28cc5678 | 684480120 | 3954 |
| buggy-catalog | negative | shallow_catalog_fanout_control | 38a953bd | 950621117 | 3955 |
| buggy-kiosk | negative | shallow_finding_heavy_button_control | 27141746 | 655628102 | 3956 |

Positive targets plant 12 judge bugs each. Negative controls plant 8 each. Total judge bugs: 64. Bug manifests and mechanism-opportunity files are judge-only and are not served.

Catalog must stay free of nested handoff and finding-return opportunities. Kiosk must stay free of nested handoff while still containing at least two finding-return opportunities and one horizon-only control.

## Matrix

Policies: C1 `ghost-structural-memory`, G `ghost-structural-return-guard`, F the frozen v0.3.19 candidate. Browser seed 1. Positive budgets 40, 80, and 120. Negative budget 120. Exact cell count: 42. No LLM policy and no BFS or DFS in the primary matrix.

## Outcomes

Derivation order is C, then D, then B, else A. The function is `derive_v0320_outcome`.

- C: harmful, unsafe, or protocol-invalid.
- D: the fresh suite did not sufficiently exercise the frozen mechanism.
- B: safe, but mixed transfer.
- A: strong fresh composite transfer on at least three of four positive shapes, with Guard bugs preserved on all six targets and both controls selective.

Outcome A may set promotion readiness to `evidence_supports_productization_study`. It does not promote the candidate and it does not change the product default. The next round in that case is a v0.3.21 productization study. Any other outcome leads to failure analysis, not promotion.

## Phase order

1. This protocol commit.
2. Generator, static qualification, and suite freeze commit.
3. Fresh policy evidence.
4. Publication commit.

No fresh target-policy result runs before the suite freeze is pushed.
