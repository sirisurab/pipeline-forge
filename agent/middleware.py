from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRetryMiddleware
from anthropic import RateLimitError, APIStatusError, APITimeoutError
from deepagents.middleware.summarization import SummarizationMiddleware, SummarizationToolMiddleware
from deepagents.backends import FilesystemBackend
from agent.config import repo_root, summarization_model
from langchain_anthropic import ChatAnthropic
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from openai import RateLimitError as OpenAIRateLimitError
from openai import APITimeoutError as OpenAITimeoutError
from openai import APIStatusError as OpenAIStatusError

backend = FilesystemBackend(root_dir=repo_root, virtual_mode=True)

class CoderSummarizationMiddleware(SummarizationMiddleware):
    name = "CoderSummarizationMiddleware"

summarization_mw = CoderSummarizationMiddleware(
    model=ChatAnthropic(model=summarization_model, timeout=300),
    backend=backend,
    trigger=("fraction", 0.85),
    keep=("fraction", 0.10),
)
summ_tool_mw = SummarizationToolMiddleware(summarization_mw)

def should_retry(error: Exception) -> bool:
    if isinstance(error, RateLimitError):
        return True
    if isinstance(error, APITimeoutError):
        return True
    if isinstance(error, APIStatusError):
        return getattr(error, 'status_code', 0) in (429, 529)

    # Google (Gemini) — ResourceExhausted is 429, ServiceUnavailable is 503
    if isinstance(error, (ResourceExhausted, ServiceUnavailable)):
        return True

    # OpenAI-compatible (DeepSeek)
    if isinstance(error, (OpenAIRateLimitError, OpenAITimeoutError)):
        return True
    if isinstance(error, OpenAIStatusError):
        return getattr(error, 'status_code', 0) in (429, 503, 529)

    return False

task_writer_limit_mw = ModelCallLimitMiddleware(
    run_limit=50,
    exit_behavior="end"
)

orchestrator_limit_mw = ModelCallLimitMiddleware(
    run_limit=50,
    exit_behavior="end"
)

coder_limit_mw = ModelCallLimitMiddleware(
    run_limit=80,
    exit_behavior="end"
)

retry_mw = ModelRetryMiddleware(
    max_retries=5,
    retry_on=should_retry,
    initial_delay=30.0,
    backoff_factor=2.0,
    max_delay=300.0,
    on_failure="error"
)
