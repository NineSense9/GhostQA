# GhostQA v0.3.20 — Outcome C

fresh validation harmful, unsafe, or invalid

Static qualification, actual evaluability, and full transfer are different claims. This round is not universal generalization and it does not change the product default.

Promotion readiness: `not_ready`.

Product default changed: no

The C condition that fired: Guard-confirmed bugs were lost on the fresh positive targets. Nested handoff and finding-gated drain both transferred on all four positive targets. Catalog stayed inactive. Kiosk produced finding-gated drains and no nested handoff. Horizon-only drains were zero. Those facts do not override the guard-loss gate.

## Static qualification

| target | nested ops | finding ops | horizon controls | max nested depth | qualified |
|---|---:|---:|---:|---:|---:|
| buggy-campus | 2 | 2 | 1 | 8 | True |
| buggy-warehouse | 2 | 2 | 1 | 8 | True |
| buggy-studio | 2 | 2 | 1 | 8 | True |
| buggy-booking | 2 | 2 | 1 | 8 | True |
| buggy-catalog | 0 | 0 | 0 | 2 | True |
| buggy-kiosk | 0 | 2 | 1 | 4 | True |

## Budget 120

| target | policy | states | URLs | confirmed | handoffs | witnesses | finding triggers | drains | horizon bypasses |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| buggy-campus | C1 | 22 | 18 | BUG-CP11,BUG-CP12,BUG-CP2 | 0 | 0 | 0 | 0 | 0 |
| buggy-campus | G | 34 | 22 | BUG-CP10,BUG-CP11,BUG-CP12,BUG-CP2,BUG-CP3,BUG-CP5,BUG-CP8,BUG-CP9 | 0 | 0 | 0 | 0 | 0 |
| buggy-campus | F | 20 | 13 | BUG-CP1,BUG-CP10,BUG-CP11,BUG-CP12,BUG-CP2,BUG-CP3 | 5 | 5 | 4 | 4 | 0 |
| buggy-warehouse | C1 | 22 | 18 | BUG-WH11,BUG-WH12,BUG-WH2 | 0 | 0 | 0 | 0 | 0 |
| buggy-warehouse | G | 35 | 23 | BUG-WH10,BUG-WH11,BUG-WH12,BUG-WH2,BUG-WH5,BUG-WH8,BUG-WH9 | 0 | 0 | 0 | 0 | 0 |
| buggy-warehouse | F | 31 | 20 | BUG-WH1,BUG-WH10,BUG-WH11,BUG-WH12,BUG-WH2,BUG-WH4,BUG-WH6,BUG-WH7 | 13 | 12 | 5 | 5 | 1 |
| buggy-studio | C1 | 22 | 18 | BUG-ST11,BUG-ST12,BUG-ST2 | 0 | 0 | 0 | 0 | 0 |
| buggy-studio | G | 34 | 22 | BUG-ST10,BUG-ST11,BUG-ST12,BUG-ST2,BUG-ST3,BUG-ST5,BUG-ST8,BUG-ST9 | 0 | 0 | 0 | 0 | 0 |
| buggy-studio | F | 21 | 14 | BUG-ST1,BUG-ST10,BUG-ST11,BUG-ST12,BUG-ST2,BUG-ST3 | 5 | 5 | 4 | 4 | 0 |
| buggy-booking | C1 | 22 | 18 | BUG-BK11,BUG-BK12,BUG-BK2 | 0 | 0 | 0 | 0 | 0 |
| buggy-booking | G | 35 | 23 | BUG-BK10,BUG-BK11,BUG-BK12,BUG-BK2,BUG-BK5,BUG-BK8,BUG-BK9 | 0 | 0 | 0 | 0 | 0 |
| buggy-booking | F | 31 | 20 | BUG-BK1,BUG-BK10,BUG-BK11,BUG-BK12,BUG-BK2,BUG-BK4,BUG-BK6,BUG-BK7 | 13 | 12 | 5 | 5 | 1 |
| buggy-catalog | C1 | 20 | 10 | BUG-CT1,BUG-CT2,BUG-CT4,BUG-CT5,BUG-CT6,BUG-CT7,BUG-CT8 | 0 | 0 | 0 | 0 | 0 |
| buggy-catalog | G | 20 | 10 | BUG-CT1,BUG-CT2,BUG-CT4,BUG-CT5,BUG-CT6,BUG-CT7,BUG-CT8 | 0 | 0 | 0 | 0 | 0 |
| buggy-catalog | F | 20 | 10 | BUG-CT1,BUG-CT2,BUG-CT4,BUG-CT5,BUG-CT6,BUG-CT7,BUG-CT8 | 0 | 0 | 0 | 0 | 0 |
| buggy-kiosk | C1 | 19 | 9 | BUG-KS1,BUG-KS3,BUG-KS4,BUG-KS5,BUG-KS6,BUG-KS7 | 0 | 0 | 0 | 0 | 0 |
| buggy-kiosk | G | 19 | 9 | BUG-KS1,BUG-KS3,BUG-KS4,BUG-KS5,BUG-KS6,BUG-KS7 | 0 | 0 | 0 | 0 | 0 |
| buggy-kiosk | F | 21 | 9 | BUG-KS1,BUG-KS3,BUG-KS4,BUG-KS5,BUG-KS6,BUG-KS7,BUG-KS8 | 0 | 0 | 2 | 2 | 1 |

## Transfer

| target | nested evaluable | finding evaluable | horizon control reached | full transfer | lost vs Guard |
|---|---:|---:|---:|---:|---|
| buggy-campus | True | True | False | False | BUG-CP5, BUG-CP8, BUG-CP9 |
| buggy-warehouse | True | True | True | False | BUG-WH5, BUG-WH8, BUG-WH9 |
| buggy-studio | True | True | False | False | BUG-ST5, BUG-ST8, BUG-ST9 |
| buggy-booking | True | True | True | False | BUG-BK5, BUG-BK8, BUG-BK9 |

## Controls

| target | handoffs | finding drains | horizon drains | max depth | lost vs Guard |
|---|---:|---:|---:|---:|---|
| buggy-catalog | 0 | 0 | 0 | 0 | — |
| buggy-kiosk | 0 | 2 | 0 | 0 | — |

## Aggregate

- positive targets = 4
- composite evaluable count = 4
- full-transfer count = 0
- nested-transfer count = 4
- finding-drain count = 4
- fresh Guard bug loss count = 4
- catalog candidate-specific event count = 0
- kiosk nested handoff count = 0
- global horizon-only drain count = 0
- trigger violations = 0
- witness violations = 0
- terminal violations = 0
- Outcome = C
- promotion_readiness = not_ready
- Product default changed: no

```text
python -m benchmark.fresh_composite_reproduce --root experiments/published/fresh-composite-v0.3.20 --verify
```
