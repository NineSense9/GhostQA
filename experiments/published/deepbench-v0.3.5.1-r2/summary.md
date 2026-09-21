# DeepBench v0.3.5.1-r2 — Sequence Lifecycle Correction

- **Date**: 2026-09-21
- **Benchmark freeze SHA**: `5355abd444eb4a4e99242c7629a1363c38e52a2a`
- **Measurement SHA**: `9d46512`
- **Product**: v0.4 preview
- **Runs**: 3 (`ghost-sequence` × 40/80/120)
- **n=1 deterministic**

This round does **not** change SequenceController policy behavior. It counts concrete `sequence_action` events and makes terminal outcomes mutually exclusive. Horizon is a lifecycle event (`sequence_horizon_reached`), not a terminal.

Do not overwrite `experiments/published/deepbench-v0.3.5.1/metrics.json`.

## Behavior lock (must match v0.3.5 / v0.3.5.1)

| strategy | budget | confirmed | BDR | Deep-BDR | TTCB | TTDCB | states |
|---|---|---|---|---|---|---|---|
| ghost-sequence | 40 | **D6, D12** | **0.143** | **0.222** | **14** | **14** | 20 |
| ghost-sequence | 80 | D6, D12 | 0.143 | 0.222 | 14 | 14 | 41 |
| ghost-sequence | 120 | D6, D12 | 0.143 | 0.222 | 14 | 14 | 63 |

## Lifecycle metrics (ghost-sequence)

| budget | mean/max len | unique start / returned / finding / terminally_tested | instances | returned | ended_on_finding | lost_parent | budget_end | horizon_reached | unique candidate fps |
|---|---|---|---|---|---|---|---|---|---|
| 40 | **1.524 / 6** | 8 / 2 / 4 / **6** | 21 | 2 | 8 | 11 | 0 | 2 | 4 |
| 80 | 1.283 / 6 | 8 / 2 / 4 / 6 | 53 | 2 | 22 | 28 | 1 | 2 | 4 |
| 120 | 1.207 / 6 | 8 / 2 / 4 / 6 | 87 | 2 | 37 | 47 | 1 | 2 | 4 |

v0.3.5.1 `mean_sequence_len=1` / `max=1` was a bookkeeping bug (`_open_instance["len"]` never accumulated). Real max length is **6**. Mean stays near 1 because most instances are 1-action `lost_parent` overwrites (47 @120), not because every sequence is one click.

v0.3.5 `branches_completed=6` matches **unique_branches_terminally_tested=6** (`returned ∪ finding`). Unique returned stays 2.

`sequence_instances_ended_on_finding=37` is an instance-outcome count, **not** 37 bugs. Unique candidate fingerprints during sequence = **4**.

## v0.3.5.1 vs r2 (@120)

| | v0.3.5.1 | r2 |
|---|---|---|
| confirmed / BDR / Deep-BDR / TTCB | D6+D12 / 0.143 / 0.222 / 14 | **same** |
| mean / max sequence len | 1 / 1 | **1.207 / 6** |
| unique completed | 2 (returned only) | returned=2, with_finding=4, terminally_tested=**6** |
| horizon | not a terminal (count 0) | lifecycle `sequence_horizon_reached=2` |
| 37 finding terminals | easy to misread as 37 bugs | 37 instance outcomes; **4** unique fingerprints |

## Next

Phase 0 measurement gate is closed. v0.3.6 asks how structural workflow memory should persist across semantic variants without collapsing context.
