# GhostQA v0.1 Truth Audit

> 2026-09-18 · 对照 61bf126 的实际代码核查文档声称。

## IMPLEMENTED（代码+测试真实存在）
- 状态模型/签名/相似度/状态图（state/），单测覆盖
- SimExecutor 模拟执行器（确定性，可崩溃/重置/输入规则/守卫）
- 5 种探索策略：Monkey/DFS/BFS/LLM-naive/GhostPolicy v1（价值函数+快慢双通道）
- 三层 Oracle：L1（crash/js_error/blank）、L2（dead_action/nav_loop）、L3（规格断言 DSL）
- 重放验证器 + ddmin 最小化（端到端测试：6步→4步理论最短）
- GhostBench v0：**2 个 Sim App / 10 个埋入 bug**（sim-shop 7 + sim-todo 3）
- JSON/HTML 报告生成器
- 37 项单测

## PARTIAL（有代码但与文档有差距 —— v0.2 已修复项标注 ✅）
- ⚠️→✅ `is_new_state` slow-path trigger 恒为 False（目的状态在决策前已被 add_transition 入图）。v0.2 改为 transition 前记录 `entered_new_state`，含回归测试。
- ⚠️→✅ bug 匹配粒度粗（kind+单字段），不同 crash 可能互相冒充。v0.2 引入统一 BugFingerprint（kind×url×element×error签名）。
- ⚠️→✅ manifest 空 match 会导致 Discovery Rate 虚高。v0.2 强制判别性 match + 重复检测抛错。
- ⚠️→✅ ddmin 文档声称 dependency-aware，实际仅检查非空。v0.2 实现三态谓词（PASS/FAIL/INVALID），INVALID 序列（元素缺失/不可执行）直接淘汰。
- ⚠️ MockLLM 关键词语义项在首次实验中为负收益（0.57 < 0.71 noLLM）。v0.2 重设计 GhostPolicy v1.1（门控调用）。
- ⚠️ PROJECT_PLAN 曾写"3 Sim Apps/15 Bugs"，实际 2/10。v0.2 文档改为 Implemented/Planned 分栏。

## NOT IMPLEMENTED（v0.1 时仍只是计划）
- Playwright 真实 Web 执行器（v0.2 主线）
- 真实 LLM Gateway（OpenAI 兼容）
- CLI 入口、WebBench、多种子统计实验、Dashboard（v0.3+）
