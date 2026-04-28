from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()
project = os.environ.get("PROJECT", "kgs")
orchestrator_model = "claude-sonnet-4-6"
task_writer_model = "claude-sonnet-4-6"
coder_advanced_model = "claude-sonnet-4-6"
coder_basic_model = "claude-haiku-4-5-20251001"
summarization_model = "claude-haiku-4-5-20251001"

repo_root = str(Path.cwd() / project)
