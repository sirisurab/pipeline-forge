from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from agent.subagents import task_writer, coder_advanced, coder_basic
from langgraph.checkpoint.memory import MemorySaver
from agent.evaluator import run_evaluator
from agent.tools import commit_git
from agent.middleware import orchestrator_limit_mw, retry_mw
from pathlib import Path
import sys
from agent.config import repo_root, orchestrator_model
from langchain_anthropic import ChatAnthropic


def main(args):
    user_prompt = args[1]

    config = {"configurable":{"thread_id": args[2]}}
    result = graph.invoke({"messages":[{"role":"user", "content": user_prompt}]}, config)
    print(result)

_backend = FilesystemBackend(root_dir=repo_root, virtual_mode=True)
_checkpointer = MemorySaver()

_orchestrator_prompt = Path("orchestrator.md").read_text()

_main_agent = create_deep_agent(
    name="pipeline-builder",
    model=ChatAnthropic(model=orchestrator_model),
    system_prompt=_orchestrator_prompt,  # new — describes orchestration logic
    tools=[run_evaluator, commit_git],               # evaluator as a tool
    backend=_backend,
    subagents=[task_writer, coder_advanced, coder_basic],
    # uncomment for use when not using langgraph server
    # checkpointer=_checkpointer,
    interrupt_on={
        "commit_git": {"allowed_decisions": ["approve", "reject"]}
    },
    middleware = [orchestrator_limit_mw, retry_mw]
)

graph = _main_agent

if __name__ == "__main__":
    main(sys.argv)
