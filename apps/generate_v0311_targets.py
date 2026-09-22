"""Write the frozen v0.3.11 preregistered apps.

    python apps/generate_v0311_targets.py
"""
from benchmark.multitarget_generator import main

if __name__ == "__main__":
    raise SystemExit(main(["write"]))
