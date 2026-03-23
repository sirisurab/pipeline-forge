from pathlib import Path
from agent.tools import stage_and_check_git
from agent.middleware import task_writer_limit_mw, coder_limit_mw, retry_mw
from agent.config import task_writer_model, coder_advanced_model, coder_basic_model
from langchain_anthropic import ChatAnthropic


task_writer_prompt = Path("task-writer.md").read_text()
coder_advanced_prompt = Path("coder-advanced.md").read_text()
coder_basic_prompt = Path("coder-basic.md").read_text()

# task-writer
task_writer = {
    "name": "task-writer",
    "description": ("""
        Writes detailed coding task specifications for each pipeline component.
        Use when the problem statement has been understood and task specs need
        to be written. Returns a summary of files written.
    """),
    "system_prompt": task_writer_prompt,
    "tools": [stage_and_check_git],
    "model": ChatAnthropic(model=task_writer_model),
    "middleware" : [task_writer_limit_mw, retry_mw]
}

# coder-advanced
coder_advanced = {
    "name": "coder-advanced",
    "description": ("""
        Implements the full pipeline from task specs. Use for the initial
        implementation run when no code exists yet. Writes all pipeline modules
        and test files. Returns a summary of files written.
    """),
    "system_prompt": coder_advanced_prompt,
    "tools": [stage_and_check_git],
    "model": ChatAnthropic(model=coder_advanced_model),
    "middleware" : [coder_limit_mw, retry_mw]
}

# coder-basic
coder_basic = {
    "name": "coder-basic",
    "description": ("""
        Applies targeted fixes to specific files based on evaluator error messages.
        Use when run_evaluator returns failures. Pass exact file paths and errors.
        Returns a summary of fixes applied.
    """),
    "system_prompt": coder_basic_prompt,
    "tools": [stage_and_check_git],
    "model": ChatAnthropic(model=coder_basic_model),
    "middleware" : [coder_limit_mw, retry_mw]
}
