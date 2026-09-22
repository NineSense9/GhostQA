# GhostQA v0.3.11 — Preregistered Multi-Target Replication

**Outcome D — inconclusive suite** (computed from protocol gates).

Product default unchanged: NoFrontier, `sequence_mode=off`.
Promotion-readiness: `not_ready`.

## Authoring-bias disclosure

- These targets are preregistered fresh targets, not independently designed external benchmarks.
- The v0.3.9 candidate was frozen before this round.
- Target identities, seeds, topology families, budgets, and bug-count ranges were preregistered before policy evaluation.
- The generator does not accept or reject topology based on policy score.
- This is not universal generalization proof.

## buggy-crm @120

| policy | states | URLs | BDR | Deep-BDR | return attempts | returned | escapes | confirmed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ghost-structural-memory | 5 | 5 | 0.0 | 0.0 | 0 | 0 | 0 | — |
| ghost-structural-return-guard | 5 | 5 | 0.0 | 0.0 | 0 | 0 | 0 | — |
| ghost-nollm | 28 | 19 | 0.7 | 0.0 | 0 | 0 | 0 | BUG-C1, BUG-C2, BUG-C3, BUG-C4, BUG-C5, BUG-C6, BUG-C8 |
| bfs | 29 | 20 | 0.4 | 0.0 | 0 | 0 | 0 | BUG-C2, BUG-C3, BUG-C4, BUG-C6 |
| dfs | 36 | 13 | 0.4 | 0.5 | 0 | 0 | 0 | BUG-C3, BUG-C5, BUG-C6, BUG-C9 |

- evaluable opportunity: 0
- C1 opportunities @120: 0
- guard escapes: 0
- L1/L2: 0/0 unclassified=0
- post-escape novel states/URLs: 0/0
- absent from C1 URLs: []
- C1 bugs lost: []
- meaningful return keys lost: []
- escape/opportunity match: True

Primary C1/guard at 40/80:

| budget | C1 states | C1 BDR | C1 returned | guard states | guard BDR | guard returned | guard escapes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 40 | 5 | 0.0 | 0 | 5 | 0.0 | 0 | 0 |
| 80 | 5 | 0.0 | 0 | 5 | 0.0 | 0 | 0 |

## buggy-wiki @120

| policy | states | URLs | BDR | Deep-BDR | return attempts | returned | escapes | confirmed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ghost-structural-memory | 6 | 6 | 0.0 | 0.0 | 116 | 0 | 0 | — |
| ghost-structural-return-guard | 23 | 16 | 0.111 | 0.0 | 49 | 19 | 2 | BUG-W2 |
| ghost-nollm | 52 | 23 | 0.333 | 0.5 | 0 | 0 | 0 | BUG-W3, BUG-W5, BUG-W9 |
| bfs | 42 | 11 | 0.0 | 0.0 | 0 | 0 | 0 | — |
| dfs | 62 | 6 | 0.333 | 0.5 | 0 | 0 | 0 | BUG-W3, BUG-W5, BUG-W9 |

- evaluable opportunity: 1
- C1 opportunities @120: 1
- guard escapes: 2
- L1/L2: 2/0 unclassified=0
- post-escape novel states/URLs: 15/10
- absent from C1 URLs: ['/revision.html?id=r1', '/page.html?id=p2', '/history.html?id=p2', '/revision.html?id=r3', '/page.html?id=p3', '/history.html?id=p3', '/editor.html?id=p3', '/editor.html', '/tags.html', '/search.html']
- C1 bugs lost: []
- meaningful return keys lost: []
- escape/opportunity match: True

Primary C1/guard at 40/80:

| budget | C1 states | C1 BDR | C1 returned | guard states | guard BDR | guard returned | guard escapes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 40 | 6 | 0.0 | 0 | 16 | 0.0 | 4 | 2 |
| 80 | 6 | 0.0 | 0 | 19 | 0.0 | 12 | 2 |

## buggy-ops @120

| policy | states | URLs | BDR | Deep-BDR | return attempts | returned | escapes | confirmed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ghost-structural-memory | 5 | 5 | 0.0 | 0.0 | 0 | 0 | 0 | — |
| ghost-structural-return-guard | 5 | 5 | 0.0 | 0.0 | 0 | 0 | 0 | — |
| ghost-nollm | 38 | 26 | 0.222 | 0.0 | 0 | 0 | 0 | BUG-O2, BUG-O5 |
| bfs | 34 | 25 | 0.333 | 0.0 | 0 | 0 | 0 | BUG-O2, BUG-O4, BUG-O6 |
| dfs | 42 | 24 | 0.556 | 1.0 | 0 | 0 | 0 | BUG-O3, BUG-O4, BUG-O6, BUG-O7, BUG-O9 |

- evaluable opportunity: 0
- C1 opportunities @120: 0
- guard escapes: 0
- L1/L2: 0/0 unclassified=0
- post-escape novel states/URLs: 0/0
- absent from C1 URLs: []
- C1 bugs lost: []
- meaningful return keys lost: []
- escape/opportunity match: True

Primary C1/guard at 40/80:

| budget | C1 states | C1 BDR | C1 returned | guard states | guard BDR | guard returned | guard escapes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 40 | 5 | 0.0 | 0 | 5 | 0.0 | 0 | 0 |
| 80 | 5 | 0.0 | 0 | 5 | 0.0 | 0 | 0 |

## Aggregate replication

| target | opportunity | escape | novel after escape | C1 bugs lost | return regression | transfer demonstrated |
|---|---:|---:|---|---|---|---|
| buggy-crm | 0 | 0 | False | [] | [] | False |
| buggy-wiki | 1 | 2 | True | [] | [] | True |
| buggy-ops | 0 | 0 | False | [] | [] | False |

## Safety

| check | cases/traces | failures | pass |
|---|---:|---:|---|
| S1–S7 | 7 | 0 | True |
| exhaustive traces | 5800 | 0 | True |

## Lifecycle

| target | escapes | L1 open-instance | L2 already-terminal | unclassified |
|---|---:|---:|---:|---:|
| buggy-crm | 0 | 0 | 0 | 0 |
| buggy-wiki | 2 | 2 | 0 | 0 |
| buggy-ops | 0 | 0 | 0 | 0 |

## Post-hoc bug visibility

### buggy-crm

| bug id | kind | trigger depth | spec-visible? | manifest-hidden? | policies confirmed |
|---|---|---:|---|---|---|
| BUG-C1 | js_error | 2 | False | True | ghost-nollm |
| BUG-C2 | blank | 1 | False | True | bfs, ghost-nollm |
| BUG-C3 | dead_action | 3 | False | True | bfs, dfs, ghost-nollm |
| BUG-C4 | nav_loop | 2 | False | True | bfs, ghost-nollm |
| BUG-C5 | semantic | 2 | True | True | dfs, ghost-nollm |
| BUG-C6 | semantic | 3 | True | True | bfs, dfs, ghost-nollm |
| BUG-C7 | js_error | 1 | False | True | — |
| BUG-C8 | http_error | 2 | False | True | ghost-nollm |
| BUG-C9 | semantic | 4 | True | True | dfs |
| BUG-C10 | semantic | 5 | True | True | — |

### buggy-wiki

| bug id | kind | trigger depth | spec-visible? | manifest-hidden? | policies confirmed |
|---|---|---:|---|---|---|
| BUG-W1 | js_error | 2 | False | True | — |
| BUG-W2 | blank | 1 | False | True | ghost-structural-return-guard |
| BUG-W3 | dead_action | 3 | False | True | dfs, ghost-nollm |
| BUG-W4 | nav_loop | 2 | False | True | — |
| BUG-W5 | semantic | 2 | True | True | dfs, ghost-nollm |
| BUG-W6 | semantic | 4 | True | True | — |
| BUG-W7 | js_error | 1 | False | True | — |
| BUG-W8 | http_error | 2 | False | True | — |
| BUG-W9 | semantic | 4 | True | True | dfs, ghost-nollm |

### buggy-ops

| bug id | kind | trigger depth | spec-visible? | manifest-hidden? | policies confirmed |
|---|---|---:|---|---|---|
| BUG-O1 | js_error | 2 | False | True | — |
| BUG-O2 | blank | 1 | False | True | bfs, ghost-nollm |
| BUG-O3 | dead_action | 4 | False | True | dfs |
| BUG-O4 | nav_loop | 2 | False | True | bfs, dfs |
| BUG-O5 | semantic | 2 | True | True | ghost-nollm |
| BUG-O6 | semantic | 3 | True | True | bfs, dfs |
| BUG-O7 | js_error | 1 | False | True | dfs |
| BUG-O8 | http_error | 2 | False | True | — |
| BUG-O9 | semantic | 4 | True | True | dfs |

## Reproduce

```text
python -m benchmark.multi_target_reproduce --root experiments/published/multi-target-replication-v0.3.11 --verify
```

Computed outcome: **D — inconclusive suite**

Product default changed: no

Fewer than two targets presented evaluable return-cycle opportunities under the preregistered budgets. Budgets are not raised.

