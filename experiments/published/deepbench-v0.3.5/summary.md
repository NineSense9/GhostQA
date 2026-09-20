# DeepBench v0.3.5 — Sequence-Aware Branch Exploration

- **Date**: 2026-09-20
- **Benchmark freeze SHA**: `5355abd444eb4a4e99242c7629a1363c38e52a2a`
- **Algorithm SHA**: `a863553`
- **Product**: v0.4 preview (Ghost default still NoFrontier)
- **Runs**: 24, **n=1 deterministic**
- **Holdout**: unscored
- **Real LLM**: skipped

Question: after reaching the project hub, can the agent **cover multiple branches** and finish **short mutation→followup sequences** without reset+replay?

## Matrix

| strategy | budget | BDR | Deep-BDR | AUC | TTCB | TTDCB | depth | hubs* | branches started/done | mutations | followups | returns | confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DFS | 40 | 0.357 | 0 | 0.214 | 5 | — | 1 | — | — | — | — | — | D1–D4, D8 |
| DFS | 120 | 0.429 | 0.111 | 0.331 | 5 | 84 | 4 | — | — | — | — | — | D1–D4, D6, D8 |
| BFS | 120 | 0.357 | 0 | 0.279 | 8 | — | 3 | — | — | — | — | — | D1–D4, D8 |
| WorkflowBFS | 40–120 | 0.214 | 0.111 | 0.102–0.177 | 6 | 6 | 4 | — | — | — | — | — | D4, D6, D8 |
| Ghost-nollm (S0) | 40–120 | 0.214 | 0.111 | 0.139–0.189 | 6 | 6 | 4 | — | — | — | — | — | D4, D6, D8 |
| Ghost-deferred | 40 | 0.071 | 0.111 | 0.014 | 32 | 32 | 4 | — | — | — | — | — | D6 |
| Ghost-deferred | 120 | **0.429** | 0.111 | 0.173 | 32 | 32 | 4 | — | — | — | — | — | D1–D4, D6, D8 |
| Ghost-branch (S1) | 40–120 | 0.143 | 0 | 0.086–0.124 | 9 | — | 3 | 1 | 1 / 0 | 0 | 0 | 0 | D4, D8 |
| Ghost-followup (S2) | 40–120 | 0.143 | 0 | 0.086–0.124 | 9 | — | 3 | 1 | 1 / 0 | 35–115 | 0 | 0 | D4, D8 |
| Ghost-sequence (S3) | 40 | 0.143 | **0.222** | 0.071 | 14 | 14 | 4 | 14* | **8 / 6** | 36 | 12 | 10 | **D6, D12** |
| Ghost-sequence | 80 | 0.143 | **0.222** | 0.107 | 14 | 14 | 4 | 34* | 8 / 6 | 72 | 22 | 24 | **D6, D12** |
| Ghost-sequence | 120 | 0.143 | **0.222** | 0.119 | 14 | 14 | 4 | 57* | 8 / 6 | 108 | 33 | 39 | **D6, D12** |

\* `hub_count` is per-`state_id` (semantic variants inflate it). `branches_started=8` is the coverage signal.

## Q1 — Multiple branches after hub?

**S3 yes.** 8 branches started, 6 completed, return_success 10–39. S0 has no branch ledger (does not systematically expand). S1/S2 start 1 branch and never complete.

## Q2 — Follow-up after mutation?

**S3 yes.** followup_actions 12 / 22 / 33. S2 records mutations (35–115) but followup_actions=0 (no commitment to stay on the mutated page).

## Q3 — Short 2–4 step sequences without LLM?

**S3 yes, NoLLM.** D12 = add-member → remove → count inconsistency. sequences_completed 10–39. Horizon=3, no LLM.

## Q4 — Branch commitment vs D6 / depth?

**S3 keeps D6 and depth=4.** S1/S2 **lose D6** (depth 3). Commitment+return is the difference.

## Q5 — First short-chain deep bugs?

**D12 confirmed** at budget 40 (TTDCB=14). D7 / D10 / D14 not confirmed. D5 still deferred-payload territory.

## D5–D14 prefix (Judge, sequence@120)

| bug | area | prefix | candidate | confirmed |
|---|---|---|---|---|
| D5 | project (login+wizard likely) | boundary input not this round | no | no |
| D6 | wizard | empty name | yes | **yes** |
| D7 | billing/export | unknown | no | no |
| D8 | help loop | — | yes | no (S3) / yes (S0) |
| D9 | members+guest+archive | too long | no | no |
| D10 | tasks complete/reopen | unknown | no | no |
| D11 | coupon/qty | no | no | no |
| D12 | members add+remove | **yes** | yes | **yes** |
| D13 | archive+unarchive+delete | no | no | no |
| D14 | rename→dashboard | no | no | no |

## Progression regression

| | depth | D6 | TTCB |
|---|---|---|---|
| S0 | 4 | yes | 6 |
| S1/S2 | 3 | **no** | 9 |
| S3 | 4 | **yes** | 14 |
| deferred@120 | 4 | yes | 32 |

S3 trades TTCB 6→14 and drops D4/D8 for D12. Not a D6 regression.

## Case studies (formal, seed=1)

**A. S0 ghost-nollm b=40:** project reached, D4/D6/D8, no branch ledger. Hub not systematically expanded.

**B. S3 ghost-sequence b=40:** branches_started=8, completed=6, return_success=10, D6+D12.

**C. S3 mutation followup:** followup_actions=12, D12 (member add→remove). S2 mutates a lot but never followups.

**Negative:** S1/S2 start one branch, never return, lose D6. hub_count on S3 is inflated by variants.

## Holdout

Unscored.

## Negative results

1. S1 branch-only is not enough (no commitment/return).
2. S2 followup without commitment does not execute followups.
3. S3 BDR 0.143 < DFS 0.429; lost shallow D4/D8.
4. D7/D10/D14 still out. Next: longer sequences / cross-page obs / semantics.
5. hub_count per-sig is a noisy metric.

## Judgment

Yes: remaining DeepBench gaps are **short-horizon sequences on a hub**, not “how to reach project”.

- Product default stays **NoFrontier** (S0): best TTCB for D6, no D12.
- `ghost-sequence` is **experimental**: first confirmed D12, Deep-BDR 0.222, D6 kept.
- Do not default S3 yet (loses D4/D8, noisy hub_count).

No Jaccard/aHash this round. No Real LLM. No Dashboard redesign.
