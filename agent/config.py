from dotenv import load_dotenv
from pathlib import Path
from langchain_anthropic import ChatAnthropic

load_dotenv()
llm_coder_advanced = ChatAnthropic(model="claude-sonnet-4-6")
llm_coder_basic = ChatAnthropic(model="claude-haiku-4-5-20251001")
llm_planner = ChatAnthropic(model="claude-sonnet-4-6")

repo_root = str(Path.cwd() / "kgs")
