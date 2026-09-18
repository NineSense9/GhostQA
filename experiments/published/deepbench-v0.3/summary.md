# DeepBench v0.3 — BuggyFlow (frozen)

- **Date**: 2026-09-19
- **App**: BuggyFlow (`apps/buggy-flow/`), freeze commit `5355abd444eb4a4e99242c7629a1363c38e52a2a`
- **Environment**: local Chromium (Playwright) + offline stdlib server
- **Judge**: `bugs.manifest.json` (14 development bugs). Holdout manifest was **not** used for scoring or tuning.
- **Validation**: BugFingerprint replay, `--skip-minimize` (ddmin covered by integration tests)
- **LLM**: MockLLM for `ghost-full` / `llm-naive` / ablations. **Real LLM skipped: credentials unavailable.**
- **Data**: `metrics.json` (61 unique policy×budget×seed runs). No seed was dropped.

BuggyShop / WebBench v0.2 is unchanged and remains the shallow benchmark.

## What this experiment can answer

DeepBench was built so BFS cannot exhaust the interesting state space at budget 40–80: multi-step login→wizard→project chains, distractor branches, 14 bugs with trigger depths 2–12.

It is **not** an experiment designed so GhostQA must win.

## Confirmed Bug Discovery Rate by budget

Mean over seeds. Deep-BDR = fraction of bugs with `trigger_depth >= 4`.

| strategy | budget | n | BDR mean±std | Deep-BDR | AUC | T2Bug | confirmed ids (union) |
|---|---|---|---|---|---|---|---|
| Monkey | 20 | 3 | 0.095±0.083 | 0 | 0.059 | 8.7 | D1, D4 |
| Monkey | 40 | **10** | **0.121±0.059** | 0 | 0.085 | 6.5 | D1–D4, D8 |
| Monkey | 80 | 3 | 0.262±0.083 | 0 | 0.154 | 8.7 | D1–D4, D8 |
| DFS | 20 | 3 | 0.214±0.000 | 0 | 0.096 | 1 | D1–D3 |
| DFS | 40 | 3 | 0.357±0.000 | 0 | 0.214 | 1 | D1–D4, D8 |
| DFS | 80 | 3 | 0.357±0.000 | 0 | 0.286 | 1 | D1–D4, D8 |
| BFS | 20 | 3 | 0.143±0.000 | 0 | 0.061 | 8 | D2, D8 |
| BFS | 40 | 3 | 0.286±0.000 | 0 | 0.145 | 8 | D1–D3, D8 |
| BFS | 80 | 3 | 0.357±0.000 | 0 | 0.239 | 8 | D1–D4, D8 |
| BFS | 120 | 1 | 0.357 | 0 | 0.279 | 8 | D1–D4, D8 |
| LLM-naive | 40 | 2 | 0.000±0.000 | 0 | 0.000 | 3 | — |
| Ghost-noLLM | 20/40/80 | 3×3 | **0.071±0.000** | 0 | ~0.07 | 1 | D4 |
| Ghost-full (MockLLM) | 20/40/80 | 3×3 | **0.071±0.000** | 0 | ~0.07 | 1 | D4 |
| Ghost-full | 120 | 1 | 0.071 | 0 | 0.071 | 1 | D4 |
| Ghost-noFrontier | 40 | 2 | **0.214±0.000** | 0 | 0.093 | 1 | D1, D4, D8 |
| Ghost-noFrontier | 120 | 1 | **0.357** | 0 | 0.257 | 1 | D1–D4, D8 |
| Ghost-noSemantic | 40 | 2 | 0.071±0.000 | 0 | 0.070 | 1 | D4 |

## Honest conclusions

1. **DeepBench is actually deep.** No strategy confirmed a `trigger_depth >= 4` bug at budget ≤ 120. Deep-BDR = 0 across the board. The 9 bugs behind login→wizard (D5–D14) were not reached.
2. **Shallow ceiling is 5/14 = 0.357** (D1 about JS, D2 reports blank, D3 settings dead, D4 empty register, D8 help↔docs loop). DFS hits this ceiling at budget 40; BFS at 80; Ghost-noFrontier at 120.
3. **Ghost-full lost to BFS and DFS** on BDR and AUC. Ghost-full/noLLM only ever confirmed D4. Time-to-first-finding is 1 (register path) but that did not translate into more bugs.
4. **Frontier planner, as implemented, hurt.** Ghost-noFrontier (0.21 @40, 0.36 @120) ≫ Ghost-full (0.07). Reset+replay consumed budget without unlocking the wizard chain.
5. **Semantic variants were not exercised.** Project-page cart-like variants only exist after creating a project. Nobody got there, so cluster/variant coverage could not help.
6. **MockLLM ≈ noLLM** on this app (both stuck on D4). LLM-naive found nothing (2 states).
7. **Real LLM experiment skipped: credentials unavailable.** These numbers are not “AI 大模型真实表现”.

## Why Ghost-full stalled (hypothesis, not a patch)

Default `available_actions` expands every text field into 6 input payloads. Combined with risk keywords that prefer 注册, GhostQA spent the budget enumerating form strings and, when local inputs were exhausted, relocating (reset+replay) instead of clicking 演示登录 and walking the wizard. Systematic DFS/BFS eventually finish the shallow graph (help/about/settings/register) and stop at the same 5-bug ceiling.

This is an algorithm limitation, not a reason to move DeepBench bugs.

## What we will not do with this result

- Will not move D5–D14 closer to the home page
- Will not drop failing seeds
- Will not retune GhostPolicy weights against this table in the freeze window

v0.4 should treat input-vocab cardinality and relocate-vs-local-form-filling as first-class hypotheses, then re-run the **frozen** DeepBench.

## Traceability

- Freeze SHA: `5355abd`
- Core matrix: `experiments/published/deepbench-v0.3/` (original 45 runs, then merged)
- Extra shards (also published): `deepbench-v0.3-monkey10/`, `deepbench-v0.3-ablation/`, `deepbench-v0.3-b120/`
