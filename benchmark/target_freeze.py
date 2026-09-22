"""Hash and verify evaluation-relevant app files (LF-normalized)."""
from __future__ import annotations

import argparse
import json
import os

from benchmark.algorithm_freeze import ROOT, sha256_file, verify_freeze

DESK_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "buggy-desk-v0.3.10", "freeze.json")
V0311_SUITE_FREEZE = os.path.join(
    ROOT, "experiments", "frozen", "v0.3.11-multitarget", "freeze.json")
V0311_TARGET_FREEZES = {
    "buggy-crm": os.path.join(
        ROOT, "experiments", "frozen", "v0.3.11-multitarget", "buggy-crm", "freeze.json"),
    "buggy-wiki": os.path.join(
        ROOT, "experiments", "frozen", "v0.3.11-multitarget", "buggy-wiki", "freeze.json"),
    "buggy-ops": os.path.join(
        ROOT, "experiments", "frozen", "v0.3.11-multitarget", "buggy-ops", "freeze.json"),
}

DESK_FILES = [
    "apps/buggy-desk/server.py",
    "apps/buggy-desk/spec.json",
    "apps/buggy-desk/bugs.manifest.json",
    "apps/buggy-desk/topology.json",
    "apps/buggy-desk/gen_pages.py",
    "apps/buggy-desk/README.md",
    "apps/buggy-desk/static/app.js",
    "apps/buggy-desk/static/index.html",
    "apps/buggy-desk/static/tickets.html",
    "apps/buggy-desk/static/ticket.html",
    "apps/buggy-desk/static/customers.html",
    "apps/buggy-desk/static/customer.html",
    "apps/buggy-desk/static/activity.html",
    "apps/buggy-desk/static/kb.html",
    "apps/buggy-desk/static/article.html",
    "apps/buggy-desk/static/reports.html",
    "apps/buggy-desk/static/team.html",
    "apps/buggy-desk/static/settings.html",
    "apps/buggy-desk/static/profile.html",
    "apps/buggy-desk/static/integrations.html",
    "apps/buggy-desk/static/compose.html",
    "apps/buggy-desk/static/help.html",
    "apps/buggy-desk/static/handbook.html",
]


def file_record(rel: str) -> dict:
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    with open(path, "rb") as f:
        raw = f.read()
    lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return {
        "sha256": sha256_file(path),
        "bytes": len(lf),
    }


def build_desk_freeze(*, freeze_commit: str, purpose: str) -> dict:
    files = {rel: file_record(rel) for rel in DESK_FILES}
    return {
        "target": "buggy-desk",
        "round": "v0.3.10",
        "purpose": purpose,
        "freeze_commit": freeze_commit,
        "no_target_policy_evaluation_before_freeze": True,
        "manifest_is_judge_only": True,
        "post_evaluation_changes_invalidate_protocol_identity": True,
        "hash_normalization": "LF newlines",
        "files": files,
    }


def write_desk_freeze(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


GENERATOR_FILES = [
    "benchmark/multitarget_generator.py",
    "benchmark/multitarget_js.py",
    "benchmark/multitarget_vocab.py",
    "apps/generate_v0311_targets.py",
]


def v0311_target_files(app_name: str) -> list:
    from benchmark.multitarget_generator import generated_relpaths
    return generated_relpaths(app_name)


def build_v0311_target_freeze(app_name: str, *, freeze_commit: str,
                              protocol_commit: str, purpose: str) -> dict:
    files = {rel: file_record(rel) for rel in v0311_target_files(app_name)}
    return {
        "target": app_name,
        "round": "v0.3.11",
        "purpose": purpose,
        "protocol_commit": protocol_commit,
        "freeze_commit": freeze_commit,
        "no_target_policy_evaluation_before_freeze": True,
        "manifest_is_judge_only": True,
        "post_evaluation_changes_invalidate_protocol_identity": True,
        "hash_normalization": "LF newlines",
        "files": files,
    }


def build_v0311_suite_freeze(*, freeze_commit: str, protocol_commit: str,
                             purpose: str) -> dict:
    from benchmark.multitarget_vocab import APP_NAMES
    rels = list(GENERATOR_FILES)
    for name in APP_NAMES:
        rels.extend(v0311_target_files(name))
    files = {rel: file_record(rel) for rel in rels}
    return {
        "target": "v0.3.11-multitarget",
        "round": "v0.3.11",
        "purpose": purpose,
        "protocol_commit": protocol_commit,
        "freeze_commit": freeze_commit,
        "no_target_policy_evaluation_before_freeze": True,
        "manifest_is_judge_only": True,
        "post_evaluation_changes_invalidate_protocol_identity": True,
        "hash_normalization": "LF newlines",
        "files": files,
    }


def write_v0311_freezes(*, freeze_commit: str, protocol_commit: str) -> None:
    from benchmark.multitarget_vocab import APP_NAMES
    purpose = "v0.3.11 multi-target suite freeze before policy evaluation"
    suite = build_v0311_suite_freeze(
        freeze_commit=freeze_commit, protocol_commit=protocol_commit,
        purpose=purpose)
    write_desk_freeze(V0311_SUITE_FREEZE, suite)
    for name in APP_NAMES:
        payload = build_v0311_target_freeze(
            name, freeze_commit=freeze_commit, protocol_commit=protocol_commit,
            purpose=purpose)
        write_desk_freeze(V0311_TARGET_FREEZES[name], payload)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["verify", "write", "write-v0311"])
    ap.add_argument("--freeze", default=DESK_FREEZE)
    ap.add_argument("--commit", default="")
    ap.add_argument("--protocol-commit", default="")
    args = ap.parse_args(argv)
    if args.cmd == "verify":
        bad = verify_freeze(args.freeze)
        if bad:
            print("MISMATCH")
            for line in bad:
                print(line)
            return 2
        print("OK")
        return 0
    if args.cmd == "write-v0311":
        write_v0311_freezes(
            freeze_commit=args.commit, protocol_commit=args.protocol_commit)
        print("wrote", V0311_SUITE_FREEZE)
        return 0
    payload = build_desk_freeze(
        freeze_commit=args.commit,
        purpose="v0.3.10 fresh-transfer target freeze before policy evaluation",
    )
    write_desk_freeze(args.freeze, payload)
    print("wrote", args.freeze)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
