# DeepBench v0.3.2 — Episode-Aware Replay Correctness

- **Date**: 2026-09-19
- **Benchmark freeze**: `5355abd` (BuggyFlow unchanged)
- **Replay-fix HEAD**: `b00de1f`
- **Runs**: 70 unique policy×budget×seed (no dropped seeds)
- **LLM**: MockLLM / NoLLM. Real LLM skipped.
- **This is corrected measurement**, not a policy retune.

v0.3.1 files in `experiments/published/deepbench-v0.3.1/` were not overwritten.

## What was wrong in v0.3.1

Ghost-full produced candidates (D4/D8) but `replay_success_rate=0` because
`result.actions()` flattened multiple reset episodes into one sequence.
Replay then executed pre-reset actions after a fresh reset.

```
executed:  A B C  | RESET | D E BUG
replayed:  RESET A B C D E BUG     ← not the original episode
```

DFS / BFS / WorkflowBFS rarely reset, so their v0.3.1 BDR was already valid.

## Probe (Ghost-full seed=1)

| budget | v0.3.1 confirmed | v0.3.2 confirmed | replay |
|---|---|---|---|
| 40 | [] | [D4] | 1.0 |
| 80 | [] | [D4, D8] | 1.0 |

`time_to_first_finding=1` vs `time_to_first_confirmed_bug=20`.
The old T2Bug field was first *finding*, not first confirmed bug.

## Corrected matrix

| strategy | budget | n | BDR | Deep-BDR | replay | T2Find | T2Conf | confirmed ids |
|---|---|---|---|---|---|---|---|---|
| Monkey | 40 | 10 | 0.121±0.059 | 0 | 1.0 | — | — | D1–D4, D8 |
| Monkey | 80 | 3 | 0.262 | 0 | 1.0 | 8.7 | 13.7 | D1–D4, D8 |
| Monkey | 120 | 3 | 0.333 | 0 | 1.0 | 8.7 | 13.7 | D1–D4, D8 |
| DFS | 40/80 | 3 | 0.357 | 0 | 1.0 | 1 | 5 | D1–D4, D8 |
| DFS | 120 | 3 | **0.429** | **0.111** | 1.0 | 1 | 5 | D1–D4, D6, D8 |
| BFS | 40 | 3 | 0.286 | 0 | 1.0 | 8 | 8 | D1–D3, D8 |
| BFS | 80/120 | 3 | 0.357 | 0 | 1.0 | 8 | 8 | D1–D4, D8 |
| WorkflowBFS | 40–120 | 3 | 0.214 | **0.111** | 1.0 | 1 | 6 | D4, D6, D8 |
| Ghost-noFrontier | 40 | 3 | 0.143 | **0.111** | 1.0 | 1 | 6 | D4, D6 |
| Ghost-noFrontier | 80/120 | 3 | 0.214 | 0.111 | 1.0 | 1 | 6 | D4, D6, D8 |
| Ghost-noLLM | 40 | 3 | 0.143 | 0 | 1.0 | 1 | 14 | D2, D4 |
| Ghost-noLLM | 80 | 3 | 0.286 | 0 | 1.0 | 1 | 14 | D1–D4 |
| Ghost-noLLM | 120 | 3 | 0.357 | **0.111** | 1.0 | 1 | 14 | D1–D4, D6 |
| Ghost-full | 40 | 3 | 0.071 | 0 | **1.0** | 1 | 20 | D4 |
| Ghost-full | 80/120 | 3 | 0.143 | 0 | **1.0** | 1 | 20 | D4, D8 |

All strategies: `replay_success_rate = 1.0` on candidates that entered validation.

## How to read this vs v0.3.1

- Ghost-full BDR 0.00 → 0.07/0.14 is **not** “frontier magically fixed”.
- Statement: **v0.3.1 confirmed-BDR for relocating policies was confounded by reset-blind replay traces.**
- Relocate is still expensive (`reloc=6–13` on Ghost-full/noLLM). Ghost-noFrontier still finds D6 earlier.
- DFS@120 still has the highest BDR (0.429).

## Metrics note

- `time_to_first_finding` = first candidate finding step
- `time_to_first_confirmed_bug` = min step among replay-confirmed bugs
- `time_to_first_bug` kept as a deprecated alias of `time_to_first_finding` (do not read it as confirmed latency)

## Negative results (still true)

1. Ghost-full does not beat DFS/BFS on BDR.
2. Ghost-full still does not confirm D6 (Deep-BDR=0).
3. Relocate volume remains high.
4. WorkflowBFS still plateaus after D4/D6/D8.
