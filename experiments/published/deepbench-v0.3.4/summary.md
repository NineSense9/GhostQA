# DeepBench v0.3.4 — Post-Reach Exploration

- **Date**: 2026-09-20
- **Benchmark freeze SHA**: `5355abd444eb4a4e99242c7629a1363c38e52a2a`
- **Algorithm SHA**: `baaa31f`
- **Product**: v0.4 preview (Ghost default = NoFrontier)
- **Runs**: 21, **n=1 deterministic** (not random seeds)
- **Holdout**: unscored
- **Real LLM**: skipped

Question: after reaching project-level workflow, does the agent **test** the deep state or only **walk**?

## Matrix

| strategy | budget | BDR | Deep-BDR | AUC | TTCB | TTDCB | depth | deferred | exploit | backtracks | confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DFS | 40 | 0.357 | 0 | 0.214 | 5 | — | 1 | — | — | — | D1–D4, D8 |
| DFS | 80 | 0.357 | 0 | 0.286 | 5 | — | 2 | — | — | — | D1–D4, D8 |
| DFS | 120 | **0.429** | **0.111** | 0.331 | 5 | 84 | 4 | — | — | — | D1–D4, D6, D8 |
| BFS | 40 | 0.286 | 0 | 0.145 | 8 | — | 1 | — | — | — | D1–D3, D8 |
| BFS | 80 | 0.357 | 0 | 0.239 | 8 | — | 2 | — | — | — | D1–D4, D8 |
| BFS | 120 | 0.357 | 0 | 0.279 | 8 | — | 3 | — | — | — | D1–D4, D8 |
| WorkflowBFS | 40–120 | 0.214 | 0.111 | 0.102–0.177 | 6 | 6 | 4 | — | — | — | D4, D6, D8 |
| Ghost-nollm (P0) | 40–120 | 0.214 | 0.111 | 0.139–0.189 | 6 | 6 | 4 | 0 | 0 | 0 | D4, D6, D8 |
| Ghost-deferred (P1) | 40 | 0.071 | 0.111 | 0.014 | 32 | 32 | 4 | 9 | 9 | 0 | D6 |
| Ghost-deferred | 80 | 0.214 | 0.111 | 0.068 | 32 | 32 | 4 | 13 | 13 | 4 | D4, D6, D8 |
| Ghost-deferred | 120 | **0.429** | **0.111** | 0.173 | 32 | 32 | 4 | 19 | 18 | 14 | D1–D4, D6, D8 |
| Ghost-exploit (P2) | 40 | 0.214 | 0 | 0.054 | 19 | — | 2 | 5 | 7 | 4 | D2, D4, D8 |
| Ghost-exploit | 80 | 0.357 | 0 | 0.184 | 19 | — | 2 | 11 | 13 | 15 | D1–D4, D8 |
| Ghost-exploit | 120 | 0.357 | 0 | 0.242 | 19 | — | 3 | 22 | 26 | 22 | D1–D4, D8 |
| Ghost-postreach (P3) | 40 | 0.214 | 0 | 0.054 | 19 | — | 2 | 5 | 7 | 4 | D2, D4, D8 |
| Ghost-postreach | 80 | 0.357 | 0 | 0.184 | 19 | — | 2 | 11 | 13 | 15 | D1–D4, D8 |
| Ghost-postreach | 120 | 0.357 | 0 | 0.242 | 19 | — | 3 | 22 | 26 | 22 | D1–D4, D8 |

DFS@120 TTDCB from this run's first_step_by_bug should be checked; table uses Deep-BDR only if needed.

## Pareto (budget 120)

| policy | max_depth | deferred | exploit | Deep-BDR | BDR |
|---|---|---|---|---|---|
| Ghost-nollm | 4 | 0 | 0 | 0.111 | 0.214 |
| Ghost-deferred | 4 | 19 | 18 | 0.111 | 0.429 |
| Ghost-exploit | 3 | 22 | 26 | 0 | 0.357 |
| Ghost-postreach | 3 | 22 | 26 | 0 | 0.357 |
| WorkflowBFS | 4 | 0 | 0 | 0.111 | 0.214 |
| DFS | 4 | — | — | 0.111 | 0.429 |

## Q1 — Is the plateau “deferred never resumes”?

**Yes for P0.** Ghost-nollm @120: deferred=0, same D4/D6/D8 as WorkflowBFS, never D1–D3. It walks the project workflow and stops testing.

## Q2 — Does resuming deferred increase deep interaction coverage?

**Yes.** Ghost-deferred @120: deferred=19, deep_states=24, states=38 vs P0's 13. Unique interactions rise. Deep-BDR stays 0.111 (D6 kept).

## Q3 — Probe+commit vs input-only?

Ghost-postreach ≈ Ghost-exploit on this freeze (same confirmed set). Probe+commit did **not** add D5–D14. Input-only deferred (P1) was the one that **tied DFS BDR** while keeping D6.

## Q4 — State exploit budget: more testing without a sink?

**Partial.** P2/P3 raise exploit_actions (7→26) and BDR vs P0 at 80/120, but **max_depth drops 4→2/3 and D6 disappears**. That is a local sink on hub pages (dashboard/settings), not a full v0.3 payload explosion. Entry was tightened (no lobby NEW fuzz); still not enough.

## Q5 — Local backtracking cover hub branches?

Backtracks: P1@120=14, P3@120=22. They visit more clusters (25–29 vs P0's 12) and pick up D1–D3. They do **not** cover D5/D7/D9–D14.

## Q6 — Deep-BDR up?

**No.** Best Deep-BDR remains 0.111 (D6 only). D5, D7, D9–D14: no candidate, no confirm. Next bottleneck is likely sequence/semantic/cross-page, not “more LONG payloads”.

## D5–D14 (Judge only, budget 120)

| bug | P0 | deferred | exploit/postreach | DFS |
|---|---|---|---|---|
| D5 | unreached | unreached | unreached | unreached |
| D6 | confirmed | confirmed | unreached | confirmed |
| D7 | unreached | unreached | unreached | unreached |
| D8 | confirmed | confirmed | confirmed | confirmed |
| D9–D14 | unreached | unreached | unreached | unreached |

## Progression regression

| | depth | D6 | TTCB |
|---|---|---|---|
| P0 | 4 | yes | 6 |
| P1 deferred | 4 | yes | 32 (slower) |
| P2/P3 | 2–3 | **no** | 19 |

P2/P3 fail the protection metric. P1 keeps reach, pays latency.

## Case studies (formal runs, seed=1)

**A. P0 ghost-nollm b=40:** depth=4, D6 at TTCB=6, deferred=0. Reaches project, does not resume fuzz.

**B. P1 ghost-deferred b=120:** depth=4, deferred=19, confirms D1–D4+D6+D8 (same set as DFS). TTCB=32.

**C. P3 ghost-postreach b=40:** depth=2, D6 gone, exploit=7. Too much hub exploitation.

## Holdout

Unscored. No H1/H2 used to pick thresholds.

## Negative results

1. Full postreach (probe+commit+back) **regresses D6**.
2. Deferred resume **does not raise Deep-BDR** above 0.111.
3. D5/D7/D9–D14 remain unreached — not a payload-order problem to hill-climb.
4. Jaccard/aHash / semantic variant untouched.
5. n=1 deterministic; no seed-shopping.

## Judgment

GhostQA's bottleneck moved from **navigation** to **what to test after arrival**. Bounded deferred resume (P1) is the only new mode that keeps workflow depth and matches DFS BDR@120. Full exploit/postreach is **not** default. Product Ghost stays **NoFrontier + first-wave**; `ghost-deferred` is experimental.
