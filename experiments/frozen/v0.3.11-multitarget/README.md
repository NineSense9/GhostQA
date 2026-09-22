# Frozen v0.3.11 multi-target suite

Preregistered generator + three fresh targets. Frozen before any C1 / return-guard / BFS / DFS / product-baseline evaluation.

- Protocol commit is recorded in `freeze.json`.
- Manifests and topology files are judge-only.
- Policy / Explorer / Oracle must not read `bugs.manifest.json` or `topology.manifest.json`.
- Post-evaluation edits of hashed files invalidate this protocol identity.

Hash normalization: LF newlines (clone-portable).
