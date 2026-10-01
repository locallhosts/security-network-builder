from datetime import datetime, timezone

from conftest import repo
from snb.discovery import build_query, discover


class FakeClient:
    def __init__(self, results):
        self.results = results
        self.queries = []

    def search_repositories(self, query, per_page=30, sort="stars"):
        self.queries.append(query)
        return self.results


def test_build_query_adds_filters(profile):
    q = build_query("ebpf security", profile, datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert "in:name,description,topics" in q
    assert "fork:false" in q and "archived:false" in q
    assert "pushed:>2025-09-01" in q


def test_topic_query_skips_in_qualifier(profile):
    assert "in:name" not in build_query("topic:ebpf", profile)


def test_discover_groups_and_filters(profile):
    org = repo("o", "ebpf", owner="bigcorp")
    org["owner"]["type"] = "Organization"
    client = FakeClient([repo("a", "ebpf", owner="alice"), repo("b", "ebpf", owner="alice"), org, repo("c", "ebpf", owner="me")])
    found = discover(client, profile)
    assert list(found) == ["alice"]                     # org and self excluded
    assert len(found["alice"].seed_repos) >= 2
    assert len(client.queries) == 2                     # one query per domain in test profile


def test_queries_per_domain_limit(profile):
    client = FakeClient([])
    discover(client, profile, queries_per_domain=0)
    assert client.queries == []
