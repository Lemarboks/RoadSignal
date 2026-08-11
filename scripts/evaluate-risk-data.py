from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.risk.data_pipeline import canonical_json, evaluate  # noqa: E402


DEFAULT_MANIFEST = ROOT / "data" / "risk" / "demo-risk-events-v1.manifest.json"
DEFAULT_REPORT = ROOT / "apps" / "api" / "app" / "risk" / "artifacts" / "demo-risk-evaluation-v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and evaluate a SafeRoute risk dataset")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the canonical evaluation report")
    mode.add_argument("--check", action="store_true", help="fail if the checked-in report is stale")
    arguments = parser.parse_args()

    rendered = canonical_json(evaluate(arguments.manifest.resolve()))
    if arguments.write:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {arguments.report}")
        return 0

    if not arguments.report.exists():
        print(f"Missing report: {arguments.report}", file=sys.stderr)
        return 1
    if arguments.report.read_text(encoding="utf-8") != rendered:
        print("Risk evaluation report is stale; run with --write and review the diff.", file=sys.stderr)
        return 1
    print("Risk dataset and evaluation report are reproducible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
