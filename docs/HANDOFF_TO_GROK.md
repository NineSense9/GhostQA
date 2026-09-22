# GhostQA 技术交接文档

> 原 v0.2 交接（审计基线 `9c6c0a0`，文档提交 `94f5db1`）仍保留于下文，作为历史。
> **v0.3.13 更新**：Suspended-parent nested sequence stack。协议 `experiments/validation/v0.3.13/protocol.json`。候选冻结 `experiments/frozen/ghost-nested-stack-guard-v0.3.13/`。**Outcome C — harmful / unsafe**：CRM @120 guard 5 states / 80 lost_parent → stack 5 states / 5 URLs / 80 pushes / 0 resumes / depth 80 / 0 horizon / 0 return。Ops @120 guard 5 states / 79 lost_parent → stack 5 states / 5 URLs / 79 pushes / 0 resumes / depth 79。P1–P15、S1–S7、5800 exhaustive traces 均为 0 failures，terminal violations 为 0。BuggyDesk stack 确认 K3/K5/K6/K9/K10，相对 guard 丢失 K1/K2。DeepBench 确认 D6/D12，丢失 D7/D11/D13/D14。Wiki 丢失 W2。BuggyShop 保留 W5/W6/W9/W10。v0.3.12 仍是 Outcome C，v0.3.11 仍是 Outcome D。不是 fresh validation。候选不晋升。产品默认不切。`python -m benchmark.nested_stack_reproduce --root experiments/published/nested-stack-v0.3.13 --verify`
> **v0.3.12 更新**：Nested-hub parent preservation。协议 `experiments/validation/v0.3.12/protocol.json`。候选冻结 `experiments/frozen/ghost-nested-hub-guard-v0.3.12/`。**Outcome C — harmful/regression**：CRM @120 guard 5 states / 80 lost_parent / 0 return → candidate 20 states / 13 URLs / 0 lost_parent / 5 nested follow-up / 8 horizon / 14 return attempts / 2 escapes。Ops @120 guard 5 states / 79 lost_parent / 0 return → candidate 28 states / 24 URLs / 0 lost_parent / 18 follow-up / 21 horizon / 30 return attempts / 7 escapes。N1–N12、S1–S7、5800 exhaustive traces 均为 0 failures。回归丢失 BuggyDesk `BUG-K3,BUG-K6,BUG-K9,BUG-K10` 与 DeepBench `BUG-D12`。Wiki `BUG-W2` 与 BuggyShop `W5,W6,W9,W10` 未丢。CRM / Ops 是已分析机制用例，不是 fresh-generalization。候选不晋升。产品默认不切。`python -m benchmark.nested_hub_reproduce --root experiments/published/nested-hub-parent-v0.3.12 --verify`
> **v0.3.11 更新**：Preregistered multi-target replication。协议 `experiments/validation/v0.3.11/protocol.json`。冻结 suite `experiments/frozen/v0.3.11-multitarget/`。**Outcome D — inconclusive suite**：仅 `buggy-wiki` 可评估（C1 1 opportunity / 6 states / 116 return attempts；guard 2 L1 escapes / 23 states / 16 URLs / 成功返回 19；post-escape novel states 15）。`buggy-crm` 与 `buggy-ops` 的 C1/guard 均 5 states、0 return attempts、0 escapes。S1–S7 与 5800 exhaustive traces 0 failures。C1 bugs lost []。promotion `not_ready`。产品默认不切。预算不追加。不是广泛泛化。`python -m benchmark.multi_target_reproduce --root experiments/published/multi-target-replication-v0.3.11 --verify`
> **v0.3.10 更新**：Fresh cross-app transfer。协议 `experiments/validation/v0.3.10/protocol.json`。目标 BuggyDesk（冻结 `experiments/frozen/buggy-desk-v0.3.10/`）。**Outcome A**：C1@120 1 次 evaluable opportunity、6 states / 6 URLs / 116 return attempts；guard 7 escapes、35 states / 19 URLs、逃出后新状态 27；S1–S7 全过；C1 confirmed 丢失 []。BFS@120 确认 5 个 bug（含 K4），guard 确认 7 个。产品默认不切。不是广泛泛化。`python -m benchmark.fresh_transfer_reproduce --root experiments/published/fresh-transfer-v0.3.10 --verify`
> **v0.3.9 更新**：Return-cycle guard（isolated module）。Outcome **A**：Shop lock 被 escape（4 events, 22 states/8 URLs），DeepBench @120 与 C1 相同（D6/D7/D11–D14, depth 4, 0 escapes）。产品默认不切。无泛化声明。`python -m benchmark.return_cycle_guard_reproduce --root experiments/published/return-cycle-guard-v0.3.9 --verify`
> **v0.3.8 更新**：application-shape 诊断 + evidence hardening。Shop 6-state = nested hub + return lock（returned terminal=0，旧 return_success=2 实为 branch_start）。H1 = step-0 reach。H2 = 全局、非 oracle-blind。Clean-clone：`python -m benchmark.application_shape_reproduce --root experiments/published/application-shape-v0.3.8 --verify`。算法未改。
> **v0.3.7 更新**：算法冻结后做 holdout + BuggyShop。C1 holdout **0/2**，BuggyShop **1/10** 且 6 states。预注册结论 **C：DeepBench-specific**。产品默认不切。不要用 holdout 调参。
> **v0.3.6 更新**：Structural hub memory（cluster-level）。C1 `ghost-structural-memory`@80–120 Deep-BDR=0.667（D6/D7/D11–D14），BDR=0.429 并列 DFS。C0 仍 D6+D12。产品默认不切。Freeze `5355abd`。
> **v0.3.5.1-r2 更新**：sequence length 按 concrete `sequence_action` 计；horizon 不是 terminal。max len=6；terminally tested branches=6。行为仍 D6+D12。
> **v0.3.5.1 更新**：Sequence metrics 纠偏。行为不变（仍 D6+D12）。`hub_count=57` 是 variant；canonical hub=3。下一问：跨 semantic variant 的 workflow memory。
> **v0.3.5 更新**：Sequence-aware branches。`ghost-sequence` 首次确认 D12，Deep-BDR=0.222，D6 仍在。产品默认仍是 NoFrontier。Freeze `5355abd`。
> **v0.3.4 更新**：Post-reach exploration。产品 Ghost 默认 NoFrontier。`ghost-deferred`@120 与 DFS BDR 打平且保留 D6；full exploit/postreach 会丢 D6。Freeze `5355abd`。
> **v0.3.3 更新**：Frontier relocation study。inventory-sum + 双计 path cost 导致 over-jump；Shadow 证明 step 6 的 hop 会打断 D6。默认应关闭 reset+replay。Freeze 仍是 `5355abd`。产品 v0.4 preview 未改。
> **v0.3.2 更新**：Episode-aware replay。`RunResult.reproduction_actions(finding)` 只返回当前 reset episode。v0.3.1 Ghost-full confirmed-BDR=0 被证明是测量错误。DeepBench freeze 仍是 `5355abd`。
> **v0.3.1 更新**：Exploration Repair。DeepBench freeze 仍是 `5355abd`。算法 HEAD 见 git。
> Graph 分类是 exact `state_id` / same cluster / new cluster。`state_similarity()` 的 Jaccard 与 aHash **没有**完整进入 graph classification。

**v0.3.1 实测（不可粉饰）**：WorkflowBFS 与 Ghost-noFrontier 能在 budget 40 到达 project 并确认 D6（Deep-BDR=0.111）。Ghost-full 带 opportunity-cost relocate 的 **confirmed-BDR=0 已被 v0.3.2 erratum supersede**（reset-blind replay）。reachability / restore_ratio 仍有效。见 `experiments/published/deepbench-v0.3.1/summary.md` 尾部 Erratum。

> **v0.3 更新（2026-09-19）**：Algorithm Proof 已落地。代码与实验以当前 git 为准。

## v0.3 现状（覆盖交接时的 PARTIAL 清单）

已修复 / 已实现：

- Navigation history：只在真实 URL 变化时入栈（`ghostqa/executor/nav.py`）
- 两层状态：`cluster_id` + `variant_key` → `state_id`；similarity 进入 Graph/Explorer
- FrontierPlanner + reset/replay；GhostPolicy v1.2
- DeepBench = BuggyFlow，freeze SHA `5355abd`
- spec_brief = id + desc + when；LLM cache key = 精确 state_id

**实验结果（不可粉饰）**：DeepBench 上 Ghost-full **没有**赢 BFS/DFS。Deep-BDR 全员为 0（budget≤120）。Frontier relocate 消融为负贡献（Ghost-noFrontier 更好）。详见 `experiments/published/deepbench-v0.3/summary.md`。

P0-2 里“Time-to-Deep-Bug 应显著优于 BFS”是 **research hypothesis**，不是工程验收门。假设未成立。

v0.4 不要做 Dashboard 直到先处理：input vocab 基数、relocate 与表单未试动作的冲突、以及冻结 DeepBench 上的重跑。

真实 LLM：`real LLM experiment skipped: credentials unavailable`。

---

# GhostQA 技术交接文档（v0.2 → Grok 4.6，历史）

> **这是 v0.2 交接原文。**
> 编写时间：2026-09-19 · 编写时 HEAD：`9c6c0a0`（v0.2，已推送 main）
> 编写原则：代码是最终事实来源。本文所有状态判断都在编写时重新用代码验证过。

---

## 1. Project North Star

**GhostQA 是一个 AI 驱动的自主探索式软件测试系统**：给定一个 Web 应用和需求规格，它自主建立软件状态模型、智能选择测试路径、发现异常，并把每个异常转化为**经过机器重放验证、带可执行最小复现路径**的可信缺陷报告。

核心技术主线（不要说"第一个会自动测试网页的 AI"——竞品已有 Momentic/QA.tech）：

```
Value-Guided Exploration        状态价值函数引导的探索（透明、可测、可消融）
+ Specification-Driven Oracle   需求规格 → 行为断言的语义 Oracle
+ Bug-Specific Replay Verify    BugFingerprint 级重放确认（过滤幻觉/误报）
+ Executable Minimal Repro      三态谓词 + ddmin 的可执行最小复现
+ Reproducible Benchmark        开放 GhostBench、基线对比、多种子统计
```

**核心研究命题**（当前未证毕，是 v0.3 的目标）：
> 在存在深状态、前置依赖、干扰分支与稀疏 Bug 的环境下，价值引导探索是否比系统性遍历（BFS/DFS）更快、更省地找到高价值缺陷？

v0.2 已证明的是**工程闭环成立**（真实浏览器全链路）；**算法优势尚未证明**（详见 §6）。

---

## 2. Current Truth Snapshot

- **Commit**：`9c6c0a07e0a0edd906e2db72b9074b37b6006ed1`（main，工作区干净）
- **测试**：41 项单测（Sim，<1s）+ 9 项集成测试（真实 Chromium，~3min）——**全部通过**（交接前刚复跑）
- **无已知失败测试、无未提交文件**

### IMPLEMENTED（代码+测试真实存在）
- 状态模型/结构签名/相似度函数/StateGraph（`ghostqa/state/`）
- Executor 抽象 + SimExecutor（确定性模拟）+ PlaywrightWebExecutor（真实浏览器）
- 5 种探索策略：Monkey/DFS/BFS/LLM-naive/GhostPolicy v1.1（门控 LLM 调用）
- 三层 Oracle：L1（crash/js_error/http_error/blank）、L2（dead_action 含幂等过滤/nav_loop）、L3（规格断言 DSL，obs/obs_sum/数值强转）
- BugFingerprint（`oracle/fingerprint.py`）贯穿 Discovery/Dedup/Replay/Manifest/Report
- 三态重放验证（PASS/FAIL/INVALID）+ ddmin 可执行最小化
- ModelGateway：Mock/Null/OpenAI 兼容（超时/重试/缓存/降级回退/token与延迟统计）
- CLI `python -m ghostqa run` + JSON/HTML 报告
- BuggyShop（`apps/buggy-shop/`：11 页、10 个埋入 bug、spec.json、manifest）
- SimBench（`benchmark/runner.py`）+ WebBench（`benchmark/web_runner.py`）
- pyproject.toml、GitHub Actions CI（unit + integration 双 job）
- 已发布证据：`experiments/published/webbench-v0.2/`

### PARTIAL（存在但有明确缺口——详见 §5）
- 状态模型只有**结构签名**，不感知业务状态（购物车有/无货同签名）
- `state/similarity.py` 有实现有单测，但**未被任何生产代码调用**
- GhostPolicy 只做**当前页面局部选动作**，无全局 frontier 规划
- `_nav_stack` 在非导航点击时也入栈（correctness debt）
- `spec_brief` 只传 assertion id，LLM 拿不到语义描述
- `_semantic_cache` 按结构签名缓存，业务状态变体间会错误复用

### NOT IMPLEMENTED
Dashboard、Android、真实 LLM 实验（Gateway 就绪但无 API key 未跑）、DeepBench、多 Agent、微调、RAG/知识图谱（均刻意未做）

### 已知指标（可追溯）
- SimBench v0.1（本地 `experiments/runs/2026-09-18-v0.1-first/`）：Ghost-noLLM 0.71 > Monkey/DFS/BFS 0.57 > LLM-naive 0.14
- WebBench v0.2（`experiments/published/webbench-v0.2/`）：BFS=Ghost-full=0.30，Ghost time-to-first-bug=1 最快，Ghost-noLLM=0.10

---

## 3. Architecture Map

```
被测 Web App (BuggyShop / 任意 URL)
   │  ↑
   │  │ observe()/execute(Action)          ghostqa/executor/playwright_web.py
   ▼  │                                  （Sim: ghostqa/executor/sim.py）
GUIState (url/title/elements/obs/meta)     ghostqa/state/models.py
   │  state_signature()                    ghostqa/state/signature.py（结构签名，无 obs）
   ▼
StateGraph（节点=签名，边=动作，计数/标记）  ghostqa/state/graph.py
   ▲
Explorer 主循环                            ghostqa/exploration/explorer.py
   │  candidates = available_actions()     ghostqa/executor/base.py
   │  action = policy.select(graph,state,candidates,ctx)
   ▼
GhostPolicy v1.1                           ghostqa/exploration/policy.py
   │  fast path: 程序分(Novelty/UCB/Risk/Rep/Cost)
   │  slow path: 门控(Uncertainty/NovelState/Stuck/SpecRelevance)→LLM重排top-k
   ▼
OracleEngine.inspect()                     ghostqa/oracle/engine.py
   │  L1 硬异常 / L2 结构异常(幂等过滤) / L3 规格断言(oracle/spec.py)
   ▼
Finding → BugFingerprint                   ghostqa/oracle/fingerprint.py
   │  （Explorer 内按 fingerprint 去重）
   ▼
ReplayValidator（三态）                     ghostqa/replay/validator.py
   │  PASS→确认 / FAIL→丢弃 / INVALID→序列不可执行
   ▼
ddmin（只对 PASS 序列保留）                 ghostqa/minimizer/ddmin.py
   ▼
Report JSON/HTML                           ghostqa/report/generator.py
Benchmark Judge（独立读 manifest，绝不被 Agent 读）  benchmark/runner.py, web_runner.py
```

**关键数据流**：观察→签名→选动作→执行→Oracle→候选 Finding→（探索结束）逐个重放验证→确认者做 ddmin→报告。`obs` 是 Oracle 的唯一业务数据来源；`ground_truth()` 在真实 Web 上恒为 `{}`（设计如此）。

---

## 4. Non-Negotiable Invariants（下一任 Agent 不得破坏）

1. **Tester / Benchmark Judge 隔离**：GhostQA 探索与 Oracle 期间绝不读取 `bugs.manifest.json`、seed bug id、被测应用内部状态。真实 Web 上 `ground_truth()` 必须保持返回 `{}`。Benchmark 评测代码（runner）可以读 manifest——只有它可以。
2. **Verified > Generated**：任何 Finding 必须经过 Replay + Fingerprint 匹配才能叫 Confirmed Bug 进入报告。候选直接进报告 = 项目失信。
3. **不得为了让 Ghost 赢而改 benchmark**：benchmark 变更必须独立合理化并记录原因（见 §9 freeze 规则）。
4. **Negative Results 必须保留**：BFS 与 Ghost 打平、Ghost-noLLM 落后、Sim 上 MockLLM 负收益——这些是资产，删除即学术不端。
5. **不伪造数据**：README/文档/PPT 中的每个实验数字必须能追溯到 `experiments/published/` 的具体 run。真实 LLM 无 key 就标 "not run"，绝不拿 MockLLM 冒充。
6. **Working > Fancy**：每个新增 AI 模块必须回答"它让 Bug Discovery / Coverage / Oracle Accuracy / Reproduction Success 中哪个指标变好了"，答不上就不做。

---

## 5. 当前最重要的技术债（已逐项从代码验证）

### A. Semantic State Problem（最关键）
`state/signature.py:18-29`：签名 = normalize(url) + title + 排序后的 (role, text)。**不含 obs、不含业务状态。**
后果（已确认）：购物车有货/无货、库存 2/0、登录前/后——只要可交互元素集合相同，**就是同一个 state**。这意味着：
- 状态依赖型 bug（如"空购物车支付崩溃"）在图上不可建模其前置状态；
- UCB/Novelty 把"同一页面的不同业务变体"当作已探索，可能跳过关键路径；
- 深度 workflow（多步表单）的中间步骤塌缩成一个节点。
**但**不能简单把全部文本/obs 塞进签名（时间戳/计数器/动态内容会 state explosion）。
**建议方向**：两层模型——`StructuralState`（现状签名）+ `BusinessVariant`（仅来自 `data-obs`/白名单关键值的变体键）。变体键来源必须由应用方显式声明（如 data-obs 属性），而非全量文本。可考虑 StateCluster：同结构不同变体归簇，簇内计数、簇间建边。

### B. State Similarity 未接入（文档不得声称已聚类）
`state/similarity.py` 的 `state_similarity()`（IDENTICAL/SIMILAR/NEW）只被 `tests/test_state.py` 使用。**StateGraph、Explorer、GhostPolicy 均未调用。** 当前去重仅靠签名精确相等。v0.3 做 StateCluster 时把它真正接入，或明确删除以免误导。

### C. 无 Global Frontier Planning（算法主线缺口）
`GhostPolicy.select()` 只在**当前状态的候选动作**中评分。没有：全图 frontier 发现、目标状态选择、路径规划/重放。后果：Agent 陷入已探索区域时只能 `back` 逐层退，无法"reset → 沿已知最短路径直达高价值 frontier"。
**这是 GhostPolicy v1.2/v2 的核心升级**：Frontier Discovery（图中有未试动作的节点）→ Target Selection（全局价值分）→ Path Planning（BFS 最短路 on StateGraph）→ 到达后局部选动作。架构上 StateGraph 已有全部边数据，只差 planner。

### D. _nav_stack 污染（correctness debt）
`executor/playwright_web.py:268`：每次 click 都 `self._nav_stack.append(url_before)`，无论是否真的发生导航。`back` 因而可能"返回"到当前 URL（重载同页）。**正确行为**：仅在 `page.url` 实际变化时入栈，或直接用浏览器 history（`page.go_back()`）。

### E. spec_brief 只传 assertion id
`__main__.py:70`、`web_runner.py:64`：`"; ".join(a["id"] for a in spec)` → LLM 只看到 `cart_total_consistent; stock_non_negative`，没有 desc/when 语义。**升级**：传 `id + desc + when`（估算每条约 20-30 tokens，10 条约 300 tokens，可接受；超量时按当前页面相关性过滤）。

### F. _semantic_cache 按结构签名缓存
`policy.py:181,186`：同签名即复用 LLM 分数。叠加问题 A——"购物车有货/无货"同签名 → 语义分错误复用。与 A 一并解决（变体键入缓存 key），不要单独打补丁。

---

## 6. 当前最大实验问题（v0.3 的核心科学问题）

WebBench v0.2：Ghost-full = BFS = 0.30。**这不是失败也不是胜利**，它说明 BuggyShop 的状态空间太小太浅（所有页面距首页 1-2 hop，40 步预算 BFS 近乎穷举）。在小而浅的空间，系统性遍历就是最优，智能引导没有发挥空间。
v0.3 必须回答：
> 在**深状态、前置依赖、干扰分支、稀疏 Bug**的环境下，Value-Guided Exploration 是否比 BFS 更快找到高价值缺陷？
这要求：(a) 有区分度的 DeepBench（§8）；(b) 正确的实验方法（§10）；(c) 算法升级到全局规划（§5C）。

---

## 7. GhostQA v0.3 规划 — Algorithm Proof

**目标**：证明（或证伪）状态空间智能探索的算法价值。不做产品 UI。

1. **Semantic State / StateCluster**：两层状态模型（§5A），结构签名 + 显式业务变体键；similarity 真正接入去重与 Novelty 计算。
2. **Frontier Planner**：全局 frontier 发现 + 目标选择 + 图上最短路径重放（§5C）。
3. **GhostPolicy v1.2**：局部评分（现状）+ 全局规划（新增）分层；LLM 门控保留，spec_brief 升级（§5E），缓存键含变体（§5F）。
4. **DeepBench**：见 §8。
5. **实验方法**：见 §10——Discovery@Budget 曲线 + Bug-by-Depth 是关键新证据。
6. **Real LLM Evaluation**：见 §11。

允许推翻的现状：GhostPolicy 内部实现可大改；Executor/Oracle/Fingerprint/Replay/ddmin 接口稳定，不建议动。

---

## 8. DeepBench 设计（第二个 Web benchmark）

**不是"BuggyShop 加页面"，而是为"深度"而生的应用。** 建议题材：订单管理后台（列表→详情→编辑→审核→支付→退款多步流）或项目管理系统。

硬性要求：
- **20-40 个有意义状态**（不是页面数），多层路径深度 1-7；
- **12-16 个埋入 bug**，按触发深度分层：浅层（1-2 步）3-4 个、中层（3-4 步）4-6 个、深层（5-7 步）4-6 个；
- **前置依赖型 bug ≥ 4 个**（如"先将用户设为 VIP → 再在订单页出现折扣计算错误"；"空购物车+已登录 → 支付崩溃"）；
- **诱饵分支**：大片无 bug 但元素丰富的区域（帮助文档/设置页），用于惩罚无引导的遍历；
- **多步表单**（3-5 步，中间状态有校验）；
- 复用 BuggyShop 的全部机制：data-testid、data-obs、localStorage 状态、stdlib server、spec.json、bugs.manifest.json。

**关键指标**（不是页面数量）：Bug Trigger Depth、Prerequisite Complexity（触发前置动作数）、Branching Factor、Reachability（BFS 在预算内可达比例）。

## 9. 防止 Benchmark Overfitting

- DeepBench 分为 **Development set**（调参可见）与 **Holdout set**（最终评估才用，manifest 单独存放）。
- 调 GhostPolicy v1.2 之前 **freeze DeepBench manifest**（bug 位置/触发深度/分支结构）。freeze 后修改 benchmark 必须在 commit message 说明与算法调优无关的理由。
- 权重调参只允许在 Development set 上进行；报告数字只出 Holdout。

## 10. 新实验体系规划

- **策略**：Monkey / DFS / BFS / LLM-naive / Ghost-noLLM / Ghost-full，加消融 **Ghost-noSemantic / Ghost-noFrontier / Ghost-noCluster**。
- **Budget**：20 / 40 / 80 / 120（画 Discovery@Budget 曲线）。
- **Seeds**：随机策略 ≥10 个 seed，报告 mean±std + min/max。
- **指标**：Confirmed Bug Discovery Rate、**Deep Bug Discovery Rate（depth≥4）**、Discovery 曲线 AUC、Time to First Bug、**Time to Deep Bug**、State/Cluster Coverage、Repeat Rate、Replay Success、Repro Compression、LLM Calls/Tokens/Latency、Cost per Confirmed Bug。
- **核心新图表**：Bug Discovery × Trigger Depth 分组柱状图——直接回答"智能策略是不是只更快点到首页旁边的 bug"。

## 11. 真实 LLM 计划

- Gateway 已就绪：`GHOSTQA_MODEL_BASE_URL/API_KEY/NAME`（OpenAI 兼容）。无 key → 标记 "not run"，绝不伪造。
- 三组对比：**Real LLM vs MockLLM vs NoLLM**，同一 benchmark、同 budget、同 seeds。
- 记录 token/latency/成本；真实 LLM 成本计入 Cost per Confirmed Bug。
- 建议首个模型：DeepSeek-V3 或 Qwen-Plus（成本低、中文场景匹配）。

## 12. v0.4 规划 — Product & Competition Demo（v0.3 稳定后再开始）

FastAPI 后端、Live Dashboard（浏览器画面流 + State Graph 实时生长 + Decision Summary 面板 + Bug 时间线 + Replay 动画 + Benchmark 图表）。**Dashboard 只是真实能力的展示层，不是新主线。** 技术约束：数据源必须全部来自现有 trace/graph/findings 落盘文件，不为 UI 改算法。

## 13. v0.5 规划 — Competition Hardening

- 2-3 个真实开源 Web 项目（非埋 bug）验证泛化性，如实记录检出/漏检；
- Failure Corpus 正式化（误报/漏报/回放失败分类 → 回归测试）；
- 演示稳定性：全离线 demo 环境 + 录屏兜底 + 评委现场出题预案；
- 性能优化（动作延迟、并行 replay）；
- 最终 benchmark 大图 + 消融总表；
- 技术方案书（按 AIC 大纲：产品概述/技术架构/功能实现/测试部署/应用价值）、3 分钟 demo 脚本、演示视频、PPT。

---

## 14. 优先级任务清单（可直接开发）

### P0-1 两层状态模型（StateCluster）
- 为什么：§5A/B/F 三个技术债的共同根因；不解决则深层 bug 不可建模。
- 涉及文件：`ghostqa/state/signature.py`（新增 variant 键）、`ghostqa/state/models.py`、`ghostqa/state/graph.py`（簇结构）、`ghostqa/state/similarity.py`（接入或删除）、`executor/playwright_web.py`（obs 白名单提取）。
- 输入：GUIState.obs（data-obs 白名单）；输出：state = (struct_sig, variant_key)，Graph 支持簇。
- 验收：购物车有/无货为不同变体但同簇；带时间戳动态文本不产生新变体；全部现有测试通过 + 新单测 ≥6。
- 依赖：无。风险：变体键设计过粗/过细——先做白名单制，禁止全量文本入键。

### P0-2 Frontier Planner + GhostPolicy v1.2
- 为什么：§5C，算法主线缺口；DeepBench 上战胜 BFS 的前提。
- 涉及文件：`ghostqa/exploration/planner.py`（新建）、`policy.py`、`explorer.py`、`state/graph.py`（最短路）。
- 输入：StateGraph（含未试动作的节点）；输出：目标 frontier + 到达动作序列。
- 验收：构造 Sim 深链 App（depth≥5，bug 在末端），v1.2 的 Time-to-Deep-Bug 显著小于 BFS（≥10 seeds）；reset+replay 路径正确执行；现有测试不回归。
- 依赖：P0-1。风险：图上最短路在签名合并后可能不存在（变体切换），需 fallback 到 back 链。

### P0-3 DeepBench 应用 + freeze
- 为什么：§6/§8，没有它 v0.3 无法证伪。
- 涉及文件：`apps/deep-bench/`（新建，复用 BuggyShop 机制）、`benchmark/web_runner.py`（支持多 app）。
- 验收：12-16 bugs、depth 1-7 分层、≥4 前置依赖 bug、诱饵分支；manifest+spec 完整；BFS@budget40 的 reachability < 60%（否则不够深）；freeze commit 单独打 tag。
- 依赖：无（可与 P0-1 并行）。风险：应用做太大——先状态图设计评审再写代码。

### P1-1 实验体系升级（多 budget × ≥10 seeds × by-depth 指标）
- 涉及文件：`benchmark/web_runner.py`（by-depth 聚合、曲线数据）、`experiments/published/`。
- 验收：输出 Discovery@Budget 曲线数据 + by-depth 分组表；统计字段完整。
- 依赖：P0-3。风险：真实浏览器实验耗时——budget 大时用 `--skip-minimize` 矩阵 + 单独补 minimize。

### P1-2 spec_brief 语义化 + LLM 缓存修复
- 涉及文件：`__main__.py`、`web_runner.py`、`runner.py`（spec_brief 传 id+desc+when）、`policy.py`（缓存键含 variant）。
- 验收：token 增量 < 400/run；真实 LLM 复跑三组对比（Real/Mock/No）。
- 依赖：P0-1（缓存键）。风险：无 key 时只更新代码并标记实验 not run。

### P1-3 _nav_stack 修正
- 涉及文件：`executor/playwright_web.py`（仅 url 变化时入栈或改用 go_back）。
- 验收：非导航点击后 back 不重载当前页；集成测试通过。
- 依赖：无。风险：go_back 对 hash/SPA 路由语义不同——保持显式栈更可控。

### P2-1 DeepBench 全实验 + 论文级图表
- 依赖：P0-2、P0-3、P1-1。产出 `experiments/published/deepbench-v0.3/`。

### P2-2 Failure Corpus 机制
- 误报/漏报/回放失败自动归类落盘 → 回归测试集。依赖：P2-1。

### P3-1 v0.4 Dashboard（仅展示层）
### P3-2 真实开源项目泛化验证

---

## 15. Do Not Do（红线）

1. 不要先做 Dashboard / Android / 任何 UI——v0.3 是算法证明。
2. 不要重写架构或换技术栈（除非有数据证明现架构是瓶颈）。
3. 不要删负结果、不要改 benchmark 迁就 Ghost。
4. 不要在探索/Oracle 中读 manifest 或应用内部状态。
5. 不要引入多 Agent / RAG / 知识图谱 / 微调——除非先证明单 Agent 价值函数到顶。
6. 不要做没有指标贡献的功能（先答"改善哪个指标"）。
7. 不要把设计文档写成已实现；状态判断以代码为准。
8. 不要拿 MockLLM 数据冒充真实 LLM 实验。

---

## 16. Handoff Runbook

```bash
git clone https://github.com/NineSense9/GhostQA.git
cd GhostQA
python -m venv .venv
# Windows: .venv/Scripts/activate    Linux: source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium

pytest -m "not integration"     # 41 项单测，<1s
pytest -m integration           # 9 项真实浏览器测试，~3min

# BuggyShop（被测应用）
python apps/buggy-shop/server.py 3939        # http://127.0.0.1:3939

# CLI 端到端（探索→验证→最小化→报告）
python -m ghostqa run --url http://127.0.0.1:3939 \
  --policy ghost --budget 60 --spec apps/buggy-shop/spec.json --out runs/demo

# WebBench 基线实验（5策略×2种子）
python -m benchmark.web_runner --budget 40 --seeds 1,2 \
  --skip-minimize --out experiments/published/webbench-v0.2

# SimBench（算法快速迭代，秒级）
python -m benchmark.runner --budget 120 --seed 42 --out experiments/runs/sim
```

- published 证据：`experiments/published/webbench-v0.2/`（config/metrics/summary）
- 本地大 run 目录 `experiments/runs/` 已 gitignore。
- 真实 LLM（可选）：`GHOSTQA_MODEL_BASE_URL` / `GHOSTQA_MODEL_API_KEY` / `GHOSTQA_MODEL_NAME`。

---

## 17. 最终交接状态

| 项 | 值 |
|---|---|
| Repository | https://github.com/NineSense9/GhostQA |
| Branch | main |
| Latest SHA（交接时） | `9c6c0a07e0a0edd906e2db72b9074b37b6006ed1`（本文档提交后见 git log） |
| Test status | 41 unit + 9 integration，全绿（2026-09-19 复跑） |
| Known failing tests | 无 |
| Uncommitted files | 无 |
| Required env vars | 无（全部可离线运行） |
| Optional env vars | `GHOSTQA_MODEL_BASE_URL` / `GHOSTQA_MODEL_API_KEY` / `GHOSTQA_MODEL_NAME` |
| Current benchmark | WebBench v0.2（BuggyShop，published） |
| Next milestone | **v0.3 Algorithm Proof**：P0-1 两层状态模型 → P0-2 Frontier Planner → P0-3 DeepBench → 全因子实验 |

---

*祝施工顺利。地基是实的，图纸在上面，别急着盖第四层——先证明第二层撑得住。*
