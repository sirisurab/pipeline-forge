from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRetryMiddleware, ModelRequest, ModelResponse, wrap_model_call, ContextEditingMiddleware, ClearToolUsesEdit  # noqa: E501
from agent.config import llm_coder_basic, llm_coder_advanced
from anthropic import RateLimitError, APIStatusError

def should_retry(error: Exception) -> bool:
    if isinstance(error, RateLimitError):
        return True
    if isinstance(error, APIStatusError):
        return getattr(error, 'status_code', 0) in (429, 529)
    return False

planner_limit_mw = ModelCallLimitMiddleware(
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

coder_context_mw = ContextEditingMiddleware(
    edits=[
        ClearToolUsesEdit(
            trigger=30000,       # fire when context hits 30k tokens
            keep=2,              # keep 2 most recent tool results
            clear_tool_inputs=True,  # also clear AIMessage tool_use blocks
            exclude_tools=[],
            placeholder="[cleared - file content no longer in context]",
        ),
    ],
)

@wrap_model_call
async def choose_coder_model(request: ModelRequest, handler) -> ModelResponse:
    """Choose model based on coder_level param. Defaults to basic model"""
    coder_level = request.state.get("coder_level","")
    if not coder_level or coder_level != "advanced":
        model = llm_coder_basic
    else:
        model = llm_coder_advanced
    return await handler(request.override(model=model))
