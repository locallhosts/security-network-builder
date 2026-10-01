"""Profile loading, validation and keyword matching."""
from __future__ import annotations

import os
import re
from importlib import resources
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def load_env(path: str = ".env") -> None:
    """Minimal .env loader (no extra dependency). Existing env vars win."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


LOCAL_PROFILE = Path("profiles/security_profile.yaml")


def read_profile_text(path: str | Path | None = None) -> str:
    """Explicit path > ./profiles/security_profile.yaml > the profile bundled with the package."""
    if path:
        return Path(path).read_text(encoding="utf-8")
    if LOCAL_PROFILE.is_file():
        return LOCAL_PROFILE.read_text(encoding="utf-8")
    return resources.files("snb").joinpath("default_profile.yaml").read_text(encoding="utf-8")


def normalize(text: str | None) -> str:
    """Lowercase and turn separators into spaces so 'mitre-attack' == 'mitre attack'."""
    return re.sub(r"[-_/.]+", " ", (text or "").lower())


def compile_keyword(keyword: str) -> re.Pattern[str]:
    tokens = normalize(keyword).split()
    if not tokens:
        raise ValueError("empty keyword")
    body = r"\s+".join(re.escape(t) for t in tokens)
    return re.compile(rf"(?<![a-z0-9]){body}(?:s)?(?![a-z0-9])")


@dataclass
class Domain:
    key: str
    label: str
    weight: float
    keywords: list[str]
    search_queries: list[str]
    _patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._patterns = [(kw, compile_keyword(kw)) for kw in self.keywords]

    def match(self, text: str) -> set[str]:
        return {kw for kw, pat in self._patterns if pat.search(text)}


@dataclass
class Settings:
    min_stars: int = 5
    active_within_days: int = 365
    results_per_query: int = 30
    max_candidates: int = 30
    max_repos_per_user: int = 100
    users_only: bool = True
    include_forks: bool = False
    preferred_languages: list[str] = field(default_factory=list)
    exclude_users: list[str] = field(default_factory=list)


@dataclass
class Profile:
    name: str
    github_username: str
    domains: list[Domain]
    settings: Settings

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        raw_domains = data.get("domains") or {}
        if not raw_domains:
            raise ValueError("profile must define at least one domain")
        domains = []
        for key, d in raw_domains.items():
            if not d.get("keywords"):
                raise ValueError(f"domain '{key}' needs at least one keyword")
            domains.append(
                Domain(
                    key=key,
                    label=d.get("label", key),
                    weight=float(d.get("weight", 5)),
                    keywords=list(d["keywords"]),
                    search_queries=list(d.get("search_queries", [])),
                )
            )
        known = set(Settings.__dataclass_fields__)
        unknown = set(data.get("settings") or {}) - known
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
        return cls(
            name=data.get("name", "Security Profile"),
            github_username=(data.get("github_username") or "").strip(),
            domains=domains,
            settings=Settings(**(data.get("settings") or {})),
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Profile":
        return cls.from_dict(yaml.safe_load(read_profile_text(path)) or {})

    def match_repo(self, repo: dict[str, Any]) -> dict[str, set[str]]:
        """Return {domain_key: matched_keywords} for one repository."""
        text = normalize(
            " ".join(
                [repo.get("name") or "", repo.get("description") or "", " ".join(repo.get("topics") or [])]
            )
        )
        hits = {}
        for domain in self.domains:
            matched = domain.match(text)
            if matched:
                hits[domain.key] = matched
        return hits
