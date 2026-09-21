# DeepBench v0.3.6 — Contextual Sequence Memory

- **Date**: 2026-09-21
- **Benchmark freeze SHA**: `5355abd444eb4a4e99242c7629a1363c38e52a2a`
- **Algorithm SHA**: `40434be`
- **Product**: v0.4 preview (Ghost default still NoFrontier, no experimental sequence)
- **n=1 deterministic NoLLM**
- **Holdout / Real LLM**: unscored / skipped

Question: should the tester remember every exact variant, collapse a cluster into one forever-tested set, or remember structural workflow identity plus meaningful semantic change?

## Ablations

| id | policy | meaning |
|---|---|---|
| C0 | `ghost-sequence` | frozen v0.3.5 exact-sig sequence memory |
| C1 | `ghost-structural-memory` | cluster-level branch memory, no contextual retest |
| C2 | `ghost-contextual` | C1 + context-sensitive retest + in-branch action novelty |
| C3 | `ghost-contextual-crossview` | C2 + recent visible-fact cross-view bonus |

## Headline (@120)

| strategy | BDR | Deep-BDR | TTCB | TTDCB | confirmed | unique branches started | attempts/branch |
|---|---|---|---|---|---|---|---|
| DFS | 0.429 | 0.111 | 5 | 84 | D1–D4, D6, D8 | — | — |
| BFS | 0.357 | 0 | 8 | — | D1–D4, D8 | — | — |
| Ghost-nollm | 0.214 | 0.111 | 6 | 6 | D4, D6, D8 | — | — |
| Ghost-deferred | **0.429** | 0.111 | 32 | 32 | D1–D4, D6, D8 | — | — |
| C0 sequence | 0.143 | 0.222 | 14 | 14 | D6, D12 | 8 | **10.875** |
| C1 structural | **0.429** | **0.667** | 14 | 14 | D6, D7, D11–D14 | **19** | **2.789** |
| C2 contextual | **0.429** | **0.667** | 14 | 14 | D6, D7, D11–D14 | 19 | 3.105 |
| C3 cross-view | **0.429** | **0.667** | 14 | 14 | D6, D7, D11–D14 | 19 | 2.632 |

C1 ties DFS/deferred on BDR and **beats them on Deep-BDR** (0.667 vs 0.111). Guardrails: **D6 and D12 kept**, depth=4, TTCB=14.

## Q1 — exact variants and meaningless repeats?

C0 @120: 8 unique branches, 87 starts, **10.875 attempts/branch**, 57 exact hub variants vs 3 canonical hubs. Yes: variant fragmentation is the waste.

## Q2 — cluster-level persistent memory reduce repeats?

C1 @120: 19 unique branches, 53 starts, **2.789 attempts/branch**. Repeat cost dropped ~4× while **coverage rose** (8→19 unique branches). Confirmed 2→6.

## Q3 — is pure structural memory too coarse?

Not on this freeze. C1 found D7/D11/D13/D14 that C0 missed. It did **not** skip context-sensitive deletes that this benchmark needed. That does **not** prove cluster memory is always enough.

## Q4 — does C2 remember enough and retest when meaning changes?

C2 matches C1's confirmed set at 80/120. Retests fire (40 @120, 22 productive @80). It does not add a new confirmed bug beyond C1. Early C2 hard-picked retests and **got stuck** (0 bugs, depth 3); after making retest additive, C2 recovered to C1. Context layer is optional, not the source of the Deep-BDR jump.

## Q5 — existing-EID follow-up vs new-EID only?

Unit tests show in-page Complete/Reopen can score contextual novelty without new eids. Frozen C2 did not convert that into extra confirmed bugs vs C1.

## Q6 — mutation refresh?

`mutation_refreshes=0` on frozen C2/C3. Bounded refresh did not fire on this app. No local-sink from refresh after the pick_override fix.

## Q7 — cross-view?

C3 records 32/66/94 cross-view checks. @40 it **drops D7** vs C1/C2 (Deep-BDR 0.333). @80/120 same six bugs as C1. Cross-view stays experimental; not required for the headline.

## Q8 — Deep-BDR above 0.222?

**Yes. 0.667** (C1/C2/C3 @80–120) = D6, D7, D11, D12, D13, D14. Remaining: D5 (payload), D9 (long chain), D10 (not confirmed). Next bottleneck is not variant-hub bookkeeping.

## Guardrails / shallow trade-off

| | D4 | D6 | D8 | D12 | depth | TTCB |
|---|---|---|---|---|---|---|
| Ghost-nollm | yes | yes | yes | no | 4 | 6 |
| C0 | no | **yes** | no | **yes** | 4 | 14 |
| C1/C2 @80+ | no | **yes** | no | **yes** | 4 | 14 |
| DFS@120 | yes | yes | yes | no | 4 | 5 |

Sequence family still trades shallow D1–D4/D8 for deep workflow bugs. Do not hide that.

## D5–D14 (Judge, C1@120)

| bug | confirmed C0 | confirmed C1 |
|---|---|---|
| D5 | no | no |
| D6 | **yes** | **yes** |
| D7 | no | **yes** |
| D8 | no | no |
| D9 | no | no |
| D10 | no | no |
| D11 | no | **yes** |
| D12 | **yes** | **yes** |
| D13 | no | **yes** |
| D14 | no | **yes** |

## Product

Do **not** switch the Ghost CLI default this round. C1 is experimental (`ghost-structural-memory`). Default remains NoFrontier, `sequence_mode=off`.
