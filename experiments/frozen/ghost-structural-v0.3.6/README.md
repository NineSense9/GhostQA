# Frozen algorithm: ghost-structural-memory (v0.3.6 C1)

This directory freezes the **recommended experimental** GhostQA algorithm from DeepBench v0.3.6 for generalization validation (v0.3.7).

It is **not** the product default. Product Ghost remains NoFrontier with `sequence_mode=off`.

## What is frozen

- Policy: `GhostPolicy(llm=None, use_frontier=False, sequence_mode="structural")`
- Source HEAD at freeze writing: `117b16d2a8160fe4346ceca6edab860d508f7a43`
- DeepBench app freeze: `5355abd444eb4a4e99242c7629a1363c38e52a2a`
- File hashes: see `freeze.json`

## What this freeze is for

Answer whether structural workflow memory still helps on:

1. BuggyFlow **same-app holdout** (requirements-known / manifest-hidden)
2. BuggyShop **cross-app transfer / regression**

## What must not happen after this freeze

- No DeepBench retuning
- No holdout-guided weight changes
- No “one small fix and rerun”
- No adding `ghost-contextual` / `ghost-contextual-crossview` to the primary validation matrix
- No `structural + deferred` portfolio during validation

Harness / measurement bugs may be fixed. Algorithm weakness must be recorded as a negative result.

## How to verify

Compare current `sha256` of the files listed in `freeze.json` against that manifest. Validation runs must abort on mismatch.
