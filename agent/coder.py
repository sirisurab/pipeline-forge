from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain.agents import create_agent
from agent.middleware import coder_limit_mw, retry_mw, coder_context_mw, choose_coder_model
from agent.tools import write_file, read_file, read_file_head, run_git
from agent.config import llm_coder_basic
from agent.state import State

coder_prompt = Path("coder.md").read_text()
coder_tools = [write_file, read_file, read_file_head, run_git]

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

coder_agent = create_agent(
    model=llm_coder_basic,
    tools=coder_tools,
    system_prompt=SystemMessage(
        content=coder_prompt,
        additional_kwargs={"cache_control": {"type": "ephemeral"}}
    ),
    middleware=[choose_coder_model, coder_context_mw, coder_limit_mw, retry_mw]
)
