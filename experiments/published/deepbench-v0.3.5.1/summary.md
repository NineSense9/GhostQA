# DeepBench v0.3.5.1 — Sequence Measurement Correctness

- **Date**: 2026-09-20
- **Benchmark freeze SHA**: `5355abd444eb4a4e99242c7629a1363c38e52a2a`
- **Measurement SHA**: `090466d`
- **Product**: v0.4 preview
- **Runs**: 12 (ghost-nollm control + branch / followup / sequence × 40/80/120)
- **n=1 deterministic**

This round does **not** change SequenceController policy behavior. It separates exact-sig bookkeeping from cluster-level metrics.

## Behavior lock (must match v0.3.5)

| strategy | budget | confirmed | BDR | Deep-BDR | TTCB | TTDCB |
|---|---|---|---|---|---|---|
| ghost-nollm | 40–120 | D4, D6, D8 | 0.214 | 0.111 | 6 | 6 |
| ghost-branch | 40–120 | D4, D8 | 0.143 | 0 | 9 | — |
| ghost-followup | 40–120 | D4, D8 | 0.143 | 0 | 9 | — |
| ghost-sequence | 40–120 | **D6, D12** | **0.143** | **0.222** | **14** | **14** |

Action counts: sequence @40/80/120 states 20/41/63 as in v0.3.5. Confirmed set unchanged.

## Canonical metrics (ghost-sequence)

| budget | hub_variant | canonical_hub | inflation | unique disc/start/comp | start events | instances | returned | finding | return_success_rate |
|---|---|---|---|---|---|---|---|---|---|
| 40 | 14 | **3** | 4.667 | 8 / 8 / 2 | 21 | 21 | 2 | 8 | 0.154 |
| 80 | 34 | **3** | 11.333 | 8 / 8 / 2 | 53 | 53 | 2 | 22 | 0.065 |
| 120 | **57** | **3** | **19.0** | 8 / 8 / 2 | **87** | **87** | 2 | 37 | 0.040 |

v0.3.5 `hub_count=57` = `hub_variant_count`. `canonical_hub_count=3`.

v0.3.5 `sequences_started=87` = `sequence_instances_started` (attempts, not unique branches). Unique started stays **8**.

v0.3.5 `sequences_completed=39` ≈ `returned(2) + finding(37)`. Not 39 unique branches.

Control `ghost-nollm`: no sequence events (metrics absent).

## v0.3.5 vs v0.3.5.1

| | v0.3.5 | v0.3.5.1 |
|---|---|---|
| confirmed / BDR / Deep-BDR / TTCB | D6+D12 / 0.143 / 0.222 / 14 | **same** |
| hub_count | 57 | hub_variant_count=57; **canonical_hub_count=3** |
| branches_started | 8 unique | 8 unique; 87 attempts |
| sequences_completed | 39 | 2 returned + 37 finding terminals |

## New observation

Semantic variants inflate exact-sig workflow bookkeeping by **19×** at budget 120 (`57/3`). This is a measurement fact for v0.3.6, not a mandate to cluster-dedupe behavior (archived vs active Delete can both be worth testing).

## Lifecycle Erratum (v0.3.5.1-r2)

`mean_sequence_len` / `max_sequence_len` in this directory were stuck at 1 because instance length was not accumulated. Terminal “completed=2” counted only returns.

Corrected in `experiments/published/deepbench-v0.3.5.1-r2/`: max length **6**; unique terminally tested branches **6** (`returned ∪ finding`). Confirmed D6+D12, BDR, Deep-BDR, TTCB unchanged.

## Next research question

> How should workflow memory persist across structural hubs while remaining sensitive to semantic context?
