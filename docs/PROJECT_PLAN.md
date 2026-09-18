# GhostQA 项目总体设计文档

> ⚠️ **历史文档（Historical v0.1 Design, 2026-09-18）**
> 本文是 v0.1 立项时的设计稿，其中的范围、计划与部分判断已被 v0.2 实际实现修正。
> **当前事实以 `docs/HANDOFF_TO_GROK.md`（交接与现行路线）和代码为准。**
> 背景材料：《AIC赛题分析与项目方向报告.md》。

---

## A. GhostQA 最终产品定义（一页版）

**GhostQA 是一个 AI 驱动的自主探索式软件测试系统。**

给定一个被测软件（v1：Web 应用）和一段需求描述，GhostQA 在无人干预的情况下：

1. **建模**：边探索边构建被测软件的状态空间模型（State Graph）；
2. **决策**：用"状态价值函数"评估每个候选动作的测试价值，智能选择下一步——而不是随机乱点（Monkey）或写死路径（脚本）；
3. **判断**：用三层 Oracle 判断软件是否出错——硬异常（程序判定）、结构异常（规则+VLM）、语义异常（需求规格→行为断言）；
4. **验证**：任何候选 bug 必须经过自动重放确认，过滤幻觉与误报；
5. **交付**：自动生成最小复现路径与带截图/录像证据的缺陷报告。

**一句话**：Monkey 有手无脑，脚本测试有脑（人脑）无手，GhostQA 是**有脑、有手、有判据、还自证清白**的测试员。

**与最相近事物的本质区别**：
- vs Monkey/DroidBot：它们无状态价值判断，GhostQA 的探索由价值函数引导；
- vs Selenium/Playwright 脚本：它们执行人写的路径，GhostQA 自主生成路径；
- vs BrowserUse/Computer Use Agent：它们是"完成任务"的 Agent，目标是"做成一件事"；GhostQA 是"找茬"的 Agent，目标是"系统地证明软件会错"——目标函数完全不同（覆盖+发现 vs 任务成功）；
- vs mabl/testRigor 等 AI 测试产品：它们是"录制/生成脚本+自愈执行"，无自主探索、无语义 Oracle、无验证最小化闭环；
- vs 学术工作（GPTDroid/MemoDroid/WebTestPilot）：没有任何工作把「价值引导探索 × 规格语义 Oracle × 重放验证最小化」三者闭环。

---

## B. GhostQA v1 范围

### v1 主战场决策：Web 应用（推翻此前报告中的 Android 建议）

| 维度 | Android | Web | 结论 |
|---|---|---|---|
| Agent 稳定性 | 模拟器+ADB 链路长、脆 | Playwright 成熟稳定 | Web |
| 状态可获取性 | UI hierarchy 需 uiautomator，时延高 | DOM + Accessibility Tree 直接可读 | Web |
| 数据/Benchmark 可构建性 | 需打包 APK | 静态 HTML/JS 即可造 buggy app | Web |
| Demo 效果 | 手机屏幕投影 | 浏览器+大屏，天然可视 | Web |
| 重放确定性 | 模拟器时序漂移大 | Playwright 重放确定性高 | Web |
| 竞赛创新度 | 学术工作多（GPTDroid 等） | 学术工作少（仅 WebTestPilot，且无探索闭环） | Web |
| 开发成本 | 高 | 低 | Web |
| 生态 | Appium/Maestro | Playwright | 平 |

**理由陈述**：原报告建议 Android 是基于"演示戏剧性"的直觉，但经过竞品调研发现：(1) Android 端 LLM 测试学术工作已密集（GPTDroid/MemoDroid/VisionDroid），差异化空间反而小；(2) Web 端仅有 WebTestPilot 且不做探索，我们的三合一闭环在 Web 端是空白；(3) 工程上 Web 链路最短，符合 Working > Fancy。**Android 作为 v2 扩展方向**（统一状态抽象预留接口）。

### v1 做什么
- Web 应用的自主探索测试（单页/多页应用均可）
- 状态图构建与可视化数据输出
- 三层 Oracle（L1 硬异常 + L2 结构异常 + L3 语义断言）
- Bug 重放验证 + ddmin 复现路径最小化
- JSON/HTML 缺陷报告
- GhostBench v0：模拟 App 测试床 + 1 个真实 buggy Web App
- Baseline 对比实验：Monkey / DFS / BFS / LLM-naive / GhostQA

### v1 不做什么
- 不做 Android/桌面端（v2）
- 不做多 Agent 架构（单 Agent + 策略层即可）
- 不做模型微调（用现成 API/开源模型）
- 不做知识图谱/RAG（除非实验证明对指标有贡献）
- 不做用户系统/多租户（Dashboard 单机即可）
- 不追求"发现语义 bug 的数量"，先保证"发现的每个 bug 都是真的"（精确率优先）

---

## C. 与现有方案对比

| 维度 | Monkey | Appium/Playwright 脚本 | 传统 Model-Based Testing | LLM GUI Agent (BrowserUse等) | 商业 AI 测试 (mabl/testRigor/KaneAI) | **GhostQA** |
|---|---|---|---|---|---|---|
| 路径来源 | 随机 | 人工编写 | 人工建模后自动生成 | LLM 即时决策 | 人工录制/NL 生成 | **价值函数引导的自主探索** |
| 状态模型 | 无 | 无 | 有（人工建） | 无/弱 | 无 | **自动构建 State Graph** |
| 测试目标 | 压测/崩溃 | 回归验证 | 覆盖验证 | 完成任务 | 回归验证 | **发现未知缺陷** |
| Oracle | 仅崩溃 | 人工断言 | 模型断言 | 无（任务成功即对） | 人工断言+视觉回归 | **三层 Oracle（含需求语义）** |
| 误报控制 | n/a | n/a | n/a | n/a（不找 bug） | 视觉 diff 噪声大 | **重放验证后才报告** |
| 复现交付 | 无 | 脚本即复现 | 可复现 | 无 | 脚本 | **自动最小化复现路径** |
| 语义理解 | 无 | 无 | 无 | 有（但用于任务） | 部分 | **用于探索决策+Oracle 双用途** |

**本质区别一句话**：其他方案里"智能"要么在测试之外（人写脚本/人建模），要么用于别的目标（完成任务）；GhostQA 把智能同时用于**探索决策、异常判断、结果验证**三个环节，并形成闭环。

---

## D. 技术架构

```
┌─────────────────────────── GhostQA v0.1 ───────────────────────────┐
│                                                                    │
│  dashboard/ (Web 前端, v0.2+)        report/ (HTML/JSON 报告)       │
│       ▲                                   ▲                        │
│       │ reads                             │ reads                  │
│  ┌────┴───────────────────────────────────┴────┐                  │
│  │              Trace Store (JSONL)             │                  │
│  └────┬───────────────────────────────────┬────┘                  │
│       │                                   │                        │
│  ┌────┴─────┐  observe/execute     ┌──────┴──────┐                │
│  │ Explorer │ ◄──────────────────► │  Executor    │                │
│  │ (主循环)  │                      │  - Playwright│                │
│  └────┬─────┘                      │  - Sim(测试)  │                │
│       │                            └──────┬──────┘                │
│       │ uses                              │ drives                │
│  ┌────┴──────────────┐               ┌────┴────┐                  │
│  │ ExplorationPolicy  │               │ 被测App  │                  │
│  │ Random/DFS/BFS/    │               └─────────┘                  │
│  │ LLMNaive/GhostV1   │                                          │
│  └────┬──────────────┘                                            │
│       │ uses                                                       │
│  ┌────┴─────────┐  ┌─────────────┐  ┌──────────────┐              │
│  │ StateGraph   │  │ OracleEngine │  │ ModelGateway │              │
│  │ + Similarity │  │ L1/L2/L3     │  │ (LLM/VLM,可关)│             │
│  └──────────────┘  └─────────────┘  └──────────────┘              │
│                                                                    │
│  验证管线（离线，测试后运行）:                                        │
│  CandidateBug → ReplayValidator → ddmin Minimizer → ConfirmedBug   │
└────────────────────────────────────────────────────────────────────┘
```

### 模块职责（输入/输出/依赖）

| 模块 | 输入 | 输出 | 依赖 |
|---|---|---|---|
| `state/models.py` | — | UIElement/GUIState/Action/Step/BugReport 数据结构 | 无（纯 stdlib） |
| `state/signature.py` | GUIState | 状态签名（结构 hash）+ 截图 ahash | 无 |
| `state/graph.py` | (state, action, state') 转移 | StateGraph：节点/边/访问计数/未探索动作 | models, signature |
| `executor/base.py` | Action | ExecResult(ok, crashed, js_errors, state, events) | models |
| `executor/playwright_web.py` | url + Action | 真实 Web 观察与执行 | playwright（可选依赖） |
| `executor/sim.py` | SimAppDef + Action | 模拟执行（确定性，供单测/实验） | base |
| `exploration/policy.py` | graph, state, candidates, llm | 选中的 Action | graph, gateway |
| `exploration/explorer.py` | executor, policy, budget | ActionTrace + 候选 bug 列表 | 全部 |
| `oracle/engine.py` | (prev_state, action, exec_result, new_state, spec) | List[Finding(severity, kind, desc, evidence)] | models, gateway(可选) |
| `replay/validator.py` | executor_factory, trace, finding | Confirmed/Unconfirmed + 重放轨迹 | executor |
| `minimizer/ddmin.py` | executor_factory, action_seq, predicate | 最小复现序列 | replay |
| `report/generator.py` | trace + confirmed bugs | report.json + report.html | 无 |
| `agent/gateway.py` | prompt/messages | LLM 响应（含 MockLLM 确定性模式） | 无（HTTP 可选） |

---

## E. 核心算法设计 v0.1

### E.1 State（状态）

```python
GUIState:
  app: str              # 被测应用标识
  url: str              # 规范化 URL（去随机参数）
  title: str
  elements: tuple[UIElement]   # 可交互元素集合
  screenshot_ahash: int | None # 64-bit 平均哈希（可选）
  obs: dict             # 可观测应用数据（如购物车总价显示文本）
  meta: dict

UIElement:
  eid: str        # 稳定标识（v1: role+text+index 的 hash；Web端优先 data-testid）
  role: str       # button/link/input/select/...
  text: str       # 可见文本（截断 64 字符）
  enabled: bool
```

**状态签名**（程序计算，零模型成本）：
`signature = sha1( normalize(url) + title + sorted( (role, text) for each element ) )`

### E.2 Action（动作）

```python
Action:
  type: click | input | scroll | back | wait | navigate
  target_eid: str | None
  text: str | None        # input 时的输入内容
```

动作空间约束：
- 候选动作 = 当前 state 可见 enabled 元素 × 其支持的动作类型；
- input 文本来自**输入词表**（边界值库：空串、超长串、特殊字符、正常值、SQL/XSS 片段）按字段类型选取，而非 LLM 每次现编；
- `back` 仅在历史非空时可用；`wait` 仅在上一步有异步迹象时注入；
- 全局步数预算 + 单状态访问上限，防止无限探索。

### E.3 State Similarity（状态去重）

三级判定：
1. `signature` 相同 → **同一状态**；
2. 同 URL 且元素集合 Jaccard ≥ 0.8，或截图 ahash 汉明距离 ≤ 10 → **相似状态**（视为同簇，降低探索优先级，但仍记录转移）；
3. 否则 → **新状态**。

防循环机制：
- (state_sig, action_key) 访问计数，UCB 奖励随次数衰减；
- 最近 K 步签名序列检测 A→B→A→B 周期，命中即对该边施加惩罚并触发 LLM slow-path"如何脱困"。

### E.4 State Graph

有向图：节点 = 状态签名（含首次发现时间、访问数、发现的动作集合）；边 = (src_sig, action_key) → (dst_sig, count)。
持久化为 JSON，供 Dashboard 渲染与实验分析。

### E.5 Exploration Policy v1（GhostPolicy）

**核心公式**（程序项全部本地计算；LLM 项仅 slow-path）：

```
Score(s, a) = w1 · Novelty(ŝ)               # a 预期到达状态的新颖度（未知则 1）
            + w2 · UCB(s, a)                # 1/sqrt(1+visits(s,a)) 未探索奖励
            + w3 · Semantics(s, a)          # LLM 语义重要性 0~1（缓存，slow-path）
            + w4 · Risk(s)                  # 风险热点 0~1（程序启发式）
            − w5 · Repetition(s, a)         # 近期重复惩罚
            − w6 · Cost(a)                  # 动作成本（input>click）
```

各项计算方式：
- **Novelty**：执行过则按目标状态签名查 graph；新签名=1，相似簇=0.3，已访问=0.05。未执行过的边取 0.8（乐观探索）。
- **UCB**：经典 curiosity 项，保证系统性覆盖（程序）。
- **Risk(s)**：程序启发式——含表单/输入框 +0.3；含"支付/删除/提交/结算"关键词 +0.4；该状态历史发现过 L2 异常 +0.3（上限 1）。
- **Semantics(s, a)**：**LLM 唯一介入点**。输入：当前页面要素摘要 + 需求规格摘要 + 候选动作列表（top-k by 程序分），输出每个动作的 0~1 价值分与一句理由（Decision Summary，供 Dashboard 展示）。结果按 state signature 缓存，同状态不重复调用。
- **Repetition**：近 10 步内 (s,a) 出现次数 × 0.2。
- **Cost**：click=0.05，input=0.1，navigate=0.02。

**Fast/Slow 双通道**：
- Fast path（默认每步）：纯程序分排序选 top-1。**零模型调用**。
- Slow path（触发式）：(a) 发现新页面类型；(b) 检测到循环；(c) 每 N=8 步定期；(d) 程序分 top-2 差距 < ε。此时调 LLM 对 top-k 候选打语义分，融合后决策。
- LLM 不可用时退化为纯程序策略（实验组之一）。

> 权重 v0.1：w1=1.0, w2=0.8, w3=1.2, w4=0.6, w5=1.0, w6=0.5。**所有权重放入 config，权重扫参本身就是实验之一。**

### E.6 Oracle（三层）

```python
Finding:
  kind: crash | js_error | blank | nav_loop | dead_action | semantic
  severity: high | medium | low
  description: str
  evidence: dict      # 截图路径/状态签名/观测值
  step_index: int
```

- **L1 硬异常（程序，100% 自动）**：进程/页面崩溃；console error / pageerror；HTTP 5xx；白屏（可交互元素数=0 且 body 文本为空）；应用意外退出。
- **L2 结构异常（规则为主）**：dead action（点击后签名与 URL 均无变化，且元素 enabled）；导航死循环（A→B→A 周期 ≥2）；无法返回（back 不可达初始簇）；表单提交后仍停留且无任何反馈文本。
- **L3 语义异常（规格驱动）**：需求规格 → **行为断言**。v0.1 断言以声明式 DSL 表达（人工写 5-10 条，LLM 辅助生成是 P1）：

```yaml
# buggy-shop 的语义断言示例
- id: cart_total_consistent
  when: page_contains("购物车")
  assert: obs("cart_total_display") == compute_total(obs("cart_items"))
  severity: high
- id: stock_non_negative
  when: always
  assert: int(obs("stock_display")) >= 0
  severity: medium
- id: login_gate
  when: action_is("click:个人中心")
  assert: not logged_in() implies url_contains("login")
  severity: high
```

**误报控制**：L3 命中不直接报 bug——进入候选池，必须过重放验证；同一签名 finding 去重；LLM judge（可选）对语义 finding 做二次确认并输出置信度，低于阈值降级为"待人工"。

### E.7 Replay Validator

```
CandidateBug → 加载 trace → 重置环境 → 逐步重放到 finding 步
            → 重新执行 Oracle → 同类 finding 复现？
            → 是: Confirmed → 交 Minimizer
            → 否: 标记 flaky（重试 3 次,仍否 → Unconfirmed, 不入报告）
```

### E.8 Minimizer（ddmin 复现路径最小化）

经典 delta debugging（Zeller ddmin）作用于动作序列：
谓词 `P(seq)` = "按 seq 重放后该 bug 仍复现"。
- 序列粒度按 chunk 二分递归删除；
- **GUI 适配**：删除某动作前检查其是否为后续动作的"依赖前置"（如 input 依赖先 click 聚焦、目标元素在该步必须存在于当前状态），不可行子序列直接判 P=False 跳过执行，节省重放成本；
- 输出最小复现序列 + 每步截图索引。

### E.9 Explorer 主循环

```
state = executor.reset(); graph.add(state)
loop until budget exhausted:
    candidates = available_actions(state)
    action = policy.select(graph, state, candidates, llm)
    result = executor.execute(action)
    new_state = result.state
    graph.add_transition(state, action, new_state)
    findings = oracle.inspect(state, action, result, new_state, spec)
    trace.append(Step(...)); bug_candidates.extend(findings)
    if crashed: executor.restart()
    state = new_state
# 探索结束 → 对每个候选 bug 做 validate+minimize → 生成报告
```

---

## F. Benchmark 方案：GhostBench v0

> 状态标注（2026-09-18 更新）：✅ Implemented / ⏳ Planned

### 组成
1. **SimApps（模拟测试床）** ✅：2 个模拟应用（sim-shop / sim-todo），共 10 个埋入 bug，覆盖 crash/js_error/dead_action/nav_loop/语义一致性/表单/边界 7 类。用途：算法快速迭代 + CI 回归 + 消融实验（确定性、零成本）。⏳ 第三个 App（sim-form）规划中。
2. **BuggyShop（真实 Web App）** ✅：`apps/buggy-shop/`，本地 stdlib 服务器 + 11 个静态页面 + localStorage 状态，埋 10 个真实 bug（见 `bugs.manifest.json`：id/类型/严重度/触发条件/fingerprint 匹配键/已知最短复现），语义断言见 `spec.json`。用途：真实环境验证 + 比赛 Demo。
3. ⏳（P2）2-3 个真实开源 Web 应用人工埋 bug，验证泛化性。

### Baselines
Monkey（随机）、DFS、BFS、LLM-naive（每步问 LLM，无状态图/无价值函数）、**GhostQA-full（GhostPolicy+三级 Oracle）**、GhostQA-noLLM（消融：w3=0）、GhostQA-noGraph（消融：Novelty/UCB 关闭）。

### 指标
Bug Discovery Rate（发现数/埋入数）、Unique Crash 数、State Coverage（访问签名数/总状态数，Sim 可精确计算）、Time-to-first-bug、Action 重复率、Token 成本/bug、Reproduction Success（确认数/候选数）、最小复现路径压缩比（原长/最小长）。

### 实验纪律
每次运行落盘 `experiments/runs/<timestamp>/`：config.yaml（权重/模型/seed/预算）、trace.jsonl、findings.json、metrics.json。**伪造数据 = 项目死刑**，Demo 里的对比数字必须能指向具体 run 目录。

---

## G. MVP 技术栈（明确到库）

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.13 | 生态+团队效率 |
| 包管理 | venv + pip | 环境已具备 |
| Web 执行 | `playwright` (sync API) | DOM/a11y/截图/重放一把抓，稳定性最好 |
| 模拟执行 | 自研 `sim.py`（纯 stdlib） | 确定性单测与零成本实验 |
| 状态图 | 自研 dict 图（v0.1 不引 networkx） | 依赖最小；需要算法时再升级 |
| 数据存储 | JSONL 文件（trace/findings/metrics） | 零依赖、可 git diff、实验纪律友好 |
| 后端 API | `fastapi`（v0.2 接入 Dashboard 时） | 标配 |
| 前端 | Next.js + Cytoscape.js（v0.2） | 状态图可视化 |
| LLM 接入 | `agent/gateway.py` 抽象 + OpenAI 兼容协议；MockLLM 内置 | 任何模型可插拔；单测零依赖 |
| 模型选择 | 决策 LLM：DeepSeek-V3/R1（成本）或 Qwen2.5-72B；VLM（v0.2 截图语义）：Qwen2.5-VL | 国产模型成本低、可复现 |
| 测试 | `pytest` | 标配 |

---

## H. Repo 结构

```
ghostqa/
├── docs/                     # 设计文档（本文件、调研、demo脚本、路线图）
├── ghostqa/                  # 核心包（算法与工程分离）
│   ├── state/                #   models / signature / similarity / graph
│   ├── executor/             #   base / sim / playwright_web
│   ├── exploration/          #   policy（含各baseline） / explorer
│   ├── oracle/               #   engine（L1/L2/L3） / spec DSL loader
│   ├── replay/               #   validator
│   ├── minimizer/            #   ddmin
│   ├── agent/                #   gateway（LLM抽象+Mock）
│   └── report/               #   generator（json/html）
├── apps/
│   └── buggy-shop/           # 真实 buggy Web App + bugs.manifest.json
├── benchmark/
│   ├── sim_apps.py           # 模拟测试床定义
│   └── runner.py             # baseline×策略 批量实验 + metrics
├── experiments/
│   └── runs/                 # 实验落盘（gitignore 大数据）
├── dashboard/                # v0.2 前端
├── tests/                    # pytest 单元测试
└── README.md
```

---

## I. 第一周开发计划

| 天 | 目标 | 产出 | 成功标准 |
|---|---|---|---|
| D1 | 项目骨架+核心数据结构 | repo、models、signature、graph | 单测过：签名去重正确 |
| D2 | Sim 执行器+动作空间 | sim.py、SimAppDef | 模拟商城可执行动作/可崩溃 |
| D3 | 主循环+3 个 baseline 策略 | explorer.py、Random/DFS/BFS | Sim 上跑通 50 步探索并出图 |
| D4 | L1/L2 Oracle + Trace | oracle engine、JSONL trace | 模拟 crash/dead-action 被捕获 |
| D5 | Replay 验证器 | validator.py | 候选 crash 重放确认/排除 |
| D6 | ddmin 最小化 | ddmin.py | 8 步路径压到 ≤4 步 |
| D7 | GhostPolicy v1 + 报告 + 周实验 | policy、report generator、Sim 对比实验 | GhostPolicy ≥ 各 baseline；出 metrics.json + HTML 报告 |

风险：D6 ddmin 的依赖前置检查比预期复杂 → 降级为"仅无依赖删除"；D7 实验量不足 → 至少跑 Sim（确定性快）。

---

## J. 第一批代码任务拆解

### P0（最小闭环，本轮直接实现）
| # | 任务 | 目的 | 文件 | 输入 | 输出 | 验收标准 | 依赖 |
|---|---|---|---|---|---|---|---|
| P0-1 | 数据模型 | 统一状态/动作/发现定义 | `state/models.py` | — | dataclass 集 | 可序列化/反序列化 | 无 |
| P0-2 | 状态签名与相似度 | 状态去重 | `state/signature.py`, `state/similarity.py` | GUIState | 签名/相似判定 | 同页同签名，改文本变签名 | P0-1 |
| P0-3 | 状态图 | 记录探索 | `state/graph.py` | 转移三元组 | 图+访问计数 | 重复转移合并计数 | P0-2 |
| P0-4 | Sim 执行器 | 无浏览器跑通全链路 | `executor/base.py`, `executor/sim.py` | SimAppDef+Action | ExecResult | 可 goto/crash/输入/重置 | P0-1 |
| P0-5 | 主循环+Random/DFS/BFS | 能探索 | `exploration/policy.py`, `exploration/explorer.py` | executor+budget | trace+graph | 50 步无异常完成 | P0-3/4 |
| P0-6 | L1/L2 Oracle | 抓异常 | `oracle/engine.py` | 执行结果+状态 | findings | crash/dead-action/loop 必报 | P0-4 |
| P0-7 | 重放验证 | 过滤误报 | `replay/validator.py` | trace+finding | Confirmed? | 真 crash 确认、假阳性排除 | P0-5/6 |
| P0-8 | ddmin 最小化 | 最小复现 | `minimizer/ddmin.py` | 动作序列+谓词 | 最短子序列 | 保持谓词为真且≤原长 | P0-7 |
| P0-9 | L3 语义 Oracle（DSL） | 语义 bug | `oracle/spec.py` + engine 扩展 | YAML 断言 | findings | 购物车金额不一致被抓 | P0-4/6 |
| P0-10 | 报告生成 | 交付物 | `report/generator.py` | trace+bugs | report.json/html | 含路径/证据/确认状态 | P0-8 |
| P0-11 | Sim 测试床+对比实验 | 量化基线 | `benchmark/sim_apps.py`, `benchmark/runner.py` | 策略×App | metrics.json | 4 策略×3 App 跑完出表 | 全部 P0 |

### P1（下周）
- P1-1 Playwright Web 执行器（observe: DOM→UIElement；execute: click/fill/back；console/pageerror 监听）
- P1-2 BuggyShop 真实 App + manifest（10 bug）
- P1-3 ModelGateway + MockLLM + GhostPolicy 语义项接入（含缓存）
- P1-4 Web 端 Replay 验证 + 最小化
- P1-5 GhostBench v0 完整实验（含 token 成本统计）

### P2（第 3-4 周）
- P2-1 FastAPI + Dashboard（Live Testing 三栏视图）
- P1-6 LLM 生成语义断言（规格→DSL 草稿，人工确认）
- P2-2 VLM 截图语义（白屏/遮挡/错位检测，ahash 升级）
- P2-3 Failure Corpus 收集与回归测试机制
- P2-4 真实开源 App 泛化实验

---
