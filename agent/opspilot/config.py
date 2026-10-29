"""
Settings, all sourced from environment variables -- nothing here is
hardcoded, because this config object is used identically in local
dev, CI (where it's deliberately given no real LLM key, see
llm_client.py), and a real deployment.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    target_repo: str  # "owner/repo" -- the repo this agent watches
    llm_api_key: str | None
    llm_provider: str  # "mock" | "openai" | "anthropic"
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            github_token=os.environ.get("GITHUB_TOKEN"),
            target_repo=os.environ.get("TARGET_REPO", ""),
            llm_api_key=os.environ.get("LLM_API_KEY"),
            # Defaults to "mock" on purpose: this agent should never
            # silently fall back to calling a real, billed LLM API
            # just because a key happened to be present in the
            # environment it was started in -- the provider has to be
            # explicitly chosen.
            llm_provider=os.environ.get("LLM_PROVIDER", "mock"),
            port=int(os.environ.get("PORT", "8000")),
        )


settings = Settings.from_env()
