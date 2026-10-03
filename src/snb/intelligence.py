"""Controlled intelligence provider boundary.
AI is optional. GitHub-derived text is untrusted data, provider responses are bounded and validated.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Protocol
from .explain import LLM, OpenAILLM, template_explanation
from .models import Recommendation

class IntelligenceError(Exception):
    """Provider configuration or execution failure."""

class IntelligenceProvider(Protocol):
    name: str
    def explain(self, recommendation: Recommendation) -> str: ...

@dataclass(frozen=True)
class OfflineProvider:
    name: str = "offline"
    def explain(self, recommendation: Recommendation) -> str:
        return template_explanation(recommendation)

@dataclass
class ValidatedProvider:
    provider: IntelligenceProvider
    max_chars: int = 2000
    @property
    def name(self) -> str:
        return self.provider.name
    def explain(self, recommendation: Recommendation) -> str:
        try:
            value = self.provider.explain(recommendation)
        except Exception as exc:
            raise IntelligenceError(f"{self.name} provider failed") from exc
        if not isinstance(value, str):
            raise IntelligenceError(f"{self.name} provider returned non-text output")
        value = value.strip()
        if not value:
            raise IntelligenceError(f"{self.name} provider returned empty output")
        if len(value) > self.max_chars:
            raise IntelligenceError(f"{self.name} provider output exceeded the limit")
        return value

@dataclass
class _AnthropicAdapter:
    client: LLM
    name: str = "anthropic"
    def explain(self, recommendation: Recommendation) -> str:
        return self.client.explain(recommendation)

@dataclass
class _OpenAIAdapter:
    client: OpenAILLM
    name: str = "openai"
    def explain(self, recommendation: Recommendation) -> str:
        return self.client.explain(recommendation)

def build_provider(provider: str | None, *, anthropic_key: str | None = None,
                   openai_key: str | None = None, anthropic_model: str | None = None,
                   openai_model: str | None = None) -> ValidatedProvider:
    selected = (provider or "offline").strip().lower()
    if selected == "offline":
        return ValidatedProvider(OfflineProvider())
    if selected == "anthropic":
        if not anthropic_key:
            raise IntelligenceError("ANTHROPIC_API_KEY is required for anthropic")
        return ValidatedProvider(_AnthropicAdapter(LLM(anthropic_key, anthropic_model)))
    if selected == "openai":
        if not openai_key:
            raise IntelligenceError("OPENAI_API_KEY is required for openai")
        return ValidatedProvider(_OpenAIAdapter(OpenAILLM(openai_key, openai_model)))
    raise IntelligenceError("unsupported intelligence provider")

def recommendation_payload(recommendation: Recommendation) -> str:
    data: dict[str, Any] = {
        "login": recommendation.login,
        "score": recommendation.score,
        "matched_domains": recommendation.matched_domains,
        "breakdown": recommendation.breakdown,
        "evidence": recommendation.evidence,
        "repositories": [
            {"name": r.get("name"), "stars": r.get("stars"), "language": r.get("language"),
             "description": str(r.get("description") or "")[:200]}
            for r in recommendation.matched_repos
        ],
    }
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
