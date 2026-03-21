from pathlib import Path
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage
from agent.middleware import planner_limit_mw, retry_mw
from agent.tools import write_file, read_file, read_file_head
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
                Planner has finished writing TaskIndex.md and all component task files at tasks/*.md
                """, tool_call_id = runtime.tool_call_id)
            ], "eval_status": 0, "coder_level": "advanced"
        },
        graph = Command.PARENT
    )

planner_prompt = Path("planner.md").read_text()
planner_tools = [write_file, read_file, read_file_head, handoff_to_coder]

planner_agent = create_agent(
    model=llm_planner,
    tools=planner_tools,
    system_prompt=SystemMessage(
        content=planner_prompt,
        additional_kwargs={"cache_control": {"type": "ephemeral"}}
    ),
    middleware=[planner_limit_mw, retry_mw]
)

