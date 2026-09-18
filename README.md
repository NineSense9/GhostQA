# GhostQA — AI 驱动的自主探索式软件测试系统

> Monkey 有手无脑，脚本测试有人脑无手。GhostQA 有脑、有手、有判据，还自证清白。

给定被测软件（v1：Web 应用）与需求描述，GhostQA 自主完成：
**状态空间建模 → 价值引导探索 → 三层 Oracle 异常判断 → 重放验证 → 最小复现 → 证据报告**。

详细设计见 `docs/PROJECT_PLAN.md`，技术调研见 `docs/TECH_SURVEY.md`。

## 快速开始

```bash
# 环境（已内置 .venv）
./.venv/Scripts/python.exe -m pytest tests -q          # 31 项单元测试
./.venv/Scripts/python.exe -m benchmark.runner --budget 120 --seed 42
```

## 当前状态（v0.1）

- [x] 状态模型/签名/相似度/状态图（纯 stdlib）
- [x] 执行器抽象 + 确定性模拟执行器（Sim）
- [x] 探索主循环 + Monkey/DFS/BFS/LLM-naive/GhostPolicy 五种策略
- [x] 三层 Oracle（L1 硬异常 / L2 结构异常 / L3 规格语义断言）
- [x] 重放验证器（候选 bug 必须复现才确认）
- [x] ddmin 复现路径最小化
- [x] JSON/HTML 缺陷报告
- [x] GhostBench v0：2 个模拟 App、10 个埋入 bug、首次基线实验已落盘
- [ ] Playwright Web 执行器（P1）
- [ ] BuggyShop 真实演示 App（P1）
- [ ] 真实 LLM 接入（P1）
- [ ] Web Dashboard（P2）

## 首次实验（2026-09-18, budget=120, seed=42）

sim-shop（7 个埋入 bug）Bug Discovery Rate：

| Monkey | DFS | BFS | LLM-naive (120次调用) | GhostQA-noLLM | GhostQA+MockLLM (9次调用) |
|---|---|---|---|---|---|
| 0.57 | 0.57 | 0.57 | **0.14** | **0.71** | 0.57 |

原始数据：`experiments/runs/2026-09-18-v0.1-first/metrics.json`

已知局限（诚实记录）：GhostPolicy 尚未推理应用内部状态依赖（如"清空购物车后正是测试支付之时"），
这是 v0.2 引入状态感知规划（state-aware planning）的直接动机。
