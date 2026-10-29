"""
A pluggable LLM client interface, with three implementations:

- MockLLMClient: deterministic, costs $0, calls no external API. This
  is what CI and the test suite use -- the same reason SurplusBid's
  tests never called a real payment gateway and SiteWatch's tests use
  a real but local Postgres rather than a hosted one. The governance
  and tool-calling logic (the part this project is actually about) is
  fully exercised either way; only the "guess a diagnosis in English"
  step is swapped out.
- OpenAIClient / AnthropicClient: real implementations, used only when
  LLM_PROVIDER + LLM_API_KEY are explicitly set. Not used anywhere in
  this repo's CI, because no key is provisioned there -- documented
  honestly rather than silently stubbed out and left unmentioned.

Every implementation shares one contract: diagnose(prompt, context) ->
a plain-text diagnosis plus an estimated token count, so the caller
(governance.py) can log cost per call regardless of which provider
produced it.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Protocol

from opspilot.config import Settings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    provider: str


class LLMClient(Protocol):
    def diagnose(self, prompt: str, context: str) -> LLMResponse: ...


class MockLLMClient:
    """
    Deterministic stand-in: hashes the input to produce a stable,
    reproducible "diagnosis" rather than a random one, so tests that
    assert on behavior (not exact wording) stay stable across runs,
    and so re-running the same failure twice in CI produces the same
    proposal -- a property a real LLM call explicitly would NOT have,
    which is itself worth noting as a known difference from production
    behavior in the project docs.
    """

    provider_name = "mock"

    def diagnose(self, prompt: str, context: str) -> LLMResponse:
        time.sleep(0.01)  # stand in for real network latency in tests/metrics
        digest = hashlib.sha256((prompt + context).encode()).hexdigest()[:8]
        text = (
            f"[mock diagnosis {digest}] Likely cause inferred from the provided "
            f"context. This is a deterministic stand-in response used in CI and "
            f"tests -- see llm_client.py for why."
        )
        return LLMResponse(
            text=text,
            prompt_tokens=len(prompt.split()) + len(context.split()),
            completion_tokens=len(text.split()),
            provider=self.provider_name,
        )


class OpenAIClient:
    """Real implementation. Requires `pip install openai` and an API key; not exercised in this repo's CI."""

    provider_name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        import openai  # imported lazily so CI never needs this dependency installed

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def diagnose(self, prompt: str, context: str) -> LLMResponse:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ],
        )
        usage = resp.usage
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            provider=self.provider_name,
        )


class AnthropicClient:
    """Real implementation. Requires `pip install anthropic` and an API key; not exercised in this repo's CI."""

    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        import anthropic  # imported lazily so CI never needs this dependency installed

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def diagnose(self, prompt: str, context: str) -> LLMResponse:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=prompt,
            messages=[{"role": "user", "content": context}],
        )
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        return LLMResponse(
            text=text,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
            provider=self.provider_name,
        )


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "mock":
        return MockLLMClient()
    if settings.llm_provider == "openai":
        if not settings.llm_api_key:
            raise ValueError("LLM_PROVIDER=openai requires LLM_API_KEY")
        return OpenAIClient(settings.llm_api_key)
    if settings.llm_provider == "anthropic":
        if not settings.llm_api_key:
            raise ValueError("LLM_PROVIDER=anthropic requires LLM_API_KEY")
        return AnthropicClient(settings.llm_api_key)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")
