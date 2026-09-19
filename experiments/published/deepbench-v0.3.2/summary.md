# DeepBench v0.3.2 — Episode-Aware Replay Correctness

- **Date**: 2026-09-19
- **Benchmark freeze SHA**: `5355abd444eb4a4e99242c7629a1363c38e52a2a` (BuggyFlow unchanged)
- **Algorithm SHA**: `b00de1f` (GhostPolicy / FrontierPlanner weights unchanged from v0.3.1)
- **Metrics SHA**: `ebd14fb` (replay/episode fields)
- **Runs**: 70 unique policy×budget×seed (no dropped seeds)
- **Policies**: monkey, dfs, bfs, workflow-bfs, ghost-nollm, ghost-full, ghost-nofrontier
- **Budgets**: 40, 80, 120
- **Seeds**: deterministic {1,2,3}; Monkey@40 also {4..10}
- **LLM**: MockLLM / NoLLM. Real LLM skipped.
- **This is corrected measurement**, not a policy retune.

v0.3.1 files in `experiments/published/deepbench-v0.3.1/` were not overwritten.
See that directory's summary **Erratum**.

## Replay correctness change

Explorer relocation / crash recovery called `executor.reset()` but `RunResult.steps`
recorded only Actions. `result.actions()` flattened episodes. Replay sliced
`actions[:finding.step_index+1]` after one reset, so:

```
executed:  A B C  | RESET | D E BUG
replayed:  RESET A B C D E BUG
```

v0.3.2 replays `reproduction_actions(finding)` from the finding's episode only.

## Frozen matrix

| strategy | budget | n | BDR | Deep-BDR | AUC | TTF | TTCB | TTDCB | pass/fail/invalid | replay | restore | episodes | confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| monkey | 40 | 10 | 0.121±0.059 | 0 | 0.085 | 6.5 | 9 | — | 17/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 |
| monkey | 80 | 3 | 0.262±0.083 | 0 | 0.154 | 8.7 | 13.7 | — | 11/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 |
| monkey | 120 | 3 | 0.333±0.041 | 0 | 0.207 | 8.7 | 13.7 | — | 15/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 |
| dfs | 40 | 3 | 0.357±0.000 | 0 | 0.214 | 1 | 5 | — | 15/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 |
| dfs | 80 | 3 | 0.357±0.000 | 0 | 0.286 | 1 | 5 | — | 15/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 |
| dfs | 120 | 3 | 0.429±0.000 | 0.111 | 0.331 | 1 | 5 | 84 | 18/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6, BUG-D8 |
| bfs | 40 | 3 | 0.286±0.000 | 0 | 0.145 | 8 | 8 | — | 12/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D8 |
| bfs | 80 | 3 | 0.357±0.000 | 0 | 0.239 | 8 | 8 | — | 15/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 |
| bfs | 120 | 3 | 0.357±0.000 | 0 | 0.279 | 8 | 8 | — | 15/0/0 | 1 | 0 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 |
| workflow-bfs | 40 | 3 | 0.214±0.000 | 0.111 | 0.102 | 1 | 6 | 6 | 9/0/0 | 1 | 0 | 1 | BUG-D4, BUG-D6, BUG-D8 |
| workflow-bfs | 80 | 3 | 0.214±0.000 | 0.111 | 0.158 | 1 | 6 | 6 | 9/0/0 | 1 | 0 | 1 | BUG-D4, BUG-D6, BUG-D8 |
| workflow-bfs | 120 | 3 | 0.214±0.000 | 0.111 | 0.177 | 1 | 6 | 6 | 9/0/0 | 1 | 0 | 1 | BUG-D4, BUG-D6, BUG-D8 |
| ghost-nofrontier | 40 | 3 | 0.143±0.000 | 0.111 | 0.104 | 1 | 6 | 6 | 6/0/0 | 1 | 0 | 1 | BUG-D4, BUG-D6 |
| ghost-nofrontier | 80 | 3 | 0.214±0.000 | 0.111 | 0.145 | 1 | 6 | 6 | 9/0/0 | 1 | 0 | 1 | BUG-D4, BUG-D6, BUG-D8 |
| ghost-nofrontier | 120 | 3 | 0.214±0.000 | 0.111 | 0.168 | 1 | 6 | 6 | 9/0/0 | 1 | 0 | 1 | BUG-D4, BUG-D6, BUG-D8 |
| ghost-nollm | 40 | 3 | 0.143±0.000 | 0 | 0.07 | 1 | 14 | — | 6/0/0 | 1 | 0.325 | 8 | BUG-D2, BUG-D4 |
| ghost-nollm | 80 | 3 | 0.286±0.000 | 0 | 0.162 | 1 | 14 | — | 12/0/0 | 1 | 0.275 | 13 | BUG-D1, BUG-D2, BUG-D3, BUG-D4 |
| ghost-nollm | 120 | 3 | 0.357±0.000 | 0.111 | 0.207 | 1 | 14 | 113 | 15/0/0 | 1 | 0.192 | 14 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6 |
| ghost-full | 40 | 3 | 0.071±0.000 | 0 | 0.036 | 1 | 20 | — | 3/0/0 | 1 | 0.225 | 7 | BUG-D4 |
| ghost-full | 80 | 3 | 0.143±0.000 | 0 | 0.072 | 1 | 20 | — | 6/0/0 | 1 | 0.113 | 8 | BUG-D4, BUG-D8 |
| ghost-full | 120 | 3 | 0.143±0.000 | 0 | 0.096 | 1 | 20 | — | 6/0/0 | 1 | 0.075 | 8 | BUG-D4, BUG-D8 |

TTF = Time to First Finding. TTCB = Time to First Confirmed Bug.
TTDCB = Time to First Deep Confirmed Bug.
`pass/fail/invalid` counts matched-candidate replays.
Old `time_to_first_bug` is a deprecated alias of TTF.

## v0.3.1 vs v0.3.2

Algorithm is the same. This table compares candidate / confirmed / replay success.

| strategy | budget | v0.3.1 cand | v0.3.1 conf | v0.3.1 replay | v0.3.2 cand | v0.3.2 conf | v0.3.2 replay |
|---|---|---|---|---|---|---|---|
| bfs | 40 | BUG-D1, BUG-D2, BUG-D3, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D8 | 1 |
| bfs | 80 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 |
| bfs | 120 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 |
| dfs | 40 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 |
| dfs | 80 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 |
| dfs | 120 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6, BUG-D8 | 1 |
| ghost-full | 40 | BUG-D4 | — | 0 | BUG-D4 | BUG-D4 | 1 |
| ghost-full | 80 | BUG-D4, BUG-D8 | — | 0 | BUG-D4, BUG-D8 | BUG-D4, BUG-D8 | 1 |
| ghost-full | 120 | BUG-D4, BUG-D8 | — | 0 | BUG-D4, BUG-D8 | BUG-D4, BUG-D8 | 1 |
| ghost-nofrontier | 40 | BUG-D4, BUG-D6 | BUG-D4, BUG-D6 | 1 | BUG-D4, BUG-D6 | BUG-D4, BUG-D6 | 1 |
| ghost-nofrontier | 80 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 |
| ghost-nofrontier | 120 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 |
| ghost-nollm | 40 | BUG-D2, BUG-D4 | — | 0 | BUG-D2, BUG-D4 | BUG-D2, BUG-D4 | 1 |
| ghost-nollm | 80 | BUG-D1, BUG-D2, BUG-D3, BUG-D4 | — | 0 | BUG-D1, BUG-D2, BUG-D3, BUG-D4 | BUG-D1, BUG-D2, BUG-D3, BUG-D4 | 1 |
| ghost-nollm | 120 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6 | — | 0 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D6 | 1 |
| ghost-oldinput | 40 | BUG-D4, BUG-D6 | BUG-D4, BUG-D6 | 1 | — | — | — |
| monkey | 40 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 |
| monkey | 80 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 |
| monkey | 120 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | BUG-D1, BUG-D2, BUG-D3, BUG-D4, BUG-D8 | 1 |
| workflow-bfs | 40 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 |
| workflow-bfs | 80 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 |
| workflow-bfs | 120 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 | BUG-D4, BUG-D6, BUG-D8 | BUG-D4, BUG-D6, BUG-D8 | 1 |

### Ghost-full seed=1 probe

| budget | v0.3.1 candidate | v0.3.1 confirmed | v0.3.1 replay | v0.3.2 candidate | v0.3.2 confirmed | v0.3.2 replay |
|---|---|---|---|---|---|---|
| 40 | D4 | — | 0 | D4 | D4 | 1.0 |
| 80 | D4, D8 | — | 0 | D4, D8 | D4, D8 | 1.0 |

Ghost-full BDR rising vs v0.3.1 is **not** “frontier magically fixed”.
Statement: **v0.3.1 confirmed-BDR for relocating policies was confounded by reset-blind replay traces.**

## v0.3.1 erratum (reachability still valid)

Live-exploration fields from v0.3.1 remain usable:

- WorkflowBFS reaches project (`max_workflow_depth=4`)
- Ghost-noFrontier reaches project
- Ghost-full reaches depth 3
- `input_share` / `restore_ratio` are exploration facts

`Ghost-full BDR=0` in v0.3.1 is superseded.

## Negative results (still true)

1. Ghost-full does not beat DFS/BFS on BDR.
2. Relocate volume remains high (see `episode_count` / `relocate_episode_count`).
3. WorkflowBFS still plateaus after D4/D6/D8.
4. Real LLM skipped.
