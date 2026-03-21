from typing_extensions import TypedDict
import sys
import subprocess
from pathlib import Path
import mypy.api
from langchain_core.messages import HumanMessage

class EvalResponse(TypedDict):
    errors: str
    status: int

# utility functions
def linting(repo_root: str) -> EvalResponse:
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

    return EvalResponse(errors=result.stdout, status= result.returncode)

def type_check(repo_root: str) -> EvalResponse:
    stdout_report, stderr_report, exit_status = mypy.api.run([repo_root])
    return EvalResponse(errors=stdout_report, status=exit_status)

def run_tests(repo_root: str) -> EvalResponse:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/",
        "-m","not integration",
        "--tb=short","-q"
        ],
        cwd=repo_root,
        capture_output = True,
        text = True
    )
    return EvalResponse(errors=result.stdout+result.stderr, status=result.returncode)

def check_for_blocker(repo_root: str) -> EvalResponse:
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
        return EvalResponse(
            errors="\n".join(blockers),
            status=2  # distinct from regular eval failure (1)
        )
    return EvalResponse(errors="", status=0)

# factory function for building node
def make_eval_node(repo_root: str):
    def evaluate(state):
        """ evaluates code based on the eval tools provided
            state : MessagesState
            Returns
            MessagesState
        """
        # Gate 0 - coder blocked
        blocker_chk_response = check_for_blocker(repo_root)
        if blocker_chk_response["status"] == 2:
            msg = HumanMessage(content=f"""Coder is blocked with the following errors.
            Human intervention needed to fix the errors and unblock the coder-
            errors - {blocker_chk_response['errors']}""")
            eval_status = 2
            return {"messages": [msg], "eval_status": eval_status, "coder_level": "basic"}

        # Gate 1 — quality checks & tests
        linting_response = linting(repo_root)
        type_check_response = type_check(repo_root)
        tests_response = run_tests(repo_root)
        response = []
        eval_status = 0
        for check, label in [
            (linting_response, "Linting"),
            (type_check_response, "Type check"),
            (tests_response, "Unit Tests")
        ]:
            if check["status"] != 0:
                response.append(HumanMessage(
                    content=f"{label} failed. Fix these errors:\n{check['errors']}"
                ))
                eval_status = 1

        return {"messages": response, "eval_status": eval_status, "coder_level": "basic"}
    return evaluate
