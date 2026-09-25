# GhostQA — AI 驱动的自主探索式软件测试系统

> Monkey 有手无脑，脚本测试有人脑无手。GhostQA 是**有脑、有手、有判据、还自证清白**的测试员。

给定一个 Web 应用与需求规格，GhostQA 在无人干预下：自主建立软件状态模型（State Graph）→ 用状态价值函数选择高价值测试路径 → 用三层 Oracle 判断异常（硬异常/结构异常/需求语义异常）→ 对每个候选 Bug 按 **BugFingerprint** 重放验证 → 用 **ddmin** 自动最小化复现路径 → 交付带证据的可信缺陷报告。

## 当前状态：v0.4 preview（Dashboard）· 最新研究轮次 v0.3.25 Outcome C

产品默认策略仍是 **NoFrontier + `sequence_mode=off`**。v0.3.24 没有改产品默认。Dashboard 展示层读取已提交的 `experiments/published/` 产物。

**v0.3.25 Outcome C — fresh validation failed the Guard-preservation gate.** 冻结的 v0.3.24 候选在 clinic、dispatch、archive、fleet 四个新正例上都到达了嵌套交接和本地 drain，但每个都比 Guard 少确认了分数不一致缺陷（CL12、DP12、AR12、FL12）。shelf 和 counter 没有嵌套交接，历史回归没有丢 Guard 缺陷。产品默认未改，候选不晋升。v0.3.24 在已检查用例上仍是 Outcome A。`python -m benchmark.fresh_transfer_v0325_reproduce --root experiments/published/fresh-transfer-v0.3.25 --verify`

**v0.3.24 Outcome A — inspected repair.** 同页 local drain 的去重标记改成浏览器 episode 记忆。debt relocation 的 `executor.reset` 会清掉同页 mutation，因此只失效旧 episode 的同页 key；跨页 child、sequence、debt 和结构记忆仍是 run-scoped。Campus 和 Studio @120 各前进 1 个 episode，重新探测同页按钮，模板 5/8/9 都在。Warehouse 和 Booking 的 episode 前进次数是 0，模板 5/8/9 保留。Catalog、Kiosk 和 DeepBench 的 episode 前进次数是 0。这是已检查修复，不是 fresh validation，也不是晋升。v0.3.23 仍是 Outcome B，v0.3.22 的诊断仍是 `persistent_post_terminal_sink`，v0.3.21 仍是 Outcome C。`python -m benchmark.episode_drain_epoch_reproduce --root experiments/published/episode-drain-epoch-v0.3.24 --verify`

**v0.3.23 Outcome B — safe partial repair.** Residual Frontier Debt Escape 在 Campus 和 Studio 上各把最老的 waypoint debt 从闭合且交互耗尽的 SCC 回放到已知路径。随后的普通动作消耗了记录的 residual token，模板 5 和 8 收回，模板 9 仍缺（BUG-CP9、BUG-ST9）。Warehouse 和 Booking 的债务在原组件里被普通动作消耗，回放次数为 0，模板 5/8/9 保留。Catalog 和 Kiosk 没有债务、没有回放。这是已检查修复，不是 fresh validation，也不是晋升。v0.3.22 的诊断仍是 `persistent_post_terminal_sink`，v0.3.21 仍是 Outcome C。`python -m benchmark.residual_frontier_debt_reproduce --root experiments/published/residual-frontier-debt-v0.3.23 --verify`

**v0.3.22 Diagnostic — persistent_post_terminal_sink.** 这轮没有改策略，只分析 v0.3.21 的分裂。Campus/Studio 在 sequence-scoped return cycle 已经被正确 abandon 之后，普通探索仍停在一个静态闭合的导航分量里；到 b480 仍没有重新执行原 entity residual frontier，模板 5/8/9 仍丢失。Warehouse/Booking 的同一分量包含回到 entity 的边，Guard 模板保持恢复。这是已检查目标上的 failure diagnosis，不是新修复，不是无限循环证明，也不是 fresh validation。`python -m benchmark.post_escape_sink_reproduce --root experiments/published/post-escape-sink-v0.3.22 --verify`

**v0.3.21 Outcome C — unsafe, harmful, or protocol-invalid.** 这是对已检查的 v0.3.20 目标做的 Return-Waypoint Frontier Escape 检修，不是新的 fresh 验证。四个 positive 都在 step 21 放弃了交接恢复后的外层返回，下一次动作由原探索策略选择 `open_side`。Warehouse 和 Booking 收回了 Guard 的模板 5/8/9。Campus 和 Studio 仍丢失这三类。四个目标还少了 v0.3.20 F 曾经确认、但 Guard 集合之外的空白页缺陷。历史回归、catalog/kiosk 对照和安全计数保持。promotion readiness 为 `not_ready`。下一问是失败分析，不是继续调这四个目标，也不是改默认策略。`python -m benchmark.return_waypoint_frontier_reproduce --root experiments/published/return-waypoint-frontier-v0.3.21 --verify`

**v0.3.20 Outcome C 仍保留。** 冻结的 v0.3.19 组合策略在 4 个新 positive target 上都走到了 nested handoff 和 finding-gated Return-Entry Drain，但都丢失了 Guard 已确认的缺陷。`python -m benchmark.fresh_composite_reproduce --root experiments/published/fresh-composite-v0.3.20 --verify`

**v0.3.19 Outcome A — inspected trigger repair.** Return-Entry Drain 只在同一步新出现 `sequence_terminal` outcome `finding`，并且这条 sequence 从 returning false 变成 true 时才启动。普通 `sequence_horizon_reached` 回到 v0.3.17 的返回。buggy-lab @120 仍在结果页按稳定顺序点 `btn_close` 然后 `btn_reopen`，BUG-L9 在第 18 步确认，Guard 的 L1、L2、L8、L9、L10 都保留。DeepBench @120 没有 horizon drain，states 26、URLs 8、return_success 37，Guard 的 D6、D7、D11、D12、D13、D14 都保留。目录 handoff 仍是 0。forum 与 billing 的 strict full transfer 都为 true。CRM 27/16，Ops 34/25。Desk、Wiki、BuggyShop 相对 guard 没有丢失。这是已检查的触发收窄，不是 fresh 验证，也不是晋升。下一轮必须是新的 fresh-validation。`python -m benchmark.finding_return_entry_reproduce --root experiments/published/finding-return-entry-v0.3.19 --verify`

**v0.3.18 Outcome C — unsafe / harmful / protocol-invalid.** 返回阶段从 false 变成 true 时，若当前 hub 还有没排空的 button，先各点一次，再继续原来的返回。buggy-lab @120 在结果页开始了 return-entry drain，按稳定顺序点了 `btn_close` 然后 `btn_reopen`，BUG-L9 在第 18 步确认。Lab 保住 L1、L2、L8、L9、L10。目录 @120 handoff 仍是 0。forum 与 billing 的 strict full transfer 都为 true。CRM 28/16，Ops 34/25。Desk、Wiki、BuggyShop 相对 guard 没有新的丢失。DeepBench @120 只确认了 BUG-D8，相对 guard 丢失 BUG-D6、BUG-D7、BUG-D11、BUG-D12、BUG-D13、BUG-D14，所以这轮是 Outcome C。机制本身在结果页接上了，但按预注册顺序 C 先于 A。这不是新的 fresh 验证，也不是晋升，本轮不再改候选。`python -m benchmark.return_entry_drain_reproduce --root experiments/published/return-entry-drain-v0.3.18 --verify`

**v0.3.17 Outcome B — partial safe repair.** 子分支回到父 hub 后，先把当前可见的 button 各点一次，再把剩余结构分支交给 v0.3.16 的一格租约。buggy-lab @120 在 run 父页面先点了 `btn_staff_note` 和 `btn_cool`，然后才租约 `open_result_from_run`。BUG-L10 在第 15 步确认，BUG-L8 在第 14 步确认，BUG-L1 在第 61 步的 `/samples.html` 出现。结果页没有开始 local drain，`btn_close` / `btn_reopen` 没有执行，BUG-L9 仍丢失。目录 @120 handoff 仍是 0，提前返回 4，drain 为 0。forum 与 billing 的 strict full transfer 都为 true。CRM 27/16，Ops 34/25。Desk、DeepBench、Wiki、BuggyShop 相对 guard 的已确认缺陷丢失为 0。提升为子分支的按钮次数为 0。这不是新的 fresh 验证，也不是晋升。`python -m benchmark.local_action_drain_reproduce --root experiments/published/local-action-drain-v0.3.17 --verify`

**v0.3.16 Outcome B — partial safe repair.** 提前物理回到父页面会结束当前 sequence；子分支回到自己的 hub 后，已发现但还没试过的本地结构分支先获得一格租约。目录 @120 的 handoff 从 2 降到 0，提前返回 4 次，guard 已确认缺陷没有丢失。buggy-lab @120 发出 6 次本地租约并恢复 BUG-L8，仍丢失 BUG-L1、BUG-L9、BUG-L10。forum 保住完整 transfer。billing 没有丢失 guard 缺陷，但覆盖与 guard 持平，没有满足 v0.3.15 的扩张门。CRM / Ops 仍超过 5 states / 5 URLs。Desk、DeepBench、Wiki、BuggyShop 相对 guard 的已确认缺陷丢失为 0。这不是新的 fresh 验证，也不是晋升。`python -m benchmark.reentry_frontier_reproduce --root experiments/published/reentry-frontier-v0.3.16 --verify`

**v0.3.15 Outcome C — validation failed.** 冻结的 Horizon Handoff 在 forum 与 billing 上完成了结构 transfer（3 个正目标都实际可评估，其中 2 个完整 transfer），但 buggy-lab 丢失了 guard 已确认的 BUG-L1、BUG-L8、BUG-L9、BUG-L10，并且浅层负对照 buggy-directory 触发了 2 次 handoff。Witness violations 与 terminal violations 为 0。这是 fresh 验证失败，不是泛化证明，也不是产品化依据。promotion readiness 为 `not_ready`。下一问是失败分析，不是改默认策略。`python -m benchmark.fresh_handoff_reproduce --root experiments/published/fresh-handoff-v0.3.15 --verify`

**v0.3.14 Outcome A — inspected mechanism repaired and regression-safe.** 嵌套分支在当前 sequence 的 commitment 还多于 1 时保持普通 continuation；只有会消耗最后一格 commitment 的分支才成为真实 child，外层 horizon 推迟到 child 的 parent witness 之后。CRM @120 从 guard 的 5/5 到 20 states / 13 URLs，5 continuations / 2 handoffs / 2 witnesses / horizon 10。Ops @120 从 5/5 到 28 states / 25 URLs，13 continuations / 7 handoffs / 4 witnesses / horizon 19。Witness violations 与 terminal violations 为 0。相对 v0.3.9 guard，BuggyDesk、DeepBench、Wiki、BuggyShop 的已确认缺陷没有丢失。H1–H20 为 0 failures，handoff model 19607 条 raw traces 的 invariant failures 为 0。这是已检查机制用例，不是 fresh validation，也不是泛化证明。候选不晋升。`python -m benchmark.horizon_handoff_reproduce --root experiments/published/horizon-handoff-v0.3.14 --verify`

**v0.3.13 Outcome C — harmful / unsafe.** 测量订正说明 `restore_without_child_return` 把 same-step finding/crash 加上物理 parent match 误记成 false restore；订正后的 residual 为 0。这不改变已发布结果：CRM/Ops 没有修好，并且相对 guard 仍丢失 BuggyDesk K1/K2、DeepBench D7/D11/D13/D14、Wiki W2。`python -m benchmark.nested_stack_reproduce --root experiments/published/nested-stack-v0.3.13 --verify`

**v0.3.12 Outcome C — harmful/regression.** 参数无关的 nested-hub preservation 让 CRM / Ops 的外层 sequence 不再在 commitment 窗口里被 `lost_parent` 打断，并进入 horizon / return。这两个目标是 v0.3.11 已分析机制用例，不是 fresh-generalization。N1–N12、S1–S7 和 5800 条 return model 为 0 failures。历史回归丢失了 BuggyDesk 的 BUG-K3 / BUG-K6 / BUG-K9 / BUG-K10 和 DeepBench 的 BUG-D12。候选不晋升。`python -m benchmark.nested_hub_reproduce --root experiments/published/nested-hub-parent-v0.3.12 --verify`

**v0.3.11 Outcome D — inconclusive suite.** 三个预注册 fresh target 里，只有 `buggy-wiki` 出现 evaluable return-cycle opportunity，并在 guard escape 后进入 C1 未见状态。`buggy-crm` 与 `buggy-ops` 的 C1/guard 均未进入 return phase，机制无法在这套预算下被广泛评估。安全检查通过，C1 confirmed bug 无丢失。不是广泛泛化。预算不追加。`python -m benchmark.multi_target_reproduce --root experiments/published/multi-target-replication-v0.3.11 --verify`

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

三个视图：**总览**（默认，含 v0.3.16 Outcome B，并保留 v0.3.15 Outcome C、v0.3.14 Outcome A、v0.3.13 Outcome C、v0.3.12 Outcome C、v0.3.11 Outcome D）、**实时探索**（浏览器截图 / 状态图 / 决策日志）、**研究证据**（freeze / clean clone / 复现命令）。研究数字来自 `GET /api/showcase`，读取已提交的 `experiments/published/` 产物，不在页面里写死研究结果。演示步骤见 `docs/DEMO.md`。

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
- **v0.3.10 fresh transfer**（experimental, not default）：冻结 v0.3.9 guard 在新应用 BuggyDesk 上再次 escape（7 events，C1 6→35 states），S1–S7 安全套件通过，C1 未丢 bug。**Outcome A — one-target transfer, not generalization.** 产品默认不切。`python -m benchmark.fresh_transfer_reproduce --root experiments/published/fresh-transfer-v0.3.10 --verify`
- **v0.3.11 preregistered multi-target replication**（experimental, not default）：同一 frozen guard，三个预注册 fresh target。**Outcome D — inconclusive suite.** 仅 `buggy-wiki` 可评估并展示 transfer（C1 6→ guard 23 states，2 escapes，L1=2）；`buggy-crm` / `buggy-ops` 未进入 return phase。S1–S7 与 5800 exhaustive traces 0 failures。C1 bugs lost = []。产品默认不切。预算不追加。`python -m benchmark.multi_target_reproduce --root experiments/published/multi-target-replication-v0.3.11 --verify`

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
apps/buggy-desk/  # v0.3.10 fresh-transfer target（冻结）
apps/buggy-crm/   # v0.3.11 preregistered fresh target T1（冻结）
apps/buggy-wiki/  # v0.3.11 preregistered fresh target T2（冻结）
apps/buggy-ops/   # v0.3.11 preregistered fresh target T3（冻结）
benchmark/        # SimBench + WebBench + multi-target reproduce
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
