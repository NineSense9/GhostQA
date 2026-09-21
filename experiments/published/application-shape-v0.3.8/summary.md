# GhostQA v0.3.8 — Application-Shape Analysis (evidence-hardened)

This round does **not** retune DeepBench, holdout, or BuggyShop scores.
Frozen C1 hashes still match `experiments/frozen/ghost-structural-v0.3.6/freeze.json`.
Diagnostic reruns @120 reproduced v0.3.7 confirmed sets (not independent trials).

Reproduction (clean clone, no `experiments/runs`):

```text
python -m benchmark.application_shape_reproduce --root experiments/published/application-shape-v0.3.8 --verify
```

Canonical analysis SHA256: `95670192a10100639c865089fef6506580eadcc42c2b59695d5e082b7efe7f7e`

## A. Baseline & freeze integrity

- Hardening parent HEAD: `090366c`
- Freeze: `ghost-structural-memory`; product default still NoFrontier / `sequence_mode=off`
- v0.3.7 outcome **C** stands
- Five frozen exploration files: unchanged vs `090366c`

## B. Evidence sources

- **Canonical:** `evidence/shop` + `evidence/flow` (committed; see `evidence-manifest.json`)
- `traces/` is a curated subset of the same bytes
- Source-modeled shop topology validated against `apps/buggy-shop/static/app.js`
- Runtime graphs / traces for observed states and H1/H2
- Ignored `experiments/runs/` is **not** required for reproduction

## C. BuggyShop coverage-collapse (observed)

C0 and C1 (trace-derived):

| | states | URLs | branch_start | return_attempt | returned terminal | lost_parent | finding |
|---|---:|---:|---:|---:|---:|---:|---:|
| ghost-sequence | 6 | 4 | 2 | 116 | **0** | 1 | 1 |
| ghost-structural-memory | 6 | 4 | 2 | 116 | **0** | 1 | 1 |
| BFS | 41 | 11 | — | — | — | — | — |
| deferred | 34 | 11 | — | — | — | — | — |

Old published field `return_success_events=2` was the **branch_start count**, not successful return-to-parent. Correct: `successful_return_to_parent_events=0`.

The observed C0/C1 six-state collapse is directly explained by a persistent return loop after a nested hub replaces the parent hub with detail, while available return behavior oscillates between cart and index and never emits a returned terminal.

Structural memory is **not** the added cause of this collapse: C0 and C1 show the same 6-state / 4-URL / 116-return-attempt pattern.

There is **no evidence** that fingerprint or semantic-variant explosion is the **primary** cause; the persistent return loop is sufficient to explain the observed coverage lock. Variant churn 1.5 is supporting, not an exclusion of all abstraction issues.

## D. H1 (trace-derived)

| policy | first action | H1 JS confirm |
|---|---|---|
| DFS | nav_settings | **8** |
| BFS | nav_login | **28** |
| deferred | nav_login | **93** |
| C0 sequence | nav_login | none (settings 0, changelog 0) |
| C1 | nav_login | none (settings 0, changelog 0) |

Failure class: **reach failure**. Immediate mechanism in this run: step-0 ranking/classification sends C0/C1 away from settings; settings/changelog remain unvisited. DFS produces the JS error as soon as it arrives. This is this route, not “all shallow bugs fail because of distractor keywords”.

## E. H2 (trace-derived)

| policy | billing | qty |
|---|---|---|
| DFS / BFS / C0 | never | — |
| deferred | reached | no qty_down |
| C1 | entries **32, 53, 87, 97** | up,down,up ×3 then a lone down at 98 |

C1 qty actions: `[33 up, 34 down, 35 up, 54 up, 55 down, 56 up, 88 up, 89 down, 90 up, 98 down]`. No `bill_qty_non_negative` finding. Oracle unit test: 1→0 legal; 0→-1 fires. Global miss with **policy-specific** mechanisms; not C1-only; not oracle-blind.

## F. Application-shape descriptors

| descriptor | value | provenance |
|---|---|---|
| mean shortest-path depth | 1.364 | **source-modeled** (declared pages vs app.js literals) |
| shop home is hub | true | source-modeled GUIState + real labels in app.js |
| C1 n_states / n_urls | 6 / 4 | runtime_observed |
| C1 return_attempt | 116 | trace_derived |
| failure class | return-to-parent mismatch | posthoc_interpretation |

## G. Supported vs not

Still supported: C0/C1 six-state collapse; persistent return loop; nested parent-hub replacement; H1 step-0 reach divergence; H2 global policy-specific miss; structural memory not added cause of shop collapse.

Narrowed: fingerprint wording; static depth is source-modeled not runtime-measured.

Not supported: C1 as general tester; nested hubs always collapse; DISTRACTOR_KEYWORDS explain every shallow miss; H2 is depth-only.

## H. Next-algorithm hypotheses (not implemented)

1. Nested-hub guard
2. Return-lock breaker after N failed parent matches (breadth-preservation floor)
3. Application-shape gate
4. Shallow-coverage reservation

## I. Product

Default **unchanged**: NoFrontier, `sequence_mode=off`.

## J. Next

v0.3.9 may implement **one** experimental mode for return-lock / nested hub. Do not retune DeepBench weights off H1/H2. H1/H2 are inspected analysis cases, not untouched holdout.

## K. Git / CI / reproducibility

See `evidence-manifest.json`, `metrics/reproduction.json` (clean-clone record), and the verify command above.

Incident: `experiments/runs/v038-diag-shop/metrics.json` was 0 bytes because `diagnostic_runner` truncated it on `aggregate()` KeyError after traces were already written. Raw evidence unaffected. No shop rerun.
