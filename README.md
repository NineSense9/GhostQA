# GhostQA — AI 驱动的自主探索式软件测试系统

> Monkey 有手无脑，脚本测试有人脑无手。GhostQA 是**有脑、有手、有判据、还自证清白**的测试员。

给定一个 Web 应用与需求规格，GhostQA 在无人干预下：自主建立软件状态模型（State Graph）→ 用状态价值函数选择高价值测试路径 → 用三层 Oracle 判断异常（硬异常/结构异常/需求语义异常）→ 对每个候选 Bug 按 **BugFingerprint** 重放验证 → 用 **ddmin** 自动最小化复现路径 → 交付带证据的可信缺陷报告。

## 当前状态：v0.3（Algorithm Proof）

| 能力 | 状态 |
|---|---|
| SimBench 算法实验层（3 个模拟 App） | ✅ Implemented |
| Playwright 真实浏览器执行器 | ✅ Implemented |
| BuggyShop 浅层 benchmark（11 页 / 10 bugs） | ✅ Implemented |
| BuggyFlow / DeepBench 深层 benchmark（16 页 / 14+2 holdout bugs，freeze `5355abd`） | ✅ Implemented |
| 两层状态模型（structural cluster + data-obs semantic variant） | ✅ Implemented |
| State similarity 接入 StateGraph / Explorer / Novelty | ✅ Implemented |
| Frontier planner（reset + replay known path） | ✅ Implemented |
| GhostPolicy v1.2（局部评分 + 全局 frontier；LLM 门控） | ✅ Implemented |
| 三层 Oracle + BugFingerprint + 三态 replay + ddmin | ✅ Implemented |
| CLI + JSON/HTML 报告 | ✅ Implemented |
| WebBench v0.2 + DeepBench v0.3 可追溯实验 | ✅ Implemented |
| 真实 LLM 实验 | ⏭ skipped（无 GHOSTQA_MODEL_* 凭据） |
| Dashboard | ⏳ Planned (v0.4) |
| Android 扩展 | ⏳ Planned (v0.4+) |

## 快速开始

```bash
git clone https://github.com/NineSense9/GhostQA.git
cd GhostQA
python -m venv .venv && .venv/Scripts/activate        # Windows
pip install -e ".[dev]"
playwright install chromium

pytest -m "not integration"      # unit tests（Sim / 状态模型 / planner，无需浏览器）
pytest -m integration            # Chromium + BuggyShop + BuggyFlow
```

## 一条命令跑完整测试

```bash
# 1. 启动被测应用（BuggyShop，完全离线）
python apps/buggy-shop/server.py 3939

# 2. 让 GhostQA 自主探索、找 Bug、验证并生成报告
python -m ghostqa run \
  --url http://127.0.0.1:3939 \
  --policy ghost \
  --budget 60 \
  --spec apps/buggy-shop/spec.json \
  --out runs/demo

# 3. 查看报告 runs/demo/report.html
```

使用真实 LLM（可选，模型不可用时自动降级为 no-LLM 策略）：

```bash
export GHOSTQA_MODEL_BASE_URL=https://api.deepseek.com/v1
export GHOSTQA_MODEL_API_KEY=sk-...
export GHOSTQA_MODEL_NAME=deepseek-chat
python -m ghostqa run --url ... --policy ghost --llm ...
```

## 实验证据

所有 README 数字可追溯至 `experiments/published/` 下的 run。

- **SimBench v0.1**（本地）：`experiments/runs/2026-09-18-v0.1-first/metrics.json`
- **WebBench v0.2**（BuggyShop，浅层）：`experiments/published/webbench-v0.2/`
  - BFS = Ghost-full = 0.30；Ghost T2Bug=1 最快；Ghost-noLLM=0.10。浅层空间里 BFS 与 Ghost 打平。
- **DeepBench v0.3**（BuggyFlow，深层，freeze `5355abd`）：`experiments/published/deepbench-v0.3/`
  - 61 unique runs。**Deep-BDR = 0**（所有策略，budget ≤ 120 都没有确认 trigger_depth≥4 的 bug）。
  - 浅层天花板 5/14=0.357（D1–D4, D8）。DFS@40 与 BFS@80 达到该天花板。
  - **Ghost-full / Ghost-noLLM = 0.071**（只确认 D4），**输给 BFS/DFS**。
  - 消融：Ghost-noFrontier@40 = 0.214，@120 = 0.357 —— **当前 Frontier relocate 是负贡献**。
  - Monkey@40 × 10 seeds：0.121±0.059。
  - 真实 LLM：skipped（无凭据）。MockLLM 数据不是真实大模型表现。
  - 详细表与负结果分析见 `experiments/published/deepbench-v0.3/summary.md`。

## 架构

```
ghostqa/
├── state/        # 两层状态 / 签名 / 相似度 / StateGraph
├── executor/     # Executor / Sim / Playwright / nav history
├── exploration/  # Explorer / 策略 / FrontierPlanner / GhostPolicy v1.2
├── oracle/       # 三层 Oracle / BugFingerprint / 规格断言 DSL
├── replay/       # 三态重放验证器
├── minimizer/    # ddmin 可执行最小复现
├── agent/        # ModelGateway：Mock / Null / OpenAI 兼容
└── report/       # JSON + HTML 报告
apps/buggy-shop/  # 浅层 benchmark
apps/buggy-flow/  # DeepBench（冻结）
benchmark/        # SimBench + WebBench（--app buggy-shop|buggy-flow）
experiments/      # published/ 可引用证据；runs/ 本地大文件(gitignore)
docs/             # PROJECT_PLAN / TECH_SURVEY / TRUTH_AUDIT / FAILURE_CORPUS / HANDOFF
```

## 工程原则

Working > Fancy ｜ Measured > Claimed ｜ Verified > Generated ｜ Small Complete System > Huge Half-finished System

- GhostQA 探索期间**绝不读取** bugs.manifest.json 与被测应用内部状态（Tester 与 Benchmark Judge 严格隔离）。
- 实验比较至少多种子，输出 mean/std/min/max；不允许挑 seed。
- 每个 AI 模块必须能回答：它让 Bug Discovery / Coverage / Oracle Accuracy / Reproduction Success 中哪个指标变好了？

## 文档

- `docs/PROJECT_PLAN.md` — 总体设计（产品定义/算法/架构/路线图）
- `docs/TECH_SURVEY.md` — 学术与工业竞品调研（2026 诚实版）
- `docs/TRUTH_AUDIT.md` — v0.1 文档-代码一致性审计
