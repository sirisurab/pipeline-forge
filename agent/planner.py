from pathlib import Path
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage
from agent.middleware import planner_limit_mw, retry_mw
from agent.tools import write_file, read_file, read_file_head, run_git
from agent.config import llm_planner

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
                Planner has finished. TaskIndex.md and all component task files are
                written to kgs/tasks/. Your job is to implement code only.
                Read TaskIndex.md first, then implement each component's tasks in order.
                Write only: kgs_pipeline/*.py, tests/test_*.py, requirements.txt,
                README.md, Makefile, pytest.ini, mypy.ini, .gitignore.
                Do not write any documentation, architecture, or summary files.
                """, tool_call_id = runtime.tool_call_id)
            ], "eval_status": 0, "coder_level": "advanced"
        },
        graph = Command.PARENT
    )

planner_prompt = Path("planner.md").read_text()
planner_tools = [write_file, read_file, read_file_head, handoff_to_coder, run_git]

planner_agent = create_agent(
    model=llm_planner,
    tools=planner_tools,
    system_prompt=SystemMessage(
        content=planner_prompt,
        additional_kwargs={"cache_control": {"type": "ephemeral"}}
    ),
    middleware=[planner_limit_mw, retry_mw]
)

