# GhostQA Failure Corpus

Started in v0.3. Real failures observed during development and experiments.
Not a database — a working log. Add a row when a failure is confirmed.

| Class | Example | Status |
|---|---|---|
| element resolution failure | Replay of a click whose `data-testid` left the DOM | seen in INVALID replay (integration) |
| invalid replay | Prefix of a crashing path is not executable after ddmin cut | handled by tri-state ddmin |
| state collapse | Cart empty/full hashed to one node (v0.2 structural signature) | fixed in v0.3 semantic variant |
| state explosion | `?t=` / clocks / `input_*` buffers creating extra nodes | guarded by volatile-query + obs whitelist |
| navigation error | Same-page click pushed Back stack, Back reloaded current URL | fixed in v0.3 nav history |
| false positive | Idempotent re-click of a live button reported as dead_action | filtered since v0.2 |
| false negative | Nav-loop match required exact full URL list vs path suffix | DeepBench uses `_contains` |
| LLM bad ranking | MockLLM down-ranks Help, which hid a nav-loop on BuggyShop | recorded, not “fixed” by cheating |
| frontier unreachable | Reset+replay landed on a different variant than the target | counted in `restore_failures` |
| flaky web event | `networkidle` timeout after click | swallowed; settle-ms still waits |
| input action explosion | 1 field × 6 payloads counted as 6 frontier actions | **mitigated** v0.3.1 InteractionOpportunity |
| local form sink | Agent enumerates payloads instead of clicking 下一步 | **mitigated** by PayloadPolicy first-wave; WorkflowBFS `input_share=0` |
| frontier payload cardinality bias | `score += len(raw_pending_actions)` | **mitigated** v1.1 interaction counts |
| restore budget waste | Ghost-full restore_ratio 0.08–0.33, BDR=0 | **unresolved** — opportunity-cost relocate still over-jumps |
| risk keyword tunnel vision | 注册 scored above 登录; relocate after adding 登录 still empty BDR | **unresolved** for Ghost-full; Ghost-noFrontier finds D6 |
| reset-blind replay | Flattened multi-episode `result.actions()` replayed after one reset | **fixed** v0.3.2 episode-local `reproduction_actions` |

Add new rows; do not delete negative results.
