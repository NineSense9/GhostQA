# GhostQA v0.3.12 — Nested-Hub Parent Preservation

**Preregistered before any candidate target evaluation.**
`executed` is `false` at this commit.

Date: 2026-09-22
Starting HEAD: `ab7a11031fe9f3f0ad84aaa67a9e33dc9bef4d85`

## Research question

Can a minimal parameter-free nested-hub preservation rule prevent active outer sequences from being prematurely terminated as `lost_parent`, allowing them to reach horizon/return without breaking the proven return-cycle safety behavior?

This is a mechanism-repair question. `buggy-crm` and `buggy-ops` are inspected mechanism-development cases carried forward from the frozen v0.3.11 suite. They cannot support a fresh-generalization claim.

Success in this round means protocol integrity and reproducible evidence, not necessarily Outcome A.

## Why this round exists

v0.3.11 was Outcome D. Wiki reached return phase and showed guard transfer. CRM and Ops never started a return phase: an outer `branch_start` met a nested hub, the nested branch click emitted `lost_parent`, and a new sequence overwrote the parent. Commitment never reached the horizon, so the v0.3.9 return-cycle guard had nothing to guard.

The measurement detector is `benchmark/nested_hub_detector.py`. It does not choose actions and it does not hardcode historical counts.

## Identities

| Role | Identity | Freeze |
|---|---|---|
| Candidate | `ghost-structural-nested-return-guard` | `experiments/frozen/ghost-nested-hub-guard-v0.3.12/freeze.json` (P1, not this commit) |
| Historical guard | `ghost-structural-return-guard` | `experiments/frozen/ghost-return-cycle-guard-v0.3.9/freeze.json` |
| Historical C1 | `ghost-structural-memory` | `experiments/frozen/ghost-structural-v0.3.6/freeze.json` |
| Product default | NoFrontier, `sequence_mode=off` | unchanged; promotion prohibited |

The candidate lives in a new module, `ghostqa/exploration/nested_hub_guard.py`. Frozen sequence, guard, policy, memory, interaction, and payload sources stay unmodified.

## Semantic rule

Preservation applies only when, before the branch-start mutation, all of the following hold:

- mode is sequence-like
- the current state is a hub
- the chosen action is a branch click
- an outer sequence instance is open
- `active_branch` is non-empty
- `returning` is false
- `commitment_left > 0`

The outer instance, outer branch, and outer parent stay in place. The click is audited as `nested_branch_followup` and consumes the existing commitment. It does not emit `lost_parent`, does not open a new sequence, and does not reset commitment to `BRANCH_HORIZON`.

There is no parent stack, no threshold N, no URL rule, and no app-specific exception. Once return phase begins, v0.3.9 exact-signature escape semantics are unchanged.

## Matrix (fixed)

CRM and Ops only:

- policies: `ghost-structural-memory`, `ghost-structural-return-guard`, `ghost-structural-nested-return-guard`
- budgets: `40`, `80`, `120`
- seed: `1`

18 cells. No BFS/DFS in this matrix. No budget change after the outcome.

Historical regression at budget 120, candidate only, judged against the published guard's confirmed set:

- Wiki (v0.3.11)
- BuggyDesk (v0.3.10)
- BuggyShop (v0.3.9)
- DeepBench (v0.3.9)

Confirmed-bug loss on any of those is Outcome C. Exact state-count equality is not required.

## One-shot semantics

1. Commit this protocol (`executed=false`) — P0.
2. Implement the isolated candidate and N1–N12 / differential / S1–S7 / exhaustive checks. Do not run CRM or Ops policy evaluation yet.
3. Freeze the candidate. Commit — P1.
4. Prove git history contains P0 then P1.
5. Run the 18-cell matrix once, then the regression cases. Rerun only exact infrastructure failures.
6. Compute Outcome A/B/C/D from `derive_v0312_outcome`. Do not retrofit the rule.

## Outcome gates

See `protocol.json` `outcome_gates`. Priority is C, then D, then A, otherwise B.

- **A** — both inspected cases repair the nested-hub lifecycle and historical confirmed bugs remain. Still not generalization.
- **B** — safe, but only a partial repair.
- **C** — safety failure, bug loss, freeze break, or app-specific logic. Do not advance the candidate.
- **D** — the historical preemption is not reproduced, or the candidate removes it on neither mechanism case.

## Scope

CRM and Ops were already analyzed in v0.3.11. A repair here is a mechanism result on inspected cases. v0.3.13 would be the round that asks whether the frozen repair transfers to a fresh target.
