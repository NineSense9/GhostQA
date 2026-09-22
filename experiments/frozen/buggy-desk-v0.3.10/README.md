# Frozen target: BuggyDesk (v0.3.10)

Fresh internal support-desk Web benchmark. Frozen before any C1 / return-guard / BFS / DFS / product-baseline evaluation.

- Manifest is judge-only.
- Policy/Explorer/Oracle must not read `bugs.manifest.json` or `topology.json`.
- Post-evaluation edits of hashed files invalidate this protocol identity.

Hash normalization: LF newlines (clone-portable).
