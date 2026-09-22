# GhostQA v0.3.10 — Fresh Cross-App Transfer Protocol

**Preregistered before any target-policy evaluation.**
`executed` is `false` at this commit.

Date: 2026-09-22
Starting HEAD: `87c669f73a295ec7568a9a6f491c4ecb7a329188`

## Research question

Does the frozen v0.3.9 return-cycle guard transfer to a fresh application shape without introducing false escapes or return regressions?

Success in this round means protocol integrity and reproducible evidence, not necessarily Outcome A.

## Identities

| Role | Identity | Freeze |
|---|---|---|
| Candidate | `ghost-structural-return-guard` (`ReturnCycleGuardGhostPolicy`) | `experiments/frozen/ghost-return-cycle-guard-v0.3.9/freeze.json` |
| Historical C1 | `GhostPolicy(llm=None, use_frontier=False, sequence_mode="structural")` | `experiments/frozen/ghost-structural-v0.3.6/freeze.json` |
| Fresh target | BuggyDesk (`apps/buggy-desk/`) | `experiments/frozen/buggy-desk-v0.3.10/freeze.json` (after app freeze commit) |
| Product default | NoFrontier, `sequence_mode=off` | unchanged; promotion prohibited |

Guard semantics remain the v0.3.9 freeze:

- exact destination signature repeat
- unresolved return phase
- parent unmatched
- first exact repeat triggers escape (abandonment, not successful return)
- no threshold N
- no cluster-only trigger

## Policy matrix (fixed)

Primary: `ghost-structural-memory`, `ghost-structural-return-guard`

Context: `ghost-nollm`, `bfs`, `dfs`

Excluded: Monkey, `ghost-sequence`, contextual variants.

Budgets: `40, 80, 120`. Primary outcome budget: `120`.

Seeds: `[1]`. All matrix policies are deterministic; no seed picking after outcomes.

## One-shot semantics

1. Commit this protocol (`executed=false`).
2. Author BuggyDesk with app-only checks. Do not run C1, guard, BFS, DFS, or product baseline before freeze.
3. Freeze and commit the target.
4. Prove Git history contains the protocol commit and the target-freeze commit.
5. Run the matrix once. Rerun only exact cells that fail for infrastructure reasons.
6. Compute Outcome A/B/C/D from the preregistered gates. Do not retrofit.

## Contamination

Do not tune candidate behavior using BuggyShop, DeepBench D1–D14, holdout H1/H2, v0.3.8/v0.3.9 traces, or new BuggyDesk policy results.

Prefer zero changes to `ghostqa/exploration/return_cycle_guard.py`. If a genuine correctness bug is found before target-policy execution: stop, document it, and version a new candidate explicitly.

## Outcome gates

See `protocol.json` `outcome_gates`. Summary:

- **A** — fresh transfer with safety (opportunity, valid escape, post-escape novelty, no C1 bug loss, S1–S5 hold, historical regression and freezes pass).
- **B** — safety passes, no C1 bug loss, but no demonstrated transfer benefit.
- **C** — false escape, return inflation, C1 bug loss, or historical invariant break.
- **D** — no evaluable return-cycle opportunity under the preregistered budget; do not raise budget or redesign the app.

BFS/DFS/default are context, not outcome gates.

## Authoring-bias disclosure (required in the published summary)

- BuggyDesk was authored after v0.3.9 existed.
- The v0.3.9 candidate was frozen before target evaluation.
- BuggyDesk will be frozen before policy evaluation.
- This is a fresh one-target cross-app transfer test, not an independently designed external benchmark and not universal generalization proof.
