from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

def human_checkpoint(state):
    """Pause graph for human review of blocker or judge-rejected code.

    state : State
    Returns : State
    """
    # Build the message shown to the human
    eval_status = state["eval_status"]

    if eval_status == 2:
        display_msg = f"BLOCKER detected — human intervention required:\n\n{state['messages'][-1].content}"  # noqa: E501
    else:
        display_msg = f"Code review required. Judge feedback:\n\n{state['messages'][-1].content}"

    human_response = interrupt(display_msg)

    return {"messages": [HumanMessage(content=human_response)]}
