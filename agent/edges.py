from typing import Literal
from agent.state import State
from langgraph.graph import END

def check_eval_status(state) -> Literal["coder_entry","human_checkpoint", "__end__"]:
    if state["eval_status"] == 2:      # BLOCKER found
        return "human_checkpoint"
    if state["eval_status"] == 1:      # eval failures
        return "coder_entry"
    return END

def entry_router(state: State) -> Literal["planner", "coder",  "evaluator"]:
    entry_point = state.get("entry_point", "planner")
    if entry_point in ["planner", "coder", "evaluator"]:
        return entry_point
    return "planner"
