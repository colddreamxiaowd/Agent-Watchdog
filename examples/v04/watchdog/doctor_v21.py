"""Chapter 21: local readiness. This script cannot authenticate real Codex."""
import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import integration_check


def probe(repo, log=None):
    repo = Path(repo).expanduser().resolve()
    codex = shutil.which("codex")
    report = {"platform": platform.platform(), "python": sys.version.split()[0],
              "git": shutil.which("git") or "NOT_FOUND",
              "codex": codex or "NOT_FOUND",
              "codex_version": "NOT_CHECKED",
              "real_codex_end_to_end": "NOT_VERIFIED"}
    if codex:
        try:
            p = subprocess.run([codex, "--version"], capture_output=True, text=True,
                               timeout=8, check=False)
            report["codex_version"] = (p.stdout or p.stderr).strip()[:120]
        except (OSError, subprocess.TimeoutExpired):
            report["codex_version"] = "UNAVAILABLE"
    try:
        report["readiness"] = integration_check.inspect(repo, log=log)
    except (RuntimeError, OSError, ValueError) as exc:
        report["readiness_error_type"] = type(exc).__name__
    report["steps"] = [
        "Run codex from a trusted disposable Git test project.",
        "Inspect /hooks, enable reviewed project hook only.",
        "Compare one real tool operation with private local JSONL timestamp and ID.",
        "Run independent Git scan, record observation locally; do not upload raw logs.",
    ]
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--log")
    a = p.parse_args()
    print(json.dumps(probe(a.repo, a.log), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
