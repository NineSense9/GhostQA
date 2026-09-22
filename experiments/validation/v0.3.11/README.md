# GhostQA v0.3.11 — Preregistered Multi-Target Replication Protocol

**Preregistered before any target-policy evaluation.**
`executed` is `false` at this commit.

Date: 2026-09-22
Starting HEAD: `ae1d20c77d12ac3520a2f966f7b2363a483b73ac`

## Research question

Does the exact same frozen v0.3.9 return-cycle guard replicate across multiple preregistered fresh application shapes, while preserving successful-return safety and C1 findings?

Success in this round means protocol integrity and reproducible evidence, not necessarily Outcome A.

## Identities

| Role | Identity | Freeze |
|---|---|---|
| Candidate | `ghost-structural-return-guard` | `experiments/frozen/ghost-return-cycle-guard-v0.3.9/freeze.json` |
| Historical C1 | `ghost-structural-memory` | `experiments/frozen/ghost-structural-v0.3.6/freeze.json` |
| Product default | NoFrontier, `sequence_mode=off` | unchanged; promotion prohibited |

## Preregistered fresh targets

These are preregistered fresh targets, not independently designed external benchmarks.

Seed rule: `seed(app_name) = int(SHA256("ghostqa-v0.3.11:" + app_name)[:8], 16)`.

| id | name | topology family | seed hex | seed |
|---|---|---|---|---:|
| T1 | buggy-crm | fanout hub / nested entity | `3f2065e3` | 1059087843 |
| T2 | buggy-wiki | cross-linked content graph | `befb469d` | 3204138653 |
| T3 | buggy-ops | deep nested / multi-parent | `fd7653f9` | 4252390393 |

Seeds cannot be rerolled after this commit.

## Matrix (fixed)

Per target, primary comparison:

- `ghost-structural-memory` and `ghost-structural-return-guard` at budgets `40, 80, 120`

Context baselines only at budget `120`:

- `ghost-nollm`, `bfs`, `dfs`

Policy seed: `[1]`. Skip-minimize. Dump evidence.

`6 + 3 = 9` cells per app, `27` cells total. No Monkey. No historical variant sweep. No extra budgets after outcomes.

## One-shot semantics

1. Commit this protocol (`executed=false`) — P0.
2. Implement the shared generator and three apps. App-only tests only. Do not run C1, guard, BFS, or DFS before freeze.
3. Freeze generator + generated targets. Commit — P1.
4. Prove git history contains P0 then P1.
5. Run the 27-cell matrix once. Rerun only exact infrastructure failures.
6. Compute Outcome A/B/C/D from the preregistered gates. Do not retrofit. Do not retune the candidate.

## Outcome gates

See `protocol.json` `outcome_gates`.

- **A** — multi-target replication with safety. Still not universal generalization.
- **B** — safe but mixed replication.
- **C** — harmful/regression. Never average away a harmful target.
- **D** — fewer than 2 of 3 targets present evaluable opportunities; do not raise budget.

Promotion-readiness may be computed. Product default does not change in this round.

## Authoring-bias disclosure (required in the published summary)

- Targets were authored after the guard existed.
- The candidate was frozen before this round.
- Identities, seeds, topology families, budgets, and bug-count ranges are preregistered before policy evaluation.
- These are preregistered fresh targets, not externally independent benchmarks.
- This is not universal generalization proof.
