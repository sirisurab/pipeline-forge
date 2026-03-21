from dotenv import load_dotenv
import subprocess
import sys
from pathlib import Path
import mypy.api
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict, NotRequired
from typing import Literal
from langgraph.graph import MessagesState
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage, trim_messages
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain.agents import create_agent
from anthropic import RateLimitError, APIStatusError
from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRetryMiddleware, ModelRequest, ModelResponse, wrap_model_call, ContextEditingMiddleware, ClearToolUsesEdit
import shutil


# message classes
class EvalResponse(TypedDict):
    errors: str
    status: int

class State(MessagesState):
    eval_status: int
    entry_point: NotRequired[Literal["planner", "coder", "evaluator"]]
    coder_level: NotRequired[Literal["basic", "advanced"]]

# tools definitions
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

# utility functions
def linting(repo_root: str) -> EvalResponse:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check"],
        cwd=repo_root,
        capture_output=True, 
        text=True
    )
    return EvalResponse(errors=result.stdout, status= result.returncode)


def format_check(repo_root: str) -> EvalResponse:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check"],
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

def check_eval_status(state) -> Literal["coder_entry","human_checkpoint", "__end__"]:
    if state["eval_status"] == 2:      # BLOCKER found
        return "human_checkpoint"
    if state["eval_status"] == 1:      # eval failures
        return "coder_entry"
    return END


# factory functions for building nodes


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
        format_response = format_check(repo_root)
        tests_response = run_tests(repo_root)
        response = []
        eval_status = 0
        for check, label in [
            (linting_response, "Linting"),
            (type_check_response, "Type check"),
            (format_response, "Format check"),
            (tests_response, "Unit Tests")
        ]:
            if check["status"] != 0:
                response.append(HumanMessage(
                    content=f"{label} failed. Fix these errors:\n{check['errors']}"
                ))
                eval_status = 1
        
        return {"messages": response, "eval_status": eval_status, "coder_level": "basic"}
    return evaluate

def human_checkpoint(state):
    """Pause graph for human review of blocker or judge-rejected code.

    state : State
    Returns : State
    """
    # Build the message shown to the human
    eval_status = state["eval_status"]

    if eval_status == 2:
        display_msg = f"BLOCKER detected — human intervention required:\n\n{state['messages'][-1].content}"
    else:
        display_msg = f"Code review required. Judge feedback:\n\n{state['messages'][-1].content}"

    human_response = interrupt(display_msg)

    return {"messages": [HumanMessage(content=human_response)]}

def coder_entry(state: State) -> State:
    """ Function for coder_entry node
        This node trims all messages except 
        1. the last human message - if last message is human msg
        2. OR the last pair of messages (AI message + tool message) - if last message is tool msg
        This node preceeds the coder node in the graph and acts as a gateway to the coder
    """
    messages = state["messages"]
    coder_level = state.get("coder_level","basic")
    reverse_msgs_iter = reversed(messages)
    last_msg = next( 
        msg for msg in reverse_msgs_iter
        if isinstance(msg, (HumanMessage, ToolMessage)))
    if isinstance(last_msg, ToolMessage):
        pair_msg = next(
            msg for msg in reverse_msgs_iter
            if isinstance(msg, AIMessage)
            )
        return {"messages": [pair_msg, last_msg], "coder_level":coder_level}
    return {"messages": [last_msg], "coder_level":coder_level}

@tool
def handoff_to_coder(runtime: ToolRuntime) -> Command:
    """
    Hands-off to codr agent after planner agent is finished.
    Removes all messages from state except the last AI Message 
    and matches it with a ToolMessage, suitable for coder agent input

    Parameters:
    runtime: ToolRuntime
    Returns
    Command
    """
    last_ai_msg = next(
                m for m in reversed(runtime.state["messages"]) 
                if isinstance(m, AIMessage)
                )
    return Command(
        goto="coder",
        update = {
            "messages" : [
                last_ai_msg,
                ToolMessage(content="""
                Planner has finished writing TaskIndex.md and all component task files at tasks/*.md
                """, tool_call_id = runtime.tool_call_id)
            ], "eval_status": 0, "coder_level": "advanced"
        },
        graph = Command.PARENT
    )

@tool
def run_git(command: str) -> str:
    """
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
    """
    allowed_cmds = ["init","add","commit","status","diff"]
    cmd_parts = command.strip().split()
    if not cmd_parts or cmd_parts[0] not in allowed_cmds:
        return f"ERROR: Command not allowed. Permitted: {allowed_cmds}"
    result = subprocess.run(
        ["git"] + cmd_parts,
        cwd = _repo_root,
        capture_output = True,
        text = True
        )
    if result.returncode !=0:
        return f"ERROR: git {command} failed with {result.stderr}"
    return result.stdout or f"git {command} ran successfully"

def entry_router(state: State) -> Literal["planner", "coder",  "evaluator"]:
    entry_point = state.get("entry_point", "planner")
    if entry_point in ["planner", "coder", "evaluator"]:
        return entry_point
    return "planner"

def should_retry(error: Exception) -> bool:
    if isinstance(error, RateLimitError):
        return True
    if isinstance(error, APIStatusError):
        return getattr(error, 'status_code', 0) in (429, 529)
    return False

@wrap_model_call
async def choose_coder_model(request: ModelRequest, handler) -> ModelResponse:
    """Choose model based on coder_level param. Defaults to basic model"""
    coder_level = request.state.get("coder_level","")
    if not coder_level or coder_level != "advanced":
        model = _llm_coder_basic
    else:
        model = _llm_coder_advanced
    return await handler(request.override(model=model))

def main():
    
    for f in ["kgs/TaskIndex.md"]:
        p = Path(f)
        if p.exists():
            p.unlink()

    # Also clean the tasks directory
    tasks_dir = Path("kgs/tasks")
    if tasks_dir.exists():
        shutil.rmtree(tasks_dir)

    user_prompt = HumanMessage(content="""Write a data pipeline to acquire, ingest, clean and process 
                               the KGS oil production data for 2020-2025. 
                               The pipeline must use parallel processing techniques. 
                               The processed files need to be ready for feature extraction 
                               and input to a Machine Learning and Analytics workflow.
                               """)
    
    config = {"configurable":{"thread_id": 1}}
    result = graph.invoke({"messages":[user_prompt], 
                            "eval_status": 0, 
                            "entry_point": "planner",
                            "coder_level": "advanced"}, config)
    print(result)

    # Loop to handle interrupts
    while True:
        # Check if graph paused on an interrupt
        # LangGraph surfaces interrupt values in result as a list
        if "__interrupt__" in result:
            interrupt_value = result["__interrupt__"][0].value
            print("\n" + "="*60)
            print("GRAPH PAUSED — HUMAN INPUT REQUIRED")
            print("="*60)
            print(interrupt_value)
            print("="*60)
            
            # Capture your response from the terminal
            human_input = input("\nYour response (press Enter twice when done):\n")
            
            # Resume the graph
            result = graph.invoke(
                Command(resume=human_input),
                config=config
            )
        else:
            # No interrupt — graph ran to completion
            print("Graph completed.")
            break

load_dotenv()
_llm_coder_advanced = ChatAnthropic(model="claude-sonnet-4-6")
_llm_coder_basic = ChatAnthropic(model="claude-haiku-4-5-20251001")
_llm_planner = ChatAnthropic(model="claude-sonnet-4-6")

_planner_limit_mw = ModelCallLimitMiddleware(
    run_limit=50,
    exit_behavior="end"
)

_coder_limit_mw = ModelCallLimitMiddleware(
    run_limit=80,
    exit_behavior="end"
)

_retry_mw = ModelRetryMiddleware(
    max_retries=5,
    retry_on=should_retry,
    initial_delay=30.0,
    backoff_factor=2.0,
    max_delay=300.0,
    on_failure="error"
)

_coder_context_mw = ContextEditingMiddleware(
    edits=[
        ClearToolUsesEdit(
            trigger=30000,       # fire when context hits 30k tokens
            keep=2,              # keep 2 most recent tool results
            clear_tool_inputs=True,  # also clear AIMessage tool_use blocks
            exclude_tools=[],  
            placeholder="[cleared - file content no longer in context]",
        ),
    ],
)

_repo_root = str(Path.cwd() / "kgs")
_planner_prompt = Path("planner.md").read_text()
_coder_prompt = Path("coder.md").read_text()
#_tests_dir = _repo_root+"/tests"
_builder = StateGraph(State)

_planner_tools = [write_file, read_file, read_file_head, handoff_to_coder]
_coder_tools = [write_file, read_file, read_file_head, run_git]
planner_agent = create_agent(
    model=_llm_planner,
    tools=_planner_tools,
    system_prompt=SystemMessage(
        content=_planner_prompt,
        additional_kwargs={"cache_control": {"type": "ephemeral"}}
    ),
    middleware=[_planner_limit_mw, _retry_mw]
)
coder_agent = create_agent(
    model=_llm_coder_basic,
    tools=_coder_tools,
    system_prompt=SystemMessage(
        content=_coder_prompt,
        additional_kwargs={"cache_control": {"type": "ephemeral"}}
    ),
    middleware=[choose_coder_model, _coder_context_mw, _coder_limit_mw, _retry_mw]
)
_builder.add_node("planner", planner_agent)
_builder.add_node("coder_entry", coder_entry)
_builder.add_node("coder", coder_agent)
_builder.add_node("human_checkpoint", human_checkpoint)
_builder.add_node("evaluator", make_eval_node(_repo_root))

# _builder.add_edge(START, "planner")
_builder.add_conditional_edges(
    START,
    entry_router,
    {
        "planner":"planner",
        "coder":"coder_entry",
        "evaluator": "evaluator"
    }
)
_builder.add_edge("coder_entry", "coder")

_builder.add_edge("coder", "evaluator")

_builder.add_conditional_edges(
                    "evaluator", 
                    check_eval_status,
                    {
                        "coder_entry":"coder_entry",
                        "human_checkpoint":"human_checkpoint",
                        "__end__":END
                    })
_builder.add_edge("human_checkpoint", "coder_entry")

checkpointer = MemorySaver()
graph = _builder.compile()

if __name__ == "__main__":
    main()
