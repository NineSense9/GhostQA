# v0.3.22 diagnostic: persistent_post_terminal_sink

Within the preregistered horizons, the remaining regression on the targets that lost template 5/8/9 at budget 120 is consistent with a post-terminal ordinary-policy attractor rather than sequence-scoped return-cycle failure or 120-step budget delay.

This round only characterizes four frozen v0.3.20 positive targets, the frozen v0.3.21 candidate, and budgets up to 480. It does not establish universal web behavior, an infinite loop, production readiness, or default-policy readiness.

Product default changed: false. Promotion readiness: not_ready.
v0.3.21 candidate result remains Outcome C.

v0.3.22 没有改策略，只分析 v0.3.21 的分裂结果。Campus/Studio 在 sequence-scoped return cycle 已经被正确 abandon 后，普通探索仍进入重复 导航吸引子；到 b480 仍未重新获得原 entity residual frontier。Warehouse/Booking 则保留了回到 entity 的生产性路径。这是已检查目标上的 failure diagnosis，不是新修复，也不是 fresh validation。

Potential next research question: can ordinary no-active-sequence exploration detect repeated SCC/edge recurrence with no state or frontier progress and yield to a previously known global residual frontier without creating new sequence success?

## Static topology

| target | sink SCC size | closed | outgoing edges | entity reachable | shortest entity path |
|---|---:|---:|---:|---:|---:|
| buggy-campus | 2 | true | 0 | false |  |
| buggy-warehouse | 26 | false | 1 | true | 0 |
| buggy-studio | 3 | true | 0 | false |  |
| buggy-booking | 26 | false | 1 | true | 0 |

## Runtime

| target | budget | abandon step | sink fraction | max no-new-state streak | entity reentry | residual action | template recovered |
|---|---:|---:|---:|---:|---:|---:|---:|
| buggy-campus | 120 | 38 | 0.703704 | 55 | 2 | 0 | false |
| buggy-campus | 240 | 38 | 0.880597 | 175 | 2 | 0 | false |
| buggy-campus | 480 | 38 | 0.945578 | 415 | 2 | 0 | false |
| buggy-warehouse | 120 | 38 | 1.0 | 11 | 10 | 6 | true |
| buggy-warehouse | 240 | 38 | 0.995025 | 63 | 10 | 6 | true |
| buggy-warehouse | 480 | 38 | 0.997732 | 303 | 10 | 6 | true |
| buggy-studio | 120 | 38 | 0.703704 | 50 | 2 | 0 | false |
| buggy-studio | 240 | 38 | 0.880597 | 170 | 2 | 0 | false |
| buggy-studio | 480 | 38 | 0.945578 | 410 | 2 | 0 | false |
| buggy-booking | 120 | 38 | 1.0 | 11 | 10 | 6 | true |
| buggy-booking | 240 | 38 | 0.995025 | 63 | 10 | 6 | true |
| buggy-booking | 480 | 38 | 0.997732 | 303 | 10 | 6 | true |

## Sequence scope

| target | horizon branch | horizon step | cycle escape step | terminal | active same sequence afterward |
|---|---|---:|---:|---|---:|
| buggy-campus | 0fad224e887cf7c5:click:open_leaf | 65 | 67 | return_cycle_abandoned | false |
| buggy-warehouse | bf665b81ba0e1863:click:open_leaf | 65 | 67 | return_cycle_abandoned | false |
| buggy-studio | 4749750aebae6484:click:open_leaf | 65 | 67 | return_cycle_abandoned | false |
| buggy-booking | 1ee6dbe67332601d:click:open_leaf | 65 | 67 | return_cycle_abandoned | false |

Budget 240 and 480 use the same horizon-cycle rule. Their steps are in `metrics/per-target.json`.

## Contrast

| target | first waypoint escape | second useful waypoint/frontier | 5/8/9 recovered @120 | recovered @240 | recovered @480 |
|---|---:|---:|---:|---:|---:|
| buggy-campus | 21 | false | false | false | false |
| buggy-warehouse | 21 | true | true | true | true |
| buggy-studio | 21 | false | false | false | false |
| buggy-booking | 21 | true | true | true | true |

diagnostic_conclusion: persistent_post_terminal_sink
