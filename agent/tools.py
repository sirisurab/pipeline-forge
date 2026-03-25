# tools definitions

from pathlib import Path
import subprocess
from langchain.tools import tool
from agent.config import repo_root


@tool
def stage_and_check_git(command: str) -> str:
    """
    IMPORTANT: Only call this tool at the end of a coding or task-writing run,
    after you are finished creating or editing all the files in that run,
    and before returning to the main orchestrating agent.
    Stage all files changed in the run at one go.

    Execute git-cli commands to, (only following commands are allowed)
    1. `git init` - to initiate the repo once in the beginning
    2. `git add <specific files> - add specific changed files to git staging
    3. `git status` - check status of files untracked, modified and staged files
    4. `git diff` - check difference between changes
    Params:
    command : str  - the command like `git add kgs_pipeline/acquire.py kgs_pipeline/ingest.py`

    Returns:
    Error message if command is not allowed or if git command fails
    Output of git command if it succeeds
    """
    allowed_cmds = ["init","add", "status","diff"]
    result = run_git(command, allowed_cmds=allowed_cmds)
    return result

@tool
def commit_git(comment: str) -> str:
    """
    IMPORTANT: Only call this tool at the end of an orchestration run,
    after the evaluator returns passed=True with no blockers or failures.
    All files changed in a succsesful orchestration run should be commited at one go.
    (where success is determined by evaluator returns passsed=True)

    Execute git-cli commands to, (only commit command is allowed)
    1. `git commit -m <meaningful comment describing changes in the tested run>` - commits changes for a successfully tested run

    Params:
    comment : str  - the meaningful comment for the git commit command eg. `all unit tests passed`

    Returns:
    Error message if command is not allowed or if git command fails
    Output of git command if it succeeds
    """  # noqa: E501

    result = subprocess.run(
        ["git", "commit", "-m", comment],  # ← pass as list, not string
        cwd=repo_root,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return f"ERROR: git commit failed with {result.stderr}"
    return result.stdout or "git commit ran successfully"

def run_git(command: str, allowed_cmds: list[str]) -> str:
    """
    Internal helper, not a @tool

    Execute git command if in allowed commands
    Params:
    command : str
    allowed_cmds : list[str]
    Returns:
    Error message if command is not allowed or if git command fails
    Output of git command if it succeeds
    """
    cmd_parts = command.strip().split()
    if cmd_parts and cmd_parts[0] == "git" and len(cmd_parts) > 1:
        cmd_parts = cmd_parts[1:]
    if not cmd_parts or cmd_parts[0] not in allowed_cmds:
        return f"ERROR: Command not allowed. Permitted: {allowed_cmds}"
    result = subprocess.run(
        ["git"] + cmd_parts,
        cwd = repo_root,
        capture_output = True,
        text = True
        )
    if result.returncode !=0:
        return f"ERROR: git {command} failed with {result.stderr}"
    return result.stdout or f"git {command} ran successfully"
