# DeepBench v0.3.1 — Exploration Repair

- **Date**: 2026-09-19
- **Benchmark freeze**: `5355abd` (BuggyFlow layout unchanged)
- **Algorithm HEAD**: `45e5669`
- **Runs**: 72 unique policy×budget×seed (no dropped seeds)
- **LLM**: MockLLM / NoLLM. Real LLM skipped: credentials unavailable.
- **Holdout**: not scored.

v0.3 numbers are in `experiments/published/deepbench-v0.3/` and were not overwritten.

## What changed in the explorer (not the benchmark)

- Input field = 1 interaction opportunity, not 6 frontier slots
- Progressive payload: first wave 2 classes; rest deferred
- WorkflowBFS: non-AI baseline that prefers submit/next over fuzz
- Frontier v1.1 scores interactions + restore cost
- Relocate uses frontier_net vs local_marginal (not `if local_untried: stay`)

## Results (confirmed BDR)

| strategy | budget | n | BDR | Deep-BDR | AUC | T2Bug | restore_ratio | input_share | max_wf_depth |
|---|---|---|---|---|---|---|---|---|---|
| Monkey | 40 | 10 | 0.121±0.059 | 0 | 0.085 | 6.5 | 0 | 0.23 | 1.3 |
| Monkey | 80 | 3 | 0.262±0.083 | 0 | 0.154 | 8.7 | 0 | 0.16 | 1.7 |
| Monkey | 120 | 3 | 0.333±0.041 | 0 | 0.207 | 8.7 | 0 | 0.14 | 1.7 |
| DFS | 40 | 3 | 0.357 | 0 | 0.214 | 1 | 0 | 0.23 | 1 |
| DFS | 80 | 3 | 0.357 | 0 | 0.286 | 1 | 0 | 0.46 | 2 |
| DFS | 120 | 3 | **0.429** | **0.111** | 0.331 | 1 | 0 | 0.31 | **4** |
| BFS | 40 | 3 | 0.286 | 0 | 0.145 | 8 | 0 | 0.05 | 1 |
| BFS | 80 | 3 | 0.357 | 0 | 0.239 | 8 | 0 | 0.15 | 2 |
| BFS | 120 | 3 | 0.357 | 0 | 0.279 | 8 | 0 | 0.15 | 3 |
| WorkflowBFS | 40 | 3 | 0.214 | **0.111** | 0.102 | 1 | 0 | **0.00** | **4** |
| WorkflowBFS | 80/120 | 3 | 0.214 | 0.111 | 0.16–0.18 | 1 | 0 | 0.00 | 4 |
| Ghost-noFrontier | 40 | 3 | 0.143 | **0.111** | 0.104 | 1 | 0 | 0.18 | **4** |
| Ghost-noFrontier | 80/120 | 3 | 0.214 | 0.111 | 0.15–0.17 | 1 | 0 | 0.06–0.09 | 4 |
| Ghost-full | 40/80/120 | 3 | **0.000** | 0 | 0 | 1 | 0.08–0.23 | 0.09–0.18 | 3 |
| Ghost-noLLM | 40/80/120 | 3 | **0.000** | 0 | 0 | 1 | 0.19–0.33 | 0.10–0.13 | 3–4 |
| Ghost-oldInput | 40 | 2 | 0.143 | 0.111 | 0.113 | 1 | 0 | 0.33 | 4 |

Deep bugs confirmed when Deep-BDR>0: **BUG-D6** (empty project name, depth 6). DFS@120 also D6.

## Answers to the v0.3.1 questions

**Q1 Input budget / local sink.** Yes for WorkflowBFS (`input_share=0`). Ghost-noFrontier also low. Flat BFS still spends input budget without reaching depth 4 at 40.

**Q2 Workflow progression.** WorkflowBFS, Ghost-noFrontier, Ghost-oldInput, DFS@120 reach `max_workflow_depth=4` (project). BFS@120 reaches 3 (wizard). Ghost-full with relocate stays at 3 and confirms nothing.

**Q3 Interaction frontier vs raw-action.** Interaction grouping is used by WorkflowBFS/Ghost. The *relocate* that consumes that score still fails.

**Q4 Opportunity-cost relocate.** **No.** Ghost-full/noLLM restore_ratio 0.08–0.33 and BDR=0. Ghost-noFrontier (same local policy, no relocate) finds D6. Relocate is still restore waste.

**Q5 Ghost depth≥4 bugs.** Ghost-full: **No**. Ghost-noFrontier: **Yes (D6)**. WorkflowBFS: **Yes (D6)**.

## Negative results (kept)

1. Ghost-full with opportunity-cost relocate confirmed **zero** bugs on this frozen matrix.
2. Adding `登录` to risk keywords (45e5669) did not fix relocate; probe *before* that commit had Ghost-full BDR=0.07 / depth 4.
3. WorkflowBFS finds D6 at budget 40 but never the rest of D5–D14 — it reaches project then stops expanding (input_share=0, states frozen at 18).
4. BFS still does not find D6 at 120 (depth 3).
5. Real LLM skipped.

## Ablation (budget 40)

| config | BDR | Deep | restore |
|---|---|---|---|
| Ghost-full (progressive + relocate) | 0.00 | 0 | 0.23 |
| Ghost-noFrontier (progressive, no relocate) | 0.14 | 0.11 | 0 |
| Ghost-oldInput (flat 6-payload + exhaustion relocate) | 0.14 | 0.11 | 0 |
| WorkflowBFS | 0.21 | 0.11 | 0 |

Progressive payloads help **when relocate is off**. Relocate is the remaining failure.

## Known limitations

- Opportunity-cost relocate still over-jumps.
- WorkflowBFS does not resume deferred fuzz after reaching project.
- Jaccard/aHash still not used in graph classification (doc-only).
- Semantic variant is still “all obs minus volatile heuristic”.
