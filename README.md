# GhostQA — AI 驱动的自主探索式软件测试系统

> Monkey 有手无脑，脚本测试有人脑无手。GhostQA 是**有脑、有手、有判据、还自证清白**的测试员。

给定一个 Web 应用与需求规格，GhostQA 在无人干预下：自主建立软件状态模型（State Graph）→ 用状态价值函数选择高价值测试路径 → 用三层 Oracle 判断异常（硬异常/结构异常/需求语义异常）→ 对每个候选 Bug 按 **BugFingerprint** 重放验证 → 用 **ddmin** 自动最小化复现路径 → 交付带证据的可信缺陷报告。

## 当前状态：v0.4 preview（Dashboard）· 算法层仍是 v0.3.2

| 能力 | 状态 |
|---|---|
| SimBench 算法实验层（3 个模拟 App） | ✅ Implemented |
| Playwright 真实浏览器执行器 | ✅ Implemented |
| BuggyShop 浅层 benchmark（11 页 / 10 bugs） | ✅ Implemented |
| BuggyFlow / DeepBench 深层 benchmark（16 页 / 14+2 holdout bugs，freeze `5355abd`） | ✅ Implemented |
| 两层状态模型（structural cluster + data-obs semantic variant） | ✅ Implemented |
| State similarity 接入 StateGraph / Explorer / Novelty | ✅ Implemented |
| Frontier planner（reset + replay known path） | ✅ Implemented |
| GhostPolicy v1.2/v1.3（局部评分 + 交互级 frontier + progressive payload） | ✅ Implemented |
| WorkflowBFS（非 AI、交互级 BFS 基线） | ✅ Implemented |
| 三层 Oracle + BugFingerprint + 三态 replay + ddmin | ✅ Implemented |
| CLI + JSON/HTML 报告 | ✅ Implemented |
| WebBench v0.2 + DeepBench v0.3 / v0.3.1 / v0.3.2 可追溯实验 | ✅ Implemented |
| 真实 LLM 实验 | ⏭ skipped（无 GHOSTQA_MODEL_* 凭据；Dashboard 可接真实 LLM） |
| Dashboard（FastAPI 实时控制台） | ✅ v0.4 preview |
| Android 扩展 | ⏳ Planned |

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

Dashboard（v0.4 preview，展示层，不改探索算法）：

```bash
python apps/buggy-shop/server.py 3939
python -m dashboard.server --port 8787
# 浏览器打开 http://127.0.0.1:8787/
```

三个视图：**总览**（默认，含 v0.3.9 return-cycle 对照）、**实时探索**（浏览器截图 / 状态图 / 决策日志）、**研究证据**（freeze / clean clone / 复现命令）。v0.3.9 / v0.3.8 数字来自 `GET /api/showcase`，读取已提交的 `experiments/published/` 产物，不在页面里写死研究结果。演示步骤见 `docs/DEMO.md`。

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
  - BFS = Ghost-full = 0.30；Ghost TTF=1 最快（当时字段名叫 T2Bug，语义是 first finding）；Ghost-noLLM=0.10。浅层空间里 BFS 与 Ghost 打平。
- **DeepBench v0.3**（BuggyFlow，深层，freeze `5355abd`）：`experiments/published/deepbench-v0.3/`
  - 61 unique runs。**Deep-BDR = 0**（所有策略，budget ≤ 120 都没有确认 trigger_depth≥4 的 bug）。
  - 浅层天花板 5/14=0.357（D1–D4, D8）。DFS@40 与 BFS@80 达到该天花板。
  - **Ghost-full / Ghost-noLLM = 0.071**（只确认 D4），**输给 BFS/DFS**。
  - 消融：Ghost-noFrontier@40 = 0.214，@120 = 0.357 —— **当前 Frontier relocate 是负贡献**。
  - Monkey@40 × 10 seeds：0.121±0.059。
  - 真实 LLM：skipped（无凭据）。MockLLM 数据不是真实大模型表现。
  - 详细表与负结果分析见 `experiments/published/deepbench-v0.3/summary.md`。
- **DeepBench v0.3.1**（同一冻结 app `5355abd`，算法 `45e5669`）：`experiments/published/deepbench-v0.3.1/`
  - 改的是 **action budgeting**（字段=1 个 opportunity、progressive payload、WorkflowBFS），不是 benchmark。
  - WorkflowBFS@40 Deep-BDR=0.111（确认 D6），`input_share=0`，`max_workflow_depth=4`。
  - Ghost-noFrontier@40 Deep-BDR=0.111；**Ghost-full（带 relocate）confirmed-BDR=0**（见 erratum），restore_ratio 最高 0.23。
  - DFS@120 BDR=0.429 Deep-BDR=0.111。BFS 仍未在 120 内确认 D6。
  - 不要把这些数字读成“Ghost 已解决深 workflow”。reachability 仍有效；confirmed-BDR 被 v0.3.2 supersede。
- **DeepBench v0.3.2**（同一 freeze `5355abd`，replay 修复 `b00de1f`）：`experiments/published/deepbench-v0.3.2/`
  - v0.3.2 fixed episode-aware replay correctness. Previously measured confirmed-BDR was understated because replay ignored reset boundaries. **Not** “Frontier algorithm improved.”
  - 纠正后 Ghost-full replay=1.0，BDR@40=0.071（D4），@80=0.143（D4,D8）。Ghost-full 仍未赢 DFS/BFS。
  - Ghost-noLLM@120 BDR=0.357 Deep-BDR=0.111（含 D6）。DFS@120 仍最高 0.429。
  - 延迟字段：TTF = first finding；TTCB = first confirmed bug；TTDCB = first deep confirmed bug。旧 `time_to_first_bug` 是 TTF 的 deprecated alias。
- **DeepBench v0.3.3**（同一 freeze `5355abd`，relocation study）：`experiments/published/deepbench-v0.3.3/`
  - 问的是 **reset+replay 值不值得付钱**，不是再调权重。产品版本仍是 v0.4 preview。
  - v0.3.2 Ghost-noLLM opportunity-cost Frontier：@40 wasted_relocate=0.429、chains=3、错过 D6；@120 BDR=0.357（含后来的 D1–D3 与 D6）。
  - Shadow Frontier 在 step 6 就会建议 hop；NoFrontier 在同一步确认 D6。推荐本身是错的，不只是 restore 贵。
  - Marginal：1 次 hop、productive=1、wasted=0，BDR 与 NoFrontier 相同（D4/D6/D8）。Momentum/Lease：0 hop。
  - **默认应关闭 reset+replay Frontier。** 不是 “Frontier 理论不成立”，而是当前预算下 inventory-sum + 全局 reset 不划算。
- **DeepBench v0.3.4**（同一 freeze `5355abd`，post-reach）：`experiments/published/deepbench-v0.3.4/`
  - 产品 `ghost` / `ghost-nollm` = NoFrontier。问的是到达深状态后会不会测。
  - P0 到达 depth=4 且确认 D6，但 deferred=0（会走、不深挖）。
  - `ghost-deferred`@120 BDR=0.429 与 DFS 打平，Deep-BDR 仍 0.111（D6 保留），deferred=19。
  - Full postreach/exploit：deep interactions ↑ 但 **D6 消失、depth 4→2/3**。不能当默认。
  - D5/D7/D9–D14 仍未到达。下一瓶颈更像 sequence/semantic，不是再堆 payload。
- **DeepBench v0.3.5**（同一 freeze `5355abd`，sequence/branch）：`experiments/published/deepbench-v0.3.5/`
  - 产品 Ghost 仍是 NoFrontier。本轮加 hub 检测、branch commitment、mutation follow-up、return-to-hub（不 reset）。
  - `ghost-sequence`@40 确认 **D6 + D12**，Deep-BDR=0.222（此前 Deep-BDR 天花板是 0.111）。
  - S1/S2 无 commitment 会丢 D6。S3 保 D6 但丢掉 D4/D8，BDR=0.143。
  - DFS@120 仍是最高 BDR（0.429）。sequence 是 experimental，不是新默认。
- **DeepBench v0.3.5.1**（同一 freeze，measurement only）：`experiments/published/deepbench-v0.3.5.1/`
  - 行为未改：ghost-sequence 仍是 D6+D12，BDR=0.143，Deep-BDR=0.222，TTCB=14。
  - `hub_count=57` 是 exact-sig 变体计数；**canonical_hub_count=3**。87 次 sequence instance ≠ 87 条 unique branch。
- **DeepBench v0.3.5.1-r2**（lifecycle 纠偏）：`experiments/published/deepbench-v0.3.5.1-r2/`
  - `mean/max sequence_len` 不再恒为 1；max=6。`unique_branches_terminally_tested=6`（returned ∪ finding）。37 次 finding terminal ≠ 37 个 bug（unique fingerprints=4）。
- **DeepBench v0.3.6**（同一 freeze，contextual sequence memory）：`experiments/published/deepbench-v0.3.6/`
  - `ghost-structural-memory`（C1）@80–120：BDR=0.429（并列 DFS/deferred），**Deep-BDR=0.667**，确认 D6/D7/D11–D14。D6+D12 仍在。
  - C0 `ghost-sequence` 仍是 D6+D12；attempts/branch 10.9 → C1 2.8。
  - C2 与 C1 同一 confirmed 集合；C3@40 丢掉 D7。产品默认仍是 NoFrontier、无 sequence。
- **v0.3.7 generalization**（算法已冻结，不再调 DeepBench）：`experiments/published/generalization-v0.3.7/`
  - Holdout H1/H2：C1 **0/2**；DFS/BFS **1/2**（仅 H1）。H2 无人确认。
  - BuggyShop：C1=C0=**1/10**（W5），6 states；BFS@120 **7/10**。结论：**C. DeepBench-specific research result**。产品默认不改。
- **v0.3.8 application-shape**（不调参）：`experiments/published/application-shape-v0.3.8/`
  - BuggyShop 6 states = 嵌套 hub 后 `returning` 锁死 index↔cart（116 return_attempt，**returned terminal=0**）。
  - H1：step 0 DFS 进 settings，C0/C1 进 login（本 run 的 distractor 分类）。
  - H2：全局失败；C1 billing entries 32/53/87/97，qty 从未落到负数。
  - Clean-clone：`python -m benchmark.application_shape_reproduce --root experiments/published/application-shape-v0.3.8 --verify`
- **v0.3.9 return-cycle guard**（experimental）：exact `new_sig` repeat during return → abandon, not complete. **Outcome A** on inspected BuggyShop lock + DeepBench regression (D6/D12 kept, 0 escapes). Product default unchanged. `experiments/published/return-cycle-guard-v0.3.9/`

## 架构

```
ghostqa/
├── state/        # 两层状态 / 签名 / 相似度 / StateGraph
├── executor/     # Executor / Sim / Playwright / nav history
├── exploration/  # Explorer / PayloadPolicy / FrontierPlanner v1.1 / WorkflowBFS
├── oracle/       # 三层 Oracle / BugFingerprint / 规格断言 DSL
├── replay/       # 三态重放验证器
├── minimizer/    # ddmin 可执行最小复现
├── agent/        # ModelGateway：Mock / Null / OpenAI 兼容
└── report/       # JSON + HTML 报告
dashboard/        # v0.4 preview：总览 / 实时探索 / 研究证据（FastAPI + 单页）
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

- `docs/DEMO.md` — Dashboard 演示路径（总览 / 实时探索 / 研究证据）
- `docs/PROJECT_PLAN.md` — 总体设计（产品定义/算法/架构/路线图）
- `docs/TECH_SURVEY.md` — 学术与工业竞品调研（2026 诚实版）
- `docs/TRUTH_AUDIT.md` — v0.1 文档-代码一致性审计
