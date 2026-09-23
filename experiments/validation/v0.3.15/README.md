# GhostQA v0.3.15 — Fresh multi-target Horizon Handoff validation

**Preregistered before any target generation and before any target-policy evaluation.**
`executed` is `false` at this commit.

Date: 2026-09-23
Starting HEAD: `6a8f51d86fced3bdb87b8d1851035a202394500a`

## Research question

Does the completely frozen v0.3.14 Horizon Handoff candidate show the same useful nested-boundary behavior on multiple new preregistered application shapes that were not used to design or tune it?

This is a fresh multi-target mechanism-transfer validation. It is stronger than the v0.3.14 inspected-mechanism result. It is not universal generalization, and it does not change the product default.

## What v0.3.14 already means

v0.3.14 Outcome A means Horizon Handoff repaired the inspected nested-boundary mechanism on CRM/Ops and passed the specified historical regression suite. That result stays narrow. This round does not edit that candidate.

Candidate:

- identity: `ghost-structural-horizon-handoff-guard`
- freeze: `experiments/frozen/ghost-horizon-handoff-v0.3.14/freeze.json`
- source: `ghostqa/exploration/horizon_handoff_guard.py`
- sha256: `827b8e64f953012ceec06fe3e0302c343a016463b5b1f88191e7a0a486c2467e`

Frozen semantics: `BRANCH_HORIZON = 3`; continuation while `commitment_left > 1`; handoff to a real child only when `commitment_left == 1`; exact or cluster parent witness; child escape unwinds. No threshold N, no max stack depth, no app-specific rule.

## Three different claims

These words are not interchangeable:

| term | meaning |
|---|---|
| static qualified | The declared graph contains the preregistered nested structure. |
| actual evaluable | A budget-120 trace actually exercises that nested boundary. |
| full transfer | The structural transfer gate passed. Bug count is not the gate. |

Static qualification does not guarantee that a policy reaches the structure.

## Fresh identities

Seed rule, frozen now:

`seed = uint32(first 8 hex digits of SHA256("ghostqa-v0.3.15:" + app_name))`

| target | family | seed hex | seed | class | bugs | port |
|---|---|---|---:|---|---:|---:|
| buggy-forum | cross_linked_discussion_with_nested_moderation | 93494ede | 2471055070 | positive | 10 | 3945 |
| buggy-billing | transactional_nested_account_invoice_payment | 5e5d80a8 | 1583186088 | positive | 10 | 3946 |
| buggy-lab | deep_experiment_run_sample_result_graph | 5e7e0329 | 1585316649 | positive | 10 | 3947 |
| buggy-directory | shallow_flat_fanout_control | 85797ba0 | 2239331232 | negative | 8 | 3948 |

No seed search. One deterministic graph per identity. Historical apps stay regressions only.

Positive targets must qualify with at least two distinct handoff-capable chains from different families or child-workflow roles. The directory control must qualify with zero such chains and a nested branch chain shorter than `BRANCH_HORIZON`.

## Matrix

Policies: C1 `ghost-structural-memory`, G `ghost-structural-return-guard`, H `ghost-structural-horizon-handoff-guard`.

Positive targets at budgets 40, 80, and 120. Directory at budget 120 only. Browser seed 1. Thirty cells. No LLM policy and no BFS/DFS in the primary matrix.

## Outcome

`derive_v0315_outcome` chooses C, then D, then B, else A.

- C: protocol invalid, safety failure, bug loss, or a handoff on the negative control.
- D: safety passes, but fewer than two positive targets are actually evaluable.
- B: at least two targets are evaluable, but fewer than two fully transfer.
- A: at least two fresh shapes fully transfer, the guard's confirmed bugs are preserved on all four targets, and the negative control stays inactive.

Promotion readiness is `not_ready`, or `evidence_supports_productization_study` only after Outcome A. Never `promoted`, `default_ready`, or `production_ready`.

Product default remains `GhostPolicy` with frontier off and `sequence_mode=off`.

## Phase order

1. This protocol commit.
2. Generator, four targets, static qualification, suite freeze commit.
3. Only then the 30 cells.
4. Publish the derived outcome unchanged, including a negative or mixed result.
