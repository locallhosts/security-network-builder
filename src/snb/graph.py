"""Relationship graph between engineers (stdlib only).

Edges (merged into one weighted edge per pair):
  co-contributor  both contribute to the same repository          weight 4
  shared-org      both are public members of the same org          weight 3 per org
  shared-domain   they match 2+ of the same security domains       weight 1 per domain

Metrics: weighted degree centrality (who is most connected) and communities
(deterministic label propagation, so identical input gives identical output).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from .models import Recommendation

W_CO_CONTRIBUTOR = 4.0
W_SHARED_ORG = 3.0
W_SHARED_DOMAIN = 1.0
MIN_SHARED_DOMAINS = 2


@dataclass
class Edge:
    a: str
    b: str
    weight: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class Graph:
    nodes: list[dict[str, Any]]
    edges: list[Edge]
    communities: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": [{"a": e.a, "b": e.b, "weight": e.weight, "reasons": e.reasons} for e in self.edges],
            "communities": self.communities,
        }


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def build_graph(recs: list[Recommendation], co_contributors: dict[str, set[str]] | None = None) -> Graph:
    """Build the graph, and write community/centrality back onto each recommendation."""
    by_login = {r.login: r for r in recs}
    edges: dict[tuple[str, str], Edge] = {}

    def add(a: str, b: str, weight: float, reason: str) -> None:
        key = _pair(a, b)
        edge = edges.setdefault(key, Edge(key[0], key[1]))
        edge.weight += weight
        edge.reasons.append(reason)

    for repo, logins in (co_contributors or {}).items():
        for a, b in combinations(sorted(l for l in logins if l in by_login), 2):
            add(a, b, W_CO_CONTRIBUTOR, f"both contribute to {repo}")

    # Index shared attributes first instead of comparing every possible pair.
    # This keeps sparse large graphs close to O(N + E) for relationship discovery.
    org_members: dict[str, list[str]] = {}
    domain_members: dict[str, list[str]] = {}
    for login, rec in by_login.items():
        for org in set(rec.orgs):
            org_members.setdefault(org, []).append(login)
        for domain in set(rec.matched_domains):
            domain_members.setdefault(domain, []).append(login)

    for org, members in sorted(org_members.items()):
        for a, b in combinations(sorted(members), 2):
            add(a, b, W_SHARED_ORG, f"both in org {org}")

    shared_domain_counts: Counter[tuple[str, str]] = Counter()
    for domain, members in sorted(domain_members.items()):
        for a, b in combinations(sorted(members), 2):
            shared_domain_counts[(a, b)] += 1
    for (a, b), count in sorted(shared_domain_counts.items()):
        if count >= MIN_SHARED_DOMAINS:
            add(a, b, W_SHARED_DOMAIN * count, f"{count} shared domains")

    adjacency: dict[str, dict[str, float]] = {l: {} for l in by_login}
    for e in edges.values():
        adjacency[e.a][e.b] = e.weight
        adjacency[e.b][e.a] = e.weight

    degree = {l: sum(nb.values()) for l, nb in adjacency.items()}
    max_degree = max(degree.values(), default=0) or 1
    labels = _label_propagation(adjacency)

    # Renumber communities by size (largest = 0)
    sizes = Counter(labels.values())
    order = {label: i for i, (label, _) in enumerate(sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0])))}
    communities = []
    for label, i in order.items():
        members = sorted((l for l, lab in labels.items() if lab == label), key=lambda l: -by_login[l].score)
        domains = Counter(d for l in members for d in by_login[l].matched_domains)
        communities.append(
            {"id": i, "size": len(members), "members": members, "top_domain": domains.most_common(1)[0][0] if domains else ""}
        )
    communities.sort(key=lambda c: c["id"])

    for login, rec in by_login.items():
        rec.community = order[labels[login]]
        rec.centrality = round(degree[login] / max_degree, 2)

    nodes = [
        {"login": r.login, "score": r.score, "community": r.community, "centrality": r.centrality}
        for r in recs
    ]
    return Graph(nodes=nodes, edges=sorted(edges.values(), key=lambda e: -e.weight), communities=communities)


def _label_propagation(adjacency: dict[str, dict[str, float]], max_iter: int = 20) -> dict[str, int]:
    nodes = sorted(adjacency)
    labels = {n: i for i, n in enumerate(nodes)}
    for _ in range(max_iter):
        changed = False
        for n in nodes:
            if not adjacency[n]:
                continue
            tally: Counter[int] = Counter()
            for nb, w in adjacency[n].items():
                tally[labels[nb]] += w
            best = max(tally.items(), key=lambda kv: (kv[1], -kv[0]))[0]  # ties -> smallest label
            if best != labels[n]:
                labels[n] = best
                changed = True
        if not changed:
            break
    return labels
