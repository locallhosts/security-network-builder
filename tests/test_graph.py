from snb.graph import build_graph
from snb.models import Recommendation


def rec(login, domains=None, orgs=None, score=10):
    return Recommendation(
        login=login,
        url=f"https://github.com/{login}",
        score=float(score),
        matched_domains=domains or [],
        breakdown={},
        evidence=[],
        matched_repos=[],
        orgs=orgs or [],
    )


def test_shared_two_domains_create_evidence_backed_edge():
    graph = build_graph([
        rec("alice", ["Cloud Security", "eBPF"], ["AcmeSec"], 20),
        rec("bob", ["Cloud Security", "eBPF"], ["OtherSec"], 10),
        rec("carol", ["Cloud Security"], ["OtherSec"], 8),
    ])

    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert {edge.a, edge.b} == {"alice", "bob"}
    assert edge.weight == 2.0
    assert edge.reasons == ["2 shared domains"]


def test_shared_single_domain_does_not_create_relationship():
    graph = build_graph([
        rec("alice", ["Cloud Security"]),
        rec("bob", ["Cloud Security"]),
    ])

    assert graph.edges == []


def test_shared_org_creates_relationship_with_explicit_reason():
    graph = build_graph([
        rec("alice", ["Cloud Security"], ["AcmeSec"]),
        rec("bob", ["eBPF"], ["AcmeSec"]),
    ])

    assert len(graph.edges) == 1
    assert graph.edges[0].weight == 3.0
    assert graph.edges[0].reasons == ["both in org AcmeSec"]


def test_contributor_relationship_is_merged_with_other_evidence():
    graph = build_graph(
        [
            rec("alice", ["Cloud Security"], score=20),
            rec("bob", ["eBPF"], score=10),
        ],
        co_contributors={"acme/security-tool": {"alice", "bob"}},
    )

    assert len(graph.edges) == 1
    assert graph.edges[0].weight == 4.0
    assert graph.edges[0].reasons == ["both contribute to acme/security-tool"]
