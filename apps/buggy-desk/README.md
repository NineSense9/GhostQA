# BuggyDesk

Deterministic internal support-desk Web benchmark for GhostQA v0.3.10.

- Fully offline localhost server (`server.py`)
- Static HTML + `static/app.js`
- `spec.json` is public to Policy/Explorer/Oracle
- `bugs.manifest.json` and `topology.json` are judge/authoring only and must not be fetched by the browser or read by Policy/Explorer/Oracle

Do not expose this app as a public daemon. It is a research target.
