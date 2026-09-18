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

Add new rows; do not delete negative results.
