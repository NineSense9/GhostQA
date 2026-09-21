# GhostQA v0.3.9 — Return-Cycle Guard

**BuggyShop is an inspected mechanism-development case. DeepBench is regression-only. H1/H2 are excluded. This round does not test generalization.**

**Product default unchanged:** NoFrontier, `sequence_mode=off`.

**Candidate isolation:** implemented in `ghostqa/exploration/return_cycle_guard.py`. Historical C1 freeze (`ghost-structural-v0.3.6`) still verifies. Frozen five exploration files were not modified.

**Exact guard:** Candidate escapes only when an unresolved return phase revisits the same exact destination signature before matching its parent. **No return-attempt threshold N.** Escape is **abandonment, not successful return.**

## Outcome

**Outcome A — Mechanism repaired, regression-safe** (computed from protocol gates, not chosen in prose).

## BuggyShop (inspected, descriptive bug IDs)

| policy | states | URLs | return_attempt | returned terminal | cycle escapes | post-escape new states | confirmed (descriptive) |
|---|---:|---:|---:|---:|---:|---:|---|
| C1 structural | 6 | 4 | 116 | 0 | 0 | — | W5 |
| return-guard | 22 | 8 | 15 | 0 | **4** | **15** | W5, W6, W9, W10 |

Baseline reproduced the v0.3.8 lock (6/4/116/0). First escape at step 6; first novel URL at step 10 (`login.html`, `profile.html`, `promo.html`, `register.html`). Escaped branches are not counted returned.

## DeepBench (regression only)

| policy | budget | BDR | Deep-BDR | depth | confirmed | cycle escapes | attempts/branch |
|---|---:|---:|---:|---:|---|---:|---:|
| C1 | 40 | 0.286 | 0.444 | 4 | D6 D7 D11 D12 | — | 1.200 |
| guard | 40 | 0.286 | 0.444 | 4 | D6 D7 D11 D12 | 0 | 1.200 |
| C1 | 80 | 0.429 | 0.667 | 4 | D6 D7 D11–D14 | — | 1.947 |
| guard | 80 | 0.429 | 0.667 | 4 | D6 D7 D11–D14 | 0 | 1.947 |
| C1 | 120 | 0.429 | 0.667 | 4 | D6 D7 D11–D14 | — | 2.789 |
| guard | 120 | 0.429 | 0.667 | 4 | D6 D7 D11–D14 | **0** | 2.789 |

lost_from_baseline_120 = []. Guard dormant on this historical workflow.

## Reproduce

```text
python -m benchmark.return_cycle_guard_reproduce --root experiments/published/return-cycle-guard-v0.3.9 --verify
```
