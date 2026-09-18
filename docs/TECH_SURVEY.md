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

## 二、工业界现状

- KaneAI(LambdaTest)/testRigor/Testim/Functionize/Autify/Tricentis/BrowserStack Low Code：自然语言/录制**生成脚本+自愈定位器**，属"辅助执行"，不主动探索找 bug。
- Applitools/Percy：视觉回归比对层。
- mabl：低代码+自愈，仍以录制流程为主。
- **有探索色彩的仅 qa.tech、Momentic**：流程发现/覆盖探索，但**无语义 Oracle、无重放确认与复现最小化的可信闭环**。
- QA Wolf：AI 辅助人力外包。

**结论：没有任何工业产品同时具备「状态空间探索 + 语义 Oracle + 自动验证最小化」组合。**

## 三、GhostQA 差异化（最终确认的 3+2 创新点）

1. **状态价值函数引导的 LLM/VLM 探索测试**（核心）：区别于 MemoDroid 的记忆复用与 FastBot 的 UCB，用 VLM/LLM 对状态-动作对估计"bug 发现价值"。
2. **规格驱动语义 Oracle 接入探索闭环**：把 WebTestPilot 思路扩展到与主动探索结合，幻觉误报由重放验证兜底。
3. **重放验证 + ddmin 最小复现的可信报告闭环**：报告即已验证，每条 bug 附最小复现路径。
4. （储备）统一状态抽象，Web→Android 跨平台扩展。
5. （储备）经验-价值双轮数据飞轮：缺陷模式库反哺探索策略。
