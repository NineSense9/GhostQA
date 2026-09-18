# GhostQA — AI 驱动的自主探索式软件测试系统

> Monkey 有手无脑，脚本测试有人脑无手。GhostQA 是**有脑、有手、有判据、还自证清白**的测试员。

给定一个 Web 应用与需求规格，GhostQA 在无人干预下：自主建立软件状态模型（State Graph）→ 用状态价值函数选择高价值测试路径 → 用三层 Oracle 判断异常（硬异常/结构异常/需求语义异常）→ 对每个候选 Bug 按 **BugFingerprint** 重放验证 → 用 **ddmin** 自动最小化复现路径 → 交付带证据的可信缺陷报告。

## 当前状态：v0.2（Real-Web Proof）

| 能力 | 状态 |
|---|---|
| SimBench 算法实验层（2 个模拟 App / 10 个埋入 bug） | ✅ Implemented |
| Playwright 真实浏览器执行器（观察/动作/稳定元素定位） | ✅ Implemented |
| BuggyShop 确定性测试环境（11 页 / 10 个埋入 bug / manifest+spec） | ✅ Implemented |
| 三层 Oracle（L1 硬异常 / L2 结构异常+幂等过滤 / L3 规格语义断言） | ✅ Implemented |
| BugFingerprint 统一身份 + 三态重放验证（PASS/FAIL/INVALID） | ✅ Implemented |
| ddmin 可执行最小复现（真实浏览器内验证） | ✅ Implemented |
| 5 种策略基线（Monkey/DFS/BFS/LLM-naive/GhostPolicy） | ✅ Implemented |
| GhostPolicy v1.1（门控 LLM 调用：Uncertainty/NovelState/Stuck/SpecRelevance） | ✅ Implemented |
| 真实 LLM Gateway（OpenAI 兼容，超时/重试/缓存/降级/token统计） | ✅ Implemented |
| CLI 端到端命令 + JSON/HTML 报告 | ✅ Implemented |
| WebBench 基线实验（5 策略 × 多种子，mean±std） | ✅ Implemented |
| Dashboard | ⏳ Planned (v0.3) |
| Android 扩展 | ⏳ Planned (v0.3+) |

## 快速开始

```bash
git clone https://github.com/NineSense9/GhostQA.git
cd GhostQA
python -m venv .venv && .venv/Scripts/activate        # Windows
pip install -e ".[dev]"
playwright install chromium

pytest -m "not integration"      # 41 项单元测试（Sim，无需浏览器）
pytest -m integration            # 9 项集成测试（真实 Chromium + BuggyShop）
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

- **首次基线实验（SimBench，v0.1）**：`experiments/runs/2026-09-18-v0.1-first/metrics.json`（本地）
- **WebBench v0.2（真实浏览器，5 策略 × 2 种子）**：`experiments/published/webbench-v0.2/`
  - 结论摘要见 `experiments/published/webbench-v0.2/summary.md`
  - 诚实要点：小型扁平应用上 BFS 与 Ghost-full 打平（0.30）；Ghost 在 time-to-first-bug 上最快（第 1 步）；Ghost-noLLM 仅 0.10——负结果已记录并分析。

## 架构

```
ghostqa/
├── state/        # 状态模型 / 签名 / 相似度 / StateGraph
├── executor/     # Executor 抽象 / SimExecutor / PlaywrightWebExecutor
├── exploration/  # Explorer 主循环 / 5 种策略（含 GhostPolicy v1.1）
├── oracle/       # 三层 Oracle / BugFingerprint / 规格断言 DSL
├── replay/       # 三态重放验证器
├── minimizer/    # ddmin 可执行最小复现
├── agent/        # ModelGateway：Mock / Null / OpenAI 兼容（降级回退）
└── report/       # JSON + HTML 报告
apps/buggy-shop/  # 确定性测试环境（server + 11 页 + spec + manifest）
benchmark/        # SimBench (runner.py) + WebBench (web_runner.py)
experiments/      # published/ 可引用证据；runs/ 本地大文件(gitignore)
docs/             # PROJECT_PLAN / TECH_SURVEY / TRUTH_AUDIT
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
