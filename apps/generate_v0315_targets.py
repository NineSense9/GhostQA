"""Write the v0.3.15 fresh handoff targets.

    python apps/generate_v0315_targets.py
"""
from benchmark.fresh_handoff_generator import main

if __name__ == "__main__":
    raise SystemExit(main(["write"]))
