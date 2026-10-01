from snb.graph import build_graph
from snb.models import Recommendation
from snb.orgs import analyze_orgs


def rec(login, score, domains, orgs=()):
    return Recommendation(login, f"https://github.com/{login}", score, list(domains), {}, [], [], orgs=list(orgs))


RECS = [
    rec("a", 30, ["eBPF", "Detection"], ["cilium"]),
    rec("b", 25, ["eBPF", "Detection"], ["cilium"]),
    rec("c", 20, ["Cloud"], ["aws"]),
    rec("d", 18, ["Cloud"], ["aws"]),
    rec("loner", 10, ["AppSec"]),
]


def test_edges_merge_reasons():
    g = build_graph(RECS, {"cilium/tetragon": {"a", "b", "outsider"}})
    ab = next(e for e in g.edges if {e.a, e.b} == {"a", "b"})
    assert len(ab.reasons) == 3                      # co-contributor + shared org + shared domains
    assert ab.weight == 4 + 3 + 2
    assert all("outsider" not in (e.a, e.b) for e in g.edges)


def test_communities_and_centrality():
    g = build_graph(RECS)
    comm = {r.login: r.community for r in RECS}
    assert comm["a"] == comm["b"] and comm["c"] == comm["d"] and comm["a"] != comm["c"]
    assert comm["loner"] not in (comm["a"], comm["c"])
    assert RECS[4].centrality == 0.0 and RECS[0].centrality == 1.0
    assert {c["size"] for c in g.communities} == {2, 1}


def test_graph_is_deterministic():
    first = build_graph(RECS).to_dict()
    assert build_graph(list(reversed(RECS))).to_dict()["communities"] == first["communities"]


def test_empty_graph():
    assert build_graph([]).to_dict() == {"nodes": [], "edges": [], "communities": []}


def test_org_summary_ranks_shared_orgs_first():
    summary = analyze_orgs(RECS)
    assert summary[0]["login"] in {"cilium", "aws"} and len(summary[0]["members"]) == 2
    cilium = next(o for o in summary if o["login"] == "cilium")
    assert cilium["total_score"] == 55 and cilium["top_domains"][0] in {"eBPF", "Detection"}
