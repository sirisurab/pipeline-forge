# eval/groq_judge.py
# Groq LLM wrapper for DeepEval.
# Groq is OpenAI-compatible — we use the openai client pointed at Groq's base URL.

import os
from openai import OpenAI, AsyncOpenAI
from deepeval.models.base_model import DeepEvalBaseLLM

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = 0):
        self.model = model
        self.temperature = temperature
        self._client = OpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url=GROQ_BASE_URL,
        )
        self._async_client = AsyncOpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url=GROQ_BASE_URL,
        )

    def get_model_name(self) -> str:
        return f"groq/{self.model}"

    def load_model(self):
        # No model loading needed — Groq is a remote API
        return self._client

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        response = await self._async_client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
