# DeepBench v0.3.3 — Frontier Relocation Study

- **Date**: 2026-09-20
- **Benchmark freeze SHA**: `5355abd444eb4a4e99242c7629a1363c38e52a2a` (unchanged)
- **Algorithm SHA**: `50f9285` (relocation ledger + modes). Product remains **v0.4 preview**.
- **Runs**: 54. Policies × budgets `{40,80,120}` × 3 **repeated trials** (Ghost-noLLM is deterministic; 1/2/3 are not stochastic seeds).
- **Primary local policy**: Ghost-noLLM (same scoring, PayloadPolicy, Oracle as v0.3.2).
- **Holdout**: unscored.
- **Real LLM**: skipped (not used to tune relocation).
- **Dashboard**: frozen; not part of this study.

This round asks: **is reset+replay relocation worth paying for?** It does not retune DeepBench, similarity, payloads, or WorkflowBFS.

## Ablation modes

| id | policy | what it does |
|---|---|---|
| R1 | `ghost-nollm-nofrontier` | no planner, no reset |
| R0 | `ghost-nollm` | v0.3.2 opportunity-cost relocate (**inventory sum**, path cost deducted in planner **and** policy) |
| Shadow | `ghost-nollm-shadow` | R0 recommendation recorded, **never executed** |
| R2 | `ghost-nollm-marginal` | best pending interaction + log breadth − **single** restore_cost + budget reserve |
| R3 | `ghost-nollm-momentum` | R2 + NEW-state streak raises relocate threshold |
| R4 | `ghost-nollm-lease` | R3 + must do K=3 productive actions / novelty before next hop |

## Matrix

Trials were identical within each policy×budget (std=0).

| strategy | budget | n | BDR | Deep-BDR | AUC | TTCB | TTDCB | reloc | restore | productive | wasted | chains | episodes | recs | confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ghost-nollm-nofrontier | 40 | 3 | 0.214 | 0.111 | 0.139 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 0 | D4, D6, D8 |
| ghost-nollm-nofrontier | 80 | 3 | 0.214 | 0.111 | 0.177 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 0 | D4, D6, D8 |
| ghost-nollm-nofrontier | 120 | 3 | 0.214 | 0.111 | 0.189 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 0 | D4, D6, D8 |
| ghost-nollm (R0) | 40 | 3 | 0.143 | 0 | 0.070 | 14 | — | 7 | 0.325 | 0.286 | 0.429 | 3 | 8 | 7 | D2, D4 |
| ghost-nollm (R0) | 80 | 3 | 0.286 | 0 | 0.162 | 14 | — | 12 | 0.275 | 0.417 | 0.333 | 3 | 13 | 12 | D1–D4 |
| ghost-nollm (R0) | 120 | 3 | **0.357** | 0.111 | 0.207 | 14 | 113 | 13 | 0.192 | 0.538 | 0.231 | 3 | 14 | 13 | D1–D4, D6 |
| ghost-nollm-shadow | 40 | 3 | 0.214 | 0.111 | 0.139 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 8 | D4, D6, D8 |
| ghost-nollm-shadow | 80 | 3 | 0.214 | 0.111 | 0.177 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 14 | D4, D6, D8 |
| ghost-nollm-shadow | 120 | 3 | 0.214 | 0.111 | 0.189 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 21 | D4, D6, D8 |
| ghost-nollm-marginal | 40 | 3 | 0.214 | 0.111 | 0.136 | 6 | 6 | 1 | 0.050 | 1.0 | 0 | 0 | 2 | 1 | D4, D6, D8 |
| ghost-nollm-marginal | 80 | 3 | 0.214 | 0.111 | 0.175 | 6 | 6 | 1 | 0.025 | 1.0 | 0 | 0 | 2 | 1 | D4, D6, D8 |
| ghost-nollm-marginal | 120 | 3 | 0.214 | 0.111 | 0.188 | 6 | 6 | 1 | 0.017 | 1.0 | 0 | 0 | 2 | 1 | D4, D6, D8 |
| ghost-nollm-momentum | 40–120 | 3 | 0.214 | 0.111 | 0.139–0.189 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 0 | D4, D6, D8 |
| ghost-nollm-lease | 40–120 | 3 | 0.214 | 0.111 | 0.139–0.189 | 6 | 6 | 0 | 0 | — | — | 0 | 1 | 0 | D4, D6, D8 |

## Q1 — Where does current Frontier fail?

All four:

1. **Score-scale mismatch.** Local utility is one next-action `_program_score` (~0.5–2.4). Remote `target.score` is a **linear sum** of pending opportunities. Shadow@40 step 8: local=2.12, r0_net=2.95 on a path_len=6 page, **marginal_net=−0.07**. Inventory sum says “go”; marginal value says “do not”.
2. **Restore cost double-counted in R0** (planner `path_cost * len` **and** policy `0.25 * len`). Conservative, but the logged `planner_restore_cost` vs `policy_restore_cost` make it explicit. It did **not** stop over-jumping, because inventory still dominates.
3. **Target ranking** repeatedly names the same high-inventory node (shadow: 21 recommendations @120, most `same_target` stays after the first).
4. **Over-jumping / chains.** R0@40: 7 relocates, 3 chains, wasted_rate=0.429, restore_ratio=0.325. First hop at step 6 is wasted and immediately chained.

## Q2 — Did marginal utility cut wasted relocation?

Yes. R0@40 wasted_rate=0.429 with 7 hops. Marginal: **1 relocate, productive_rate=1.0, wasted_rate=0, chains=0**. Stay reasons @40: 22 `local_better`, 10 `reserve`, 6 `warmup`.

BDR did **not** rise above NoFrontier. Marginal matches NoFrontier’s D4/D6/D8 and never picks up R0’s later D1–D3.

## Q3 — Did momentum reduce workflow interruption?

Yes, by refusing to hop at all. Momentum@40 stay reasons: 24 `local_better`, 10 `reserve`, 6 `warmup`, **0 relocate**. Trace matches NoFrontier (D6 at TTCB=6). R0 interrupts at step 6 (TTCB=14, Deep-BDR=0 at budget 40).

## Q4 — Did lease cut relocate chains?

Lease also executed **zero** relocates (same as momentum on this app). Chains went from 3 (R0 every budget) to 0. There was no remaining hop for the lease to constrain; momentum+reserve already suppressed them.

## Q5 — BDR / Deep-BDR?

- Deep-BDR@40: NoFrontier / Shadow / Marginal / Momentum / Lease = **0.111 (D6)**. R0 = **0**.
- BDR@120: R0 = **0.357** (D1–D4, D6). Everyone else = **0.214** (D4, D6, D8).
- DFS@120 from v0.3.2 remains 0.429. Nobody here beats DFS.

Relocation is therefore **not uniformly negative**: at 120 it buys shallow D1–D3 after paying restore, but it **delays or drops D6** at the budgets where local policy already has it.

## Q6 — Efficiency without BDR gains?

| | restore_ratio @40 | episodes @40 | TTCB |
|---|---|---|---|
| R0 | 0.325 | 8 | 14 |
| Marginal | 0.050 | 2 | 6 |
| Momentum/Lease/NoFrontier | 0 | 1 | 6 |

Marginal keeps Deep-BDR and cuts restore waste vs R0. It does not create a new discovery curve beyond NoFrontier.

## Shadow Frontier

Shadow execution **equals NoFrontier** (reloc=0, D4/D6/D8, TTCB=6). The planner still *wanted* 8/14/21 hops at 40/80/120. First would-be hop is step 6, the same step NoFrontier confirms D6. That is direct evidence the **R0 recommendation is the wrong decision**, not merely an expensive restore of a good target.

Most later shadow recs have `marginal_net < 0` while `r0_net ≈ 2.95` and `path_len=6`. Ranking is the primary defect; restore cost is secondary.

## Trace case studies (formal runs)

### Case A — interrupting D6 (R0 vs Shadow/NoFrontier)

- **R0** `ghost-nollm` budget=40 trial=1, **step 6**: relocate path_len=2, r0_net=3.35, outcome **wasted + chain**. Next hop step 8. Confirmed `{D2,D4}`, Deep-BDR=0, TTCB=14, restore_ratio=0.325.
- **Shadow** same budget/trial: records the same step-6 recommendation (`executed=false`) and **stays**. Confirmed `{D4,D6,D8}`, TTCB=6.
- **NoFrontier**: identical confirmed set, no planner.

### Case B — a later productive hop (R0 @120)

- **R0** `ghost-nollm` budget=120 trial=1, **step 13**: path_len=1, r0_net=2.15, **productive**, `actions_until_new_state=3`, `finding_within_5=true`.
- Same run still opens with the wasted step-6 chain. Net: BDR 0.357 including D6 at TTCB=14 / TTDCB=113.

### Case C — marginal’s single hop

- **Marginal** budget=40 trial=1, **step 7**: path_len=2, marginal_net=1.37 (r0 would have been 3.35), **productive**, until_new=3, finding_within_5. Then local policy continues. Confirmed `{D4,D6,D8}` like NoFrontier. No chain.

No cherry-picked demo apps. Files: `relocation_traces/ghost-nollm_b40_s1.jsonl`, `ghost-nollm-shadow_b40_s1.jsonl`, `ghost-nollm_b120_s1.jsonl`, `ghost-nollm-marginal_b40_s1.jsonl`.

## Holdout

Unscored. Config frozen after the NoLLM matrix above; H1/H2 were not used to pick thresholds.

## Negative results (keep)

1. R0 opportunity-cost relocate **over-jumps**. First hop is typically wasted.
2. Inventory-sum remote score is **not** on the same scale as local next-action utility.
3. R0 double path-cost is real; fixing only the double-count (without changing the sum) is not what we shipped as default — R2 changes the *value* side.
4. Marginal/momentum/lease **do not beat NoFrontier on BDR**. They mostly *stop hopping*.
5. R0@120 higher BDR is real (D1–D3) and must not be erased; it is paid for with restore_ratio and delayed D6.
6. DFS@120 still has the highest published BDR on this freeze.
7. WorkflowBFS plateau, Jaccard/aHash, semantic variant: recorded, not touched.
8. Real LLM not used for this study.

## Engineering judgment

**Reset+replay Frontier should be disabled by default.**

- Default Ghost-noLLM: `use_frontier=False` (current NoFrontier behavior).
- R0 `opportunity` mode: **experimental**, kept for replay of v0.3.2.
- `marginal` / `momentum` / `lease`: **experimental**. Marginal is the only new mode that still hops, and it hops once productively without beating NoFrontier.

This is not “Frontier theory is false”. It is: **under this Web action budget, global reset+replay of an inventory-sum frontier is not cost-effective as the default.** A larger state space, or a restore cheaper than full reset, would need a new study.

Traces: `experiments/published/deepbench-v0.3.3/relocation_trace.jsonl` and `relocation_traces/`.
