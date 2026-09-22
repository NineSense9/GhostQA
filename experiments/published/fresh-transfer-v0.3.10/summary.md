# GhostQA v0.3.10 — Fresh Cross-App Transfer

**Outcome A — fresh transfer with safety** (computed from protocol gates).

Product default unchanged: NoFrontier, `sequence_mode=off`.

## Authoring-bias disclosure

- BuggyDesk was authored after v0.3.9 existed.
- The v0.3.9 candidate was frozen before target evaluation.
- BuggyDesk was frozen before policy evaluation.
- This is a fresh one-target cross-app transfer test, not an independently designed external benchmark and not universal generalization proof.

## BuggyDesk @120

| policy | states | URLs | BDR | Deep-BDR | return attempts | returned | escapes | confirmed |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ghost-structural-memory | 6 | 6 | 0.0 | 0.0 | 116 | 0 | 0 | — |
| ghost-structural-return-guard | 35 | 19 | 0.7 | 1.0 | 34 | 2 | 7 | BUG-K1, BUG-K10, BUG-K2, BUG-K3, BUG-K5, BUG-K6, BUG-K9 |
| ghost-nollm | 33 | 11 | 0.4 | 0.5 | 0 | 0 | 0 | BUG-K3, BUG-K5, BUG-K6, BUG-K9 |
| bfs | 30 | 19 | 0.5 | 0.5 | 0 | 0 | 0 | BUG-K2, BUG-K3, BUG-K4, BUG-K6, BUG-K9 |
| dfs | 29 | 8 | 0.4 | 0.5 | 0 | 0 | 0 | BUG-K3, BUG-K5, BUG-K6, BUG-K9 |

BFS/DFS/ghost-nollm are context. They are not outcome gates.

## Safety suite

| scenario | expected | observed | pass |
|---|---|---|---|
| S1 direct successful return | returned terminal, zero escape | escapes=0 returned=1 | True |
| S2 multi-step successful return | successful return, zero escape | escapes=0 returned=1 | True |
| S3 same cluster, distinct exact variants | zero escape solely because cluster repeats | escapes=0 returned=1 | True |
| S4 exact self-loop | exactly one escape, abandoned, not returned | escapes=1 returned=0 inflation=0 | True |
| S5 short A→B→A cycle | escape on first exact repeated destination; abandoned | escapes=1 returned=0 inflation=0 | True |
| S6 history reset between branches | branch-one cycle history does not poison branch two | escapes=1 returned=1 | True |
| S7 finding then cycle | finding + cycle escape is not counted returned | escapes=1 returned=0 | True |

## Post-hoc bug visibility

| bug id | kind | trigger depth | spec-visible? | manifest-hidden? | policies confirmed |
|---|---|---:|---|---|---|
| BUG-K1 | js_error | 2 | False | True | ghost-structural-return-guard |
| BUG-K2 | blank | 1 | False | True | bfs, ghost-structural-return-guard |
| BUG-K3 | dead_action | 3 | False | True | bfs, dfs, ghost-nollm, ghost-structural-return-guard |
| BUG-K4 | nav_loop | 2 | False | True | bfs |
| BUG-K5 | semantic | 2 | True | True | dfs, ghost-nollm, ghost-structural-return-guard |
| BUG-K6 | semantic | 3 | True | True | bfs, dfs, ghost-nollm, ghost-structural-return-guard |
| BUG-K7 | js_error | 1 | False | True | — |
| BUG-K8 | http_error | 2 | False | True | — |
| BUG-K9 | semantic | 4 | True | True | bfs, dfs, ghost-nollm, ghost-structural-return-guard |
| BUG-K10 | semantic | 5 | True | True | ghost-structural-return-guard |

## Transfer metrics (primary budget 120)

- C1 evaluable return-cycle opportunities: 1
- Guard return_cycle_escape events: 7
- Post-escape novel states: 27
- Post-escape novel URLs: ['/ticket.html?id=1002', '/customer.html?id=c2', '/ticket.html?id=1003', '/activity.html?id=c2', '/compose.html', '/kb.html', '/article.html?id=a1', '/article.html?id=a2', '/article.html?id=a3', '/team.html', '/profile.html', '/integrations.html', '/reports.html']
- Absent from C1 URLs: ['/ticket.html?id=1003', '/activity.html?id=c2', '/compose.html', '/kb.html', '/article.html?id=a1', '/article.html?id=a2', '/article.html?id=a3', '/team.html', '/profile.html', '/integrations.html', '/reports.html', '/ticket.html?id=1002', '/customer.html?id=c2']
- C1 confirmed bugs lost by guard: []
- First escape step: 7

## Reproduce

```text
python -m benchmark.fresh_transfer_reproduce --root experiments/published/fresh-transfer-v0.3.10 --verify
```

Product default changed: no

