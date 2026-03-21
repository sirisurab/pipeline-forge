from pathlib import Path
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
import shutil
from agent.state import State
from agent.evaluator import make_eval_node
from agent.human_in_loop import human_checkpoint
from agent.edges import entry_router, check_eval_status
from agent.config import repo_root
from agent.coder import coder_agent, coder_entry
from agent.planner import planner_agent

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
                               """)  # noqa: E501

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


#_tests_dir = repo_root+"/tests"
_builder = StateGraph(State)


_builder.add_node("planner", planner_agent)
_builder.add_node("coder_entry", coder_entry)
_builder.add_node("coder", coder_agent)
_builder.add_node("human_checkpoint", human_checkpoint)
_builder.add_node("evaluator", make_eval_node(repo_root))

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
