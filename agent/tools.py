# tools definitions

from pathlib import Path
import subprocess
from langchain.tools import tool
from agent.config import repo_root


# file read and write tools
@tool
def write_file(filepath: str, content: str) -> str:
    """Write content to a file at the given path."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    Path(filepath).write_text(content)
    return f"Written to {filepath}"

@tool
def read_file(filepath: str) -> str:
    """Read content from a file. Raises an error if file exceeds 1MB."""
    p = Path(filepath)
    if not p.exists():
        return f"ERROR: {filepath} does not exist. Check TaskIndex.md for the correct filename."
    if p.is_dir():
        return f"ERROR: {filepath} is a directory, not a file. Specify a file path."

    if p.stat().st_size > 1_000_000:
        return (
            f"ERROR: {filepath} is too large to read in full "
            f"({p.stat().st_size:,} bytes). "
            f"Use read_file_head to preview the first few lines instead."
        )
    return p.read_text()

@tool
def read_file_head(filepath: str, n_lines: int = 10) -> str:
    """Read the first n lines of a file. Use for previewing large data files."""
    p = Path(filepath)
    if not p.exists():
        return f"ERROR: file {filepath} does not exist"
    if p.is_dir():
        return f"ERROR: {filepath} is a directory not a file"

    lines = p.read_text().splitlines()
    return "\n".join(lines[:n_lines])

@tool
def run_git(command: str) -> str:
    """
    IMPORTANT: Only call this tool when a HumanMessage explicitly
    contains the word 'commit' or 'version'. Do not call autonomously.

    Executes git-cli commands to
    1. `git init` - to initiate the repo once in the beginning
    2. `git add <specific changed files>` - to add files that have changed
    3. `git commit -m "<comment>"` - commits changes with a short but meaningful comment describing the changes

    Do not run `git pull`, `git push`, `git rm` and other destructive commands.
    Do not run `git add .`

    Params:
    command : str  - the command like `git commit -m "fixed datetime error"`

    Returns:
    Error message if command is not allowed or if git command fails
    Output of git command if it succeeds
    """  # noqa: E501
    allowed_cmds = ["init","add","commit","status","diff"]
    cmd_parts = command.strip().split()
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
