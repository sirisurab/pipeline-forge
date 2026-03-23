from typing_extensions import TypedDict
import sys
import subprocess
import shutil
from pathlib import Path
import mypy.api
from langchain.tools import tool
from pydantic import BaseModel
from agent.config import repo_root

class CheckResult(TypedDict):
    errors: str
    status: int

class EvalResult(BaseModel):
    passed: bool
    blockers: str
    failures: dict[str, str]

# utility functions
def ensure_playwright(repo_root:str):
    """
    Makes sure playwrigth and chromium are installed.
    If not, installs them
    """
    check_playwright = subprocess.run(
        [sys.executable, "-c", "import playwright"],
        cwd=repo_root,
        capture_output=True
    )
    if check_playwright.returncode != 0:
        # install playwright
        subprocess.run(
            [sys.executable,"-m","pip","install","playwright"],
            cwd=repo_root,
            capture_output = True
        )
    subprocess.run(
            [sys.executable,"-m","playwright","install","chromium"],
            cwd=repo_root,
            capture_output = True
        )


def linting(repo_root: str) -> CheckResult:
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

    return CheckResult(errors=normalize_paths(result.stdout), status= result.returncode)

def type_check(repo_root: str) -> CheckResult:
    cache_dir = Path(repo_root) / ".mypy_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    stdout_report, stderr_report, exit_status = mypy.api.run([repo_root])
    return CheckResult(errors=normalize_paths(stdout_report), status=exit_status)

def run_tests(repo_root: str) -> CheckResult:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/",
        "-m","not integration",
        "--tb=short","-q"
        ],
        cwd=repo_root,
        capture_output = True,
        text = True
    )
    return CheckResult(errors=normalize_paths(result.stdout+result.stderr), status=result.returncode)

def check_for_blocker(repo_root: str) -> CheckResult:
    """Search all Python files in kgs_pipeline/ and tests/ for BLOCKER: comments."""
    blockers = []
    search_dirs = ["kgs_pipeline", "tests"]

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
def normalize_paths(errors: str) -> str:
    return errors.replace(repo_root + "/", "/").replace("kgs/", "/")

@tool
def run_evaluator() -> EvalResult:

    """ Evaluates the pipeline code for linting, type checking and test errors.
        Must be called only after
        1. coder-advanced has confirmed that code-writing is complete
        2. coder-basic has confirmed that code-fixing is complete
    """
    #ensure playwrigth is installed
    ensure_playwright(repo_root)
    # Gate 0 - coder blocked
    blocker_chk_response = check_for_blocker(repo_root)
    if blocker_chk_response["status"] == 2:
        blocker_msg = f"""Coder is blocked with the following errors.
        Human intervention needed to fix the errors and unblock the coder-
        errors - {blocker_chk_response['errors']}"""
        return EvalResult(passed= False,
                          blockers=blocker_msg,
                          failures={})

    # Gate 1 — quality checks & tests
    linting_response = linting(repo_root)
    type_check_response = type_check(repo_root)
    tests_response = run_tests(repo_root)
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

    return EvalResult(passed=passed, blockers="", failures=failures)
