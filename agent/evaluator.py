from typing_extensions import TypedDict
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
import json
import mypy.api
from langchain.tools import tool
from agent.config import repo_root, project

eval_file = "eval_results.md"
eval_path = Path(repo_root) / eval_file

class CheckResult(TypedDict):
    errors: str
    status: int

class EvalResult(TypedDict):
    passed: bool
    blockers: str
    failures: dict[str, str]

# utility functions
def linting(repo_root: str, project: str) -> CheckResult:
    """ Checks for linting errors
        Performs formatting and auto-fix of 'safe' linting errors
    """
    # format
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format"],
        cwd=repo_root,
        capture_output=True,
        text=True
    )
    # check for linting errors, auto-fix safe errors and formatting issues
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--fix"],
        cwd=repo_root,
        capture_output=True,
        text=True
    )

    return CheckResult(errors=normalize_paths(result.stdout, project=project), status= result.returncode)

def type_check(repo_root: str, project: str) -> CheckResult:
    cache_dir = Path.cwd() / ".mypy_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    stdout_report, stderr_report, exit_status = mypy.api.run([repo_root])
    return CheckResult(errors=normalize_paths(stdout_report, project=project), status=exit_status)

def run_tests(repo_root: str, project: str) -> CheckResult:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/",
        "-m","not integration",
        "--tb=short","-q"
        ],
        cwd=repo_root,
        capture_output = True,
        text = True
    )
    return CheckResult(errors=normalize_paths(result.stdout+result.stderr, project=project), status=result.returncode)

def check_for_blocker(repo_root: str, project: str) -> CheckResult:
    """Search all Python files in {project}_pipeline/ and tests/ for BLOCKER: comments."""

    blockers = []
    search_dirs = [f"{project}_pipeline", "tests"]

    for dir_name in search_dirs:
        search_path = Path(repo_root) / dir_name
        if not search_path.exists():
            continue
        for py_file in search_path.rglob("*.py"):
            for line_num, line in enumerate(py_file.read_text().splitlines(), start=1):
                if "BLOCKER:" in line:
                    blockers.append(
                        f"{py_file.relative_to(repo_root)}:{line_num} → {line.strip()}"
                    )

    if blockers:
        return CheckResult(
            errors="\n".join(blockers),
            status=2  # distinct from regular eval failure (1)
        )
    return CheckResult(errors="", status=0)

# Strip repo_root prefix from error messages so paths are virtual-FS relative
def normalize_paths(errors: str, project: str) -> str:
    return errors.replace(repo_root + "/", "/").replace(f"{project}/", "/")

def write_eval_to_file(eval_path: Path, eval_result: EvalResult) -> dict[str, bool | str]:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write to file in readable markdown format
    passed = eval_result["passed"]
    failures = eval_result["failures"]
    blockers = eval_result["blockers"]
    try:
        with eval_path.open(mode="a") as f:
            f.write(f"\n## Eval Run at {timestamp}\n\n")
            f.write(f"**Status:** {'✅ PASSED' if passed else '❌ FAILED'}\n\n")
            if blockers and blockers != "":
                f.write("### Blockers:\n")
                f.write(f"```\n{blockers}\n```\n\n")
            if failures:
                f.write("### Failures:\n")
                for label, error_msg in failures.items():
                    f.write(f"- **{label}:**\n")
                    f.write(f"```\n{error_msg}\n```\n\n")

            f.write("---\n")
    except Exception as e:
        # Fallback: return full result in response if file write fails
        return {"passed": passed, "result": f"File write failed: {e}\n\n{json.dumps(eval_result, indent=2)}"}  # noqa: E501

    # Return concise reference to file
    if passed:
        return {"passed": True, "result": f"All checks passed. See {eval_file} for details (timestamp: {timestamp})"}  # noqa: E501
    else:
        failure_summary = ", ".join(failures.keys())
        return {"passed": False, "result": f"Eval failed: {failure_summary}. See {eval_file} for full errors (timestamp: {timestamp})"}  # noqa: E501


def install_deps(repo_root: str) -> None:
    """Install dev dependencies from pyproject.toml before running checks."""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]", "-q"],
        cwd=repo_root,
        capture_output=True,
    )

@tool
def run_evaluator() -> dict[str, bool | str]:

    """ Evaluates the pipeline code for linting, type checking and test errors.
        Must be called only after
        1. coder-advanced has confirmed that code-writing is complete
        2. coder-basic has confirmed that code-fixing is complete
    """
    # Gate 0 - coder blocked
    blocker_chk_response = check_for_blocker(repo_root, project=project)
    if blocker_chk_response["status"] == 2:
        blocker_msg = f"""Coder is blocked with the following errors.
        Human intervention needed to fix the errors and unblock the coder-
        errors - {blocker_chk_response['errors']}"""
        eval_result = EvalResult(passed=False, blockers=blocker_msg, failures=dict())
        result = write_eval_to_file(eval_path, eval_result)
        return result

    # Gate 1 — ensure dev deps installed (pandas-stubs, types-requests etc.)
    install_deps(repo_root)

    # Gate 2 — quality checks & tests
    linting_response = linting(repo_root, project=project)
    type_check_response = type_check(repo_root, project=project)
    tests_response = run_tests(repo_root, project=project)
    failures = dict()
    passed = True
    for check, label in [
        (linting_response, "Linting"),
        (type_check_response, "Type check"),
        (tests_response, "Unit Tests")
    ]:
        if check["status"] != 0:
            failures[label] = f"{label} failed. Fix these errors:\n{check['errors']}"
            passed = False

    eval_result = EvalResult(passed=passed, blockers="", failures=failures)
    result = write_eval_to_file(eval_path, eval_result)
    return result
