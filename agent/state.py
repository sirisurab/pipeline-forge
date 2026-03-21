from langgraph.graph import MessagesState
from typing import Literal
from typing_extensions import NotRequired

class State(MessagesState):
    eval_status: int
    entry_point: NotRequired[Literal["planner", "coder", "evaluator"]]
    coder_level: NotRequired[Literal["basic", "advanced"]]
