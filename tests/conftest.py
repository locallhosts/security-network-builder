import pytest
from snb.config import Profile

PROFILE = {
    "name": "Test",
    "github_username": "me",
    "settings": {"preferred_languages": ["Go"], "min_stars": 1},
    "domains": {
        "ebpf": {"label": "eBPF", "weight": 10, "keywords": ["ebpf", "falco"], "search_queries": ["ebpf security"]},
        "detect": {"label": "Detection", "weight": 8, "keywords": ["sigma", "mitre attack"], "search_queries": ["sigma"]},
    },
}


@pytest.fixture
def profile():
    return Profile.from_dict(PROFILE)


def repo(name, desc="", topics=(), stars=0, lang=None, pushed="2026-09-01T00:00:00Z", fork=False, archived=False, owner="alice"):
    return {
        "name": name, "full_name": f"{owner}/{name}", "html_url": f"https://github.com/{owner}/{name}",
        "description": desc, "topics": list(topics), "stargazers_count": stars, "language": lang,
        "pushed_at": pushed, "fork": fork, "archived": archived,
        "owner": {"login": owner, "type": "User", "html_url": f"https://github.com/{owner}"},
    }
