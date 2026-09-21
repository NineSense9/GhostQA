# GhostQA v0.3.8 — Application-Shape / State-Semantics Analysis

This round does **not** retune DeepBench, holdout, or BuggyShop scores.
Frozen C1 hashes still match `experiments/frozen/ghost-structural-v0.3.6/freeze.json`.
Diagnostic reruns @120 reproduced v0.3.7 confirmed sets (not new trials).

## A. Baseline & freeze integrity

- Start HEAD: `8ba2b2e`
- Freeze: `ghost-structural-memory`, product default still NoFrontier / `sequence_mode=off`
- v0.3.7 outcome **C** stands
- Five frozen exploration files: hash OK after this round’s tooling

## B. Evidence sources

- Static page graphs from `apps/buggy-shop` / `apps/buggy-flow`
- v0.3.7 published metrics (BDR lock)
- Diagnostic reruns tagged `diagnostic_rerun=true`:
  - BuggyShop @120: BFS, deferred, sequence, C1
  - BuggyFlow holdout @120: DFS, BFS, deferred, sequence, C1
- Artifacts: `metrics/*.json`, `traces/*.jsonl`

Offline: `python -m benchmark.application_shape_analysis`

## C. BuggyShop coverage-collapse trace

**6 states is not “the shop is small”.** BFS reached **11 URLs / 41 states**. C0/C1 reached **4 URLs / 6 states**.

Event trace (C1 = C0):

| step | src → dst | action | sequence label |
|---|---|---|---|
| 0 | index → products | first home branch (`pick_override`) | `branch` |
| 1 | products → detail | `item_apple` | `sequence_followup` |
| 2 | detail → cart | `btn_add` | new **nested hub** branch start |
| 3 | cart | `btn_remove` | W5 confirmed |
| 4+ | index ↔ cart | `返回首页` / browser `back` | `return_hub`, `returning=true` forever |

Facts:

- Home **is** a hub (`HUB_MIN_BRANCHES=3`; 5 branch clicks including search).
- Detail **is also** a hub (加入购物车 / 收藏 / 立即购买). Starting `btn_add` does `lost_parent` on the products branch.
- Parent hub for the live sequence is **detail**, but the only return widget used is **返回首页** (index). `_complete_branch` never matches parent → `returning` never clears.
- 116 `return_attempt` events, 2 `branch_start`, 0 successful return-to-parent.
- Missed: register, login, profile, promo, help, checkout (W1/W2/W6/W9/W10/W4).

BFS/deferred keep ordinary breadth: they do not hard-pick `return_hub` after a nested hub.

Root cause class: **premature hub commitment + return-to-wrong-parent lock**, not fingerprint collapse (variant churn is only 1.5).

## D. H1 divergence trace

H1 path: `index → settings → changelog → btn_changelog_detail` (js_error).

| policy | first action | settings? | changelog? | confirm step |
|---|---|---|---|---|
| DFS | **nav_settings** | yes | yes | **8** |
| BFS | nav_login | yes later | yes | 28 |
| deferred | nav_login | yes later | yes | 93 |
| C0 sequence | **nav_login** | **0** | **0** | — |
| C1 | **nav_login** | **0** | **0** | — |

Divergence is **step 0**. `系统设置` / `更新日志` hit `DISTRACTOR_KEYWORDS` (`设置`, `日志`), so they are not sequence branches. Ghost program score prefers progress `登录`. Sequence family never reaches changelog.

Class: **reach failure** (action ranking / distractor filter), not oracle/replay (DFS js_error confirms immediately).

## E. H2 global failure

H2: spec-visible `bill_qty_non_negative`. Default `billQty=1`; need **two** `btn_qty_down` (1→0 still legal; 0→-1 violates). Unit oracle fires on `-1`.

| policy | reached billing? | qty_down? | two consecutive downs? |
|---|---|---|---|
| DFS / BFS / C0 | **no** | — | — |
| deferred | once, then `nav_project` | no | no |
| C1 | **yes**, 4 visits | yes, interleaved **up, down, up** | **no** |

C1 is **not** the unique failure. DFS/BFS never reach billing (they spent budget on settings/help). C1 reaches billing but follow-up order never nets qty below 0.

Class: mixed **reach failure** (DFS/BFS/C0) + **interaction construction** (C1). Not oracle-blind.

## F. Application-shape descriptors

Measured, **not** wired into policy.

| descriptor | BuggyShop | BuggyFlow (C1 run) | reads as |
|---|---|---|---|
| mean shortest-path depth (static) | **1.36** (max 3) | deep workflow after login | shop is shallow |
| home hub? | **yes** (fanout 6) | **no** (all progress/distractor) | shop commits at the lobby |
| nested hubs | detail is a hub | project is a hub | shop nests hubs on the happy path |
| shallow leaf density | promo/profile/register depth 1 | changelog is a distractor leaf | |
| return-to-hub reuse | C1 **0** (stuck returning) | C1 uses project return | shop return target ≠ parent hub |
| semantic-variant churn | BFS 3.73; C1 1.5 | C0 63 states / few URLs | C0 wastes variants; shop C1 never gets that far |
| branch overlap / fanout | high overlap via home | project branches (members/tasks/billing) | |

Most explanatory: **(1) hub-at-lobby + nested hub on the first path**, **(2) return-to-parent mismatch**, **(3) distractor filter on shallow bugs**, **(4) shallow shortest-path depth**.

## G. Supported vs not

Supported:

- Shop 6-state is a **control-loop lock**, evidenced by 116 return_attempts after step 4.
- H1 miss is **step-0 ranking**, not “sequence is always deep-only by magic”.
- H2 is **global**, not a C1 indictment.
- Structural memory did not cause the shop collapse (C0=C1).

Not supported:

- “C1 is a general workflow tester.”
- “Raising HUB_MIN_BRANCHES would have been proven here” (not tested; would be algorithm change).
- Changing DISTRACTOR_KEYWORDS to catch H1 (holdout-guided; forbidden).

## H. Next-algorithm hypotheses (not implemented)

1. **Hub commitment confidence / nested-hub guard**: do not start a new sequence because a leaf page has 3 buttons.
2. **Breadth-preservation floor**: while `returning` and parent hub is missing, drop return override after N failed attempts.
3. **Application-shape gate**: enable sequence only if home is not a hub or mean depth > τ.
4. **Shallow-coverage reservation**: never classify the only path to an unvisited URL as distractor-only… or keep a small untried-URL quota.

## I. Product decision

Unchanged. Ghost default remains NoFrontier, `sequence_mode=off`.

## J. Next-step proposal

**v0.3.9** should implement **one** of the hypotheses above as an explicit experimental mode (`ghost-sequence-gated` or return-lock breaker), freeze it, and re-run BuggyShop + holdout **without** using those scores to retune DeepBench weights. Real LLM still waits.

## K. Git / CI / reproducibility

- Tooling: `benchmark/application_shape.py`, `benchmark/application_shape_analysis.py`, `benchmark/diagnostic_runner.py`
- Tests: `tests/test_application_shape.py`
- Diagnostic confirmed sets locked to v0.3.7
