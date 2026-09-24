# v0.3.23 result: Outcome B

Safety and protocol pass and the debt relocation engages on Campus and Studio, but template 9 remains missing on both. This is a safe partial repair. It is not promoted.

Residual Frontier Debt Escape did relocate the oldest waypoint debt out of a closed, interaction-exhausted SCC on Campus and Studio. Later normal actions consumed the recorded residual tokens and recovered template 5 and 8. Template 9 is still absent, so confirmed(Guard) is not a subset. Warehouse and Booking kept template 5/8/9 with zero debt relocations. Catalog and Kiosk created no debt and did not relocate.

This is inspected repair evidence only. It is not fresh validation and it does not change the product default.

v0.3.22 diagnosis remains persistent_post_terminal_sink. v0.3.21 remains Outcome C.

## Mechanism

| target | debt created | relocations | tokens consumed | resolved debts | 5/8/9 recovered |
|---|---:|---:|---:|---:|---:|
| buggy-campus | 2 | 1 | 6 | 2 | 5 and 8; BUG-CP9 missing |
| buggy-studio | 2 | 1 | 6 | 2 | 5 and 8; BUG-ST9 missing |
| buggy-warehouse | 2 | 0 | 6 | 2 | yes |
| buggy-booking | 2 | 0 | 6 | 2 | yes |

## Gate

| target | closed exhausted SCC | relocation | replay ok | productive residual exploration | lost vs Guard |
|---|---:|---:|---:|---:|---|
| buggy-campus | yes | 1 | yes | yes | BUG-CP9 |
| buggy-studio | yes | 1 | yes | yes | BUG-ST9 |
| buggy-warehouse | no | 0 |  | organic consumption | none |
| buggy-booking | no | 0 |  | organic consumption | none |

## Controls

| target | debt created | relocation | violations | Guard loss |
|---|---:|---:|---:|---|
| buggy-catalog | 0 | 0 | 0 | none |
| buggy-kiosk | 0 | 0 | 0 | none |

Product default changed: false.
