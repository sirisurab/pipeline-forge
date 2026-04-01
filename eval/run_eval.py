# eval/run_eval.py
# Evaluates all four KGS pipeline test files against the three judge metrics.
# Reads test files from disk, runs each through all three GEval metrics,
# prints a summary table, and writes results to eval_results.md.
#
# Usage:
#   python eval/run_eval.py
#
# Expects to be run from the repo root (dapi_poc/ parent), with kgs/ as a sibling:
#   .
#   ├── dapi_poc/
#   └── kgs/
#       └── tests/
#           ├── test_acquire.py
#           ├── test_ingest.py
#           ├── test_transform.py
#           └── test_features.py

import os
import sys
from dotenv import load_dotenv
import textwrap
from pathlib import Path
from datetime import datetime

from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from kgs_metrics import STAGE_METRICS

# ---------------------------------------------------------------------------
# Config — adjust KGS_TESTS_DIR if running from a different location
# ---------------------------------------------------------------------------
KGS_TESTS_DIR = Path(__file__).resolve().parent.parent / "kgs" / "tests"
OUTPUT_FILE = Path(__file__).resolve().parent / "eval_results.md"

TEST_FILES = [
    "test_acquire.py",
    "test_ingest.py",
    "test_transform.py",
    "test_features.py",
]

PASS_THRESHOLD = 0.5


def load_test_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Test file not found: {path}")
    return path.read_text(encoding="utf-8")


def run_evaluation(filename: str, source: str) -> dict:
    """Run stage-appropriate metrics against one test file. Returns dict of metric → score/reason."""
    test_case = LLMTestCase(
        input=filename,
        actual_output=source,
    )

    metrics = STAGE_METRICS.get(filename)
    if not metrics:
        print(f"  WARNING: No metrics defined for {filename}, skipping.")
        return {}

    results = {}
    for metric in metrics:
        try:
            metric.measure(test_case)
            results[metric.name] = {
                "score": metric.score,
                "reason": metric.reason,
                "passed": metric.score >= PASS_THRESHOLD,
            }
        except Exception as e:
            results[metric.name] = {
                "score": None,
                "reason": f"ERROR: {e}",
                "passed": False,
            }
    return results


def format_score(score) -> str:
    if score is None:
        return "ERR "
    bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
    return f"{score:.2f} [{bar}]"


def write_markdown_report(all_results: dict):
    lines = [
        f"# KGS Pipeline — LLM Judge Eval Results",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"*Judge: Groq / llama-3.3-70b-versatile*",
        "",
        "## Summary",
        "",
    ]

    for filename, results in all_results.items():
        if not results:
            continue
        metric_names = list(results.keys())
        header = f"| File | " + " | ".join(metric_names) + " |"
        separator = "|---|" + "|---|" * len(metric_names)
        lines.append(header)
        lines.append(separator)
        row = f"| {filename} |"
        for metric_name in metric_names:
            r = results.get(metric_name, {})
            score = r.get("score")
            passed = r.get("passed", False)
            cell = f" {'✓' if passed else '✗'} {score:.2f} |" if score is not None else " ERR |"
            row += cell
        lines.append(row)
        lines.append("")

    lines += ["---", "", "## Detail", ""]

    for filename, results in all_results.items():
        if not results:
            continue
        lines.append(f"### {filename}")
        lines.append("")
        for metric_name, r in results.items():
            score = r.get("score")
            reason = r.get("reason", "")
            passed = r.get("passed", False)
            status = "PASS" if passed else "FAIL"
            lines.append(f"**{metric_name}** — {status} ({score:.2f})" if score is not None else f"**{metric_name}** — ERROR")
            lines.append("")
            for line in textwrap.wrap(reason, width=100):
                lines.append(f"> {line}")
            lines.append("")

    report = "\n".join(lines)
    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(f"\n✓ Full report written to {OUTPUT_FILE}")


def main():

    load_dotenv()

    if not KGS_TESTS_DIR.exists():
        print(f"ERROR: kgs/tests/ not found at {KGS_TESTS_DIR}")
        print("Adjust KGS_TESTS_DIR in run_eval.py or run from repo root.")
        sys.exit(1)

    all_results = {}

    for filename in TEST_FILES:
        path = KGS_TESTS_DIR / filename
        print(f"\n{'='*60}")
        print(f"Evaluating: {filename}")
        print('='*60)

        try:
            source = load_test_file(path)
        except FileNotFoundError as e:
            print(f"  SKIP: {e}")
            continue

        results = run_evaluation(filename, source)
        all_results[filename] = results

        # Print inline summary
        for metric_name, r in results.items():
            score = r["score"]
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  {metric_name:<25} {status}  {format_score(score)}")
            # Print first sentence of reason only inline
            reason_preview = r["reason"].split(".")[0] if r["reason"] else ""
            print(f"    → {reason_preview[:120]}")

    write_markdown_report(all_results)


if __name__ == "__main__":
    main()
