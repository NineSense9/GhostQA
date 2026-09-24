# v0.3.21 result: Outcome C

unsafe, harmful, or protocol-invalid

This round is an inspected repair of the frozen v0.3.20 fresh targets. It is not fresh validation and it does not change the product default.

Waypoint mechanism engaged: 4/4.
Positives retaining every Guard bug: 2/4.
Template 5/8/9 recovered: 2/4.
Catalog waypoint escapes: 0.
Kiosk waypoint escapes: 0.
Horizon-only drains: 0.
Product default changed: false.

v0.3.19 Outcome A and v0.3.20 Outcome C remain unchanged.

| target | Guard confirmed | v0.3.20 F confirmed | v0.3.21 confirmed | 5/8/9 recovered | lost vs Guard |
|---|---|---|---|---|---|
| buggy-campus | BUG-CP10, BUG-CP11, BUG-CP12, BUG-CP2, BUG-CP3, BUG-CP5, BUG-CP8, BUG-CP9 | BUG-CP1, BUG-CP10, BUG-CP11, BUG-CP12, BUG-CP2, BUG-CP3 | BUG-CP10, BUG-CP11, BUG-CP12, BUG-CP2, BUG-CP3 | False | BUG-CP5, BUG-CP8, BUG-CP9 |
| buggy-warehouse | BUG-WH10, BUG-WH11, BUG-WH12, BUG-WH2, BUG-WH5, BUG-WH8, BUG-WH9 | BUG-WH1, BUG-WH10, BUG-WH11, BUG-WH12, BUG-WH2, BUG-WH4, BUG-WH6, BUG-WH7 | BUG-WH10, BUG-WH11, BUG-WH12, BUG-WH2, BUG-WH4, BUG-WH5, BUG-WH6, BUG-WH7, BUG-WH8, BUG-WH9 | True | — |
| buggy-studio | BUG-ST10, BUG-ST11, BUG-ST12, BUG-ST2, BUG-ST3, BUG-ST5, BUG-ST8, BUG-ST9 | BUG-ST1, BUG-ST10, BUG-ST11, BUG-ST12, BUG-ST2, BUG-ST3 | BUG-ST10, BUG-ST11, BUG-ST12, BUG-ST2, BUG-ST3 | False | BUG-ST5, BUG-ST8, BUG-ST9 |
| buggy-booking | BUG-BK10, BUG-BK11, BUG-BK12, BUG-BK2, BUG-BK5, BUG-BK8, BUG-BK9 | BUG-BK1, BUG-BK10, BUG-BK11, BUG-BK12, BUG-BK2, BUG-BK4, BUG-BK6, BUG-BK7 | BUG-BK10, BUG-BK11, BUG-BK12, BUG-BK2, BUG-BK4, BUG-BK5, BUG-BK6, BUG-BK7, BUG-BK8, BUG-BK9 | True | — |

| target | escapes | first escape step | next label | next action |
|---|---:|---:|---|---|
| buggy-campus | 1 | 21 | branch | open_side |
| buggy-warehouse | 2 | 21 | branch | open_side |
| buggy-studio | 1 | 21 | branch | open_side |
| buggy-booking | 2 | 21 | branch | open_side |

