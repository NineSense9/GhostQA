# BuggyFlow — DeepBench (GhostQA v0.3)

Deterministic, offline project-workspace app used as the **deep-state**
benchmark. BuggyShop remains the shallow benchmark.

- 16 HTML shells, localStorage state, `data-testid` / `data-obs`
- 14 development bugs in `bugs.manifest.json` (judge only)
- 2 holdout bugs in `holdout.manifest.json` (do not tune on these)
- Spec in `spec.json` (oracle; no bug ids)

## Freeze rule

After the freeze commit, do **not** change bug triggers, depths, branch
placement, or the development manifest unless you found a correctness bug
in the benchmark itself. Record the reason in the commit message.

GhostQA exploration and Oracle must never read `bugs.manifest.json` or
`holdout.manifest.json`. Pages must not expose `data-bug-id`.

## Run

```bash
python apps/buggy-flow/server.py 3940
python -m ghostqa run --url http://127.0.0.1:3940 --policy ghost --budget 80 \
  --spec apps/buggy-flow/spec.json --out runs/deep-demo
python -m benchmark.web_runner --app buggy-flow --budget 40 --seeds 1,2 \
  --skip-minimize --out experiments/published/deepbench-v0.3
```
