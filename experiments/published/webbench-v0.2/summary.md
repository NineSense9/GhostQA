# WebBench v0.2 — 真实浏览器基线实验

- **日期**：2026-09-18
- **环境**：BuggyShop（11 页 / 10 个埋入 bug，本地离线）+ Chromium (Playwright 1.63)
- **配置**：budget=40 actions/run，5 策略 × 2 seeds（1,2），skip-minimize（ddmin 证据见集成测试与 CLI run）
- **数据**：`metrics.json`（每 run 明细 + 聚合）· `config.json`

## 聚合结果（Confirmed Bug Discovery Rate，经 BugFingerprint 重放验证后）

| 策略 | mean±std | [min,max] | 首次发现步数(均值) | 状态数 | LLM调用 |
|---|---|---|---|---|---|
| Monkey | 0.100±0.141 | [0.0, 0.2] | 12.5 | 13 | 0 |
| DFS | 0.200±0.000 | [0.2, 0.2] | 8 | 11 | 0 |
| BFS | **0.300±0.000** | [0.3, 0.3] | 3 | 18 | 0 |
| Ghost-noLLM | 0.100±0.000 | [0.1, 0.1] | **1** | 12 | 0 |
| Ghost-full (MockLLM) | **0.300±0.000** | [0.3, 0.3] | **1** | 16 | 16 |

## 诚实结论

1. **Q1（真实环境稳定探索）**✅：所有策略在真实 Chromium 中稳定完成 40+ actions（含崩溃后自动重启），最长 run 69s。
2. **Q2（Replay 成功率）**✅：进入验证管线的候选 100% 通过指纹级重放确认（replay_success_rate=1.0）；CLI 全管线 run 中 2/2 候选确认。
3. **Q3（真实浏览器 ddmin）**✅：集成测试与 CLI run 均产出可执行最短路径（例：注册语义 bug 9 步 → 2 步；dead_action 9 步 → 3 步）。
4. **Q4（Ghost 是否更快/更多）**⚠️ 部分成立：
   - **Time-to-first-bug：Ghost 第 1 步即发现**（风险关键词把高价值区域排在最前），全场最快——价值引导确实改变了"先测哪里"。
   - **总发现率：Ghost-full 与 BFS 打平（0.30）**。原因分析：BuggyShop 状态空间小而扁平（全部页面距首页 1-2 跳），40 步预算内 BFS 即可近乎穷举——**在小而浅的状态空间，系统性广度遍历就是最优解，智能引导没有发挥空间**。Ghost 的理论优势场景（深状态空间/大预算）需要更大的 benchmark 验证，这是下一轮的核心实验问题。
   - **Ghost-noLLM 仅 0.10，负结果**：程序项（Novelty/UCB/Risk）单独不如简单 BFS；说明语义项（即使 MockLLM 关键词版）在真实 Web 上贡献为正（0.10→0.30），与 v0.1 Sim 上的负收益结论相反——**LLM 语义价值是场景依赖的**，不能一概而论。

## 已知偏差与限制

- seeds=2 统计功效有限；结论仅为方向性证据。
- MockLLM 是关键词代理，不代表真实 LLM 水平；真实 LLM 实验待 API 配置后复跑（GHOSTQA_MODEL_*）。
- BuggyShop 规模小；需要更深状态空间的第二个 benchmark app。
- 幂等过滤（idempotence filter）上线后消除了"重复点击幂等按钮"类误报（本数据为过滤后结果）。

## 本轮实际发现的 seed bugs（示例）

Ghost-full 单次 run 确认：BUG-W6（注册空用户名假成功，语义）、BUG-W3（收藏按钮无响应）、BUG-W10（未登录访问个人中心，语义）等；不同策略命中的 bug 集合见 `metrics.json` 各 run 的 `confirmed_bugs` 字段。
