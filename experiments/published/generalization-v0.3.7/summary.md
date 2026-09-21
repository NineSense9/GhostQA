# GhostQA v0.3.7 — Algorithm Freeze & Generalization Validation

- **Date**: 2026-09-21
- **Algorithm freeze**: `ghost-structural-memory` (v0.3.6 C1)
- **Source HEAD at freeze writing**: `117b16d`
- **Freeze commit**: `a54d325`
- **Protocol commit**: `ba2e5b6` (`executed=false` at that commit)
- **DeepBench app freeze**: `5355abd`
- **n=1 NoLLM**. No algorithm change after freeze. Hashes verified OK after both validation matrices.

This round is **not** a DeepBench tuning round. Three evidence layers are reported separately. They are not pooled into one BDR.

## Frozen candidate

```text
GhostPolicy(llm=None, use_frontier=False, sequence_mode="structural")
```

Product default remains NoFrontier, `sequence_mode=off`.

Excluded from primary validation: `ghost-contextual`, `ghost-contextual-crossview`.

## V1 — BuggyFlow same-app holdout

Label: **requirements-known / manifest-hidden**. Not a new application. N=2 (`BUG-H1`, `BUG-H2`).

| policy | budget | confirmed / 2 | IDs | candidates | replay p/f/i | TTCB | states | unique branches | attempts/branch |
|---|---|---|---|---|---|---|---|---|---|
| DFS | 40–120 | **1/2** | H1 | 14–20 | 1/0/0 | 8 | 15–40 | — | — |
| BFS | 40–120 | **1/2** | H1 | 13–20 | 1/0/0 | 28 | 11–31 | — | — |
| ghost-nollm | 40–120 | **0/2** | — | 6 | 0/0/0 | — | 13 | — | — |
| ghost-deferred | 40–80 | 0/2 | — | 2–5 | 0/0/0 | — | 17–33 | — | — |
| ghost-deferred | 120 | **1/2** | H1 | 17 | 1/0/0 | 93 | 38 | — | — |
| ghost-sequence | 40–120 | **0/2** | — | 5 | 0/0/0 | — | 20–63 | 8 | 2.6–10.9 |
| ghost-structural-memory | 40–120 | **0/2** | — | 9–14 | 0/0/0 | — | 20–28 | 15–19 | 1.2–2.8 |

Nobody confirmed **H2**. C1 did not confirm **H1**.

### Holdout bug visibility (Judge, post-hoc)

| bug | kind | depth | requirement-visible? | manifest-hidden? | who confirmed |
|---|---|---|---|---|---|
| BUG-H1 | js_error (changelog detail) | 3 | **no** (not a spec assertion; L1 js_error) | yes | DFS, BFS, deferred@120 |
| BUG-H2 | semantic (`bill_qty_non_negative`) | 8 | **yes** (in `spec.json`) | yes | **nobody** |

Do not call this “fully blind bug discovery”. H2 is spec-visible. H1 is a shallow-ish js_error that DFS finds and the sequence family misses — the same shallow trade-off seen on D4/D8.

### What *did* transfer on the same app

C1 vs C0 on this holdout run (same BuggyFlow binary):

- unique branches started 8 → 15–19
- attempts/branch @120 **10.875 → 2.789**

That is **efficiency on the development app**, not holdout bug-finding.

## V2 — BuggyShop cross-app transfer / regression

Not a new blind benchmark. Used in v0.2. 10 bugs (W1–W10).

| policy | budget | confirmed / 10 | BDR | TTCB | IDs | states |
|---|---|---|---|---|---|---|
| DFS | 40–120 | 1/10 | 0.10 | 19 | W7 | 15–42 |
| BFS | 40 | 3/10 | 0.30 | 3 | W1,W5,W6 | 20 |
| BFS | 80 | 4/10 | 0.40 | 3 | +W9 | 35 |
| BFS | **120** | **7/10** | **0.70** | 3 | W1–W3,W5–W7,W9 | 41 |
| ghost-nollm | 40 | 1/10 | 0.10 | 1 | W6 | 11 |
| ghost-nollm | 80–120 | 4/10 | 0.40 | 1 | W1,W2,W5,W6 | 23 |
| ghost-deferred | 40 | 1/10 | 0.10 | 21 | W6 | 13 |
| ghost-deferred | 80 | 5/10 | 0.50 | 21 | W1,W2,W5,W6,W9 | 28 |
| ghost-deferred | 120 | 6/10 | 0.60 | 21 | +W3 | 34 |
| ghost-sequence | 40–120 | 1/10 | 0.10 | 3 | W5 | **6** |
| ghost-structural-memory | 40–120 | 1/10 | 0.10 | 3 | W5 | **6** |

C1 **equals C0** here (same 1/10, 6 states, 2 unique branches, 2 hubs). It is **not** a catastrophic crash, but it **is** a coverage collapse vs BFS/nollm/deferred. Sequence-family hub commitment is a poor fit for this shallow shop. `HUB_MIN_BRANCHES` was **not** lowered.

## Development reference (not re-tuned)

Frozen DeepBench v0.3.6, C1@120: BDR 0.429 (tie DFS), Deep-BDR 0.667 (D6/D7/D11–D14), D6+D12 kept. DFS kept broader shallow coverage (D1–D4, D8).

## Pre-registered outcome

**C. Keep C1 as a DeepBench-specific research result.**

Not A: C1 found **0/2** holdout bugs.  
Not a clean B: holdout was not positive, and BuggyShop coverage collapsed.

Structural workflow memory remains a **credible DeepBench finding** (Deep-BDR 0.222→0.667; repeat 10.9→2.8). It did **not** generalize to hidden same-app bugs or to BuggyShop in this one-shot protocol.

## Product

Default **unchanged**: NoFrontier, `sequence_mode=off`.  
Experimental recommendation is **not** promoted.

## Next

Do not retune on holdout. Prefer **application-shape / state-semantics analysis** (why sequence modes pin 6 states on BuggyShop; why H1/H2 were missed). Real LLM evidence is not the next step until the NoLLM algorithm’s transfer limits are understood.
