# GhostQA 专项技术调研（学术 + 工业）

> 2026-09-18 联网调研。用于支撑差异化判断。

## 一、学术界现状（2023–2026）

### LLM/VLM + GUI 测试代表工作

| 工作 | 发表 | 核心 | 效果 | 缺陷 |
|---|---|---|---|---|
| GPTDroid | ICSE'24 | 测试建模为 Q&A，LLM 读 GUI 生成脚本+功能记忆 | 活动覆盖率+32%，多发现31%缺陷，53个新bug | Oracle 弱，仍以覆盖/崩溃为引导 |
| AutoDroid | 2023 | 随机探索建 UTG 作 App Memory+LLM 常识 | 任务执行类 | 目标是完成任务而非找 bug |
| VisionDroid | FSE 系'24 | 首个 MLLM 检测非崩溃功能 bug（错位/逻辑不一致） | 29个新bug | Oracle 仅靠视觉启发，误报未系统解决 |
| MemoDroid | ASE'25 | 三层记忆（情节/反思/策略）跨 App 复用经验 | 覆盖率+79~96%，缺陷+57~198%，49新bug | 最强基线；但无"状态价值函数前瞻探索"、无语义Oracle闭环 |
| WebTestPilot | FSE'26 | 神经符号：NL规格→断言（GUI元素符号化） | bug检测96%精确/召回 | **Web端最接近我们语义Oracle的工作，但不做自主探索** |
| TOGLL | ICSE'25 | 代码LLM生成断言Oracle | 超EvoSuite/TOGA | 基于代码非需求 |
| CHARD/Clapp | SCP'21 | delta debugging 最小化 Monkey/APE 崩溃序列 | 成熟 | 只服务随机工具的崩溃序列，非 LLM agent 轨迹 |

经典基线：Monkey、DroidBot、Stoat、Sapienz、APE、FastBot（字节 UCB+CV）、Humanoid、TimeMachine、Q-testing。

### 三个重点方向成熟度判定

1. **LLM/VLM 状态价值引导探索**：低成熟度。FastBot=UCB 奖励、MemoDroid=策略记忆，**无工作用 VLM 对状态-动作对做前瞻价值估计**。→ 明确空白。
2. **需求驱动语义 Oracle**：新兴。仅 WebTestPilot（Web 端，神经符号化）；移动端无；**均未接入主动探索闭环**。
3. **LLM Agent 轨迹的重放验证+最小化**：中低。delta debugging 成熟但只用于随机工具崩溃序列；**对 LLM agent 长轨迹的"确认幻觉/真bug+最小复现"无人系统做**。

## 二、工业界现状（2026 年复核，诚实版）

> v0.2 复核结论：竞品在"自主探索"上进展很快，**GhostQA 的差异不能再表述为"第一个让 AI 自己测试"**。

- **Momentic**：已公开宣传 "point at URL → real bugs"、自动录制、复现步骤、flow graph、覆盖缺口探索。是自主探索测试方向最直接的竞品。
- **QA.tech**：明确提供 "autonomous exploratory QA agents"。
- **BrowserStack / KaneAI(LambdaTest) / testRigor / mabl / Functionize / Autify / Tricentis**：主体仍是"自然语言/录制生成脚本+自愈执行"范式，探索能力有限或为辅。
- **Applitools / Percy**：视觉回归比对层，非执行模型。
- **OpenAI testing-agent-demo 等开源示范**：证明通用 Agent 可做测试，但无系统化探索与验证闭环。

**竞品普遍缺失的环节**（基于公开资料判断，如有更新需再核）：
1. 探索策略本身不透明、不可复现、无公开 baseline 对比——"黑盒 Agent 说找到了 bug"。
2. 缺少**规格驱动的语义 Oracle**（用需求文档判定行为对错，而非只看崩溃）。
3. 缺少**按 BugFingerprint 的重放验证**与**可执行的最小复现路径**——报告可信度的最后一公里。
4. 没有公开的 benchmark 与消融实验支撑其"更聪明"的声称。

## 三、GhostQA 差异化（v0.2 修订版）

1. **Transparent & Measurable Value-Guided Exploration**：状态价值函数各项（Novelty/UCB/Risk/Semantic/Repetition/Cost）全透明、权重可调、决策摘要可审计；与 Monkey/DFS/BFS/LLM-naive 在同一 benchmark 上对比。
2. **Specification-Driven Semantic Oracle**：需求规格 → 行为断言，观测仅用页面呈现值，接入探索闭环。
3. **Bug-Specific Replay Verification**：统一 BugFingerprint，候选 bug 必须指纹级重放确认，过滤幻觉与误报。
4. **Executable Minimum Reproduction**：三态谓词（PASS/FAIL/INVALID）+ ddmin，输出的最小路径保证从干净环境可逐步执行。
5. **Open GhostBench + Baseline/Ablation**：SimBench（算法迭代）+ WebBench（真实浏览器），多种子 mean±std 公开，消融（no-LLM / no-graph）证明每个组件的边际贡献。
