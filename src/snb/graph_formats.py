"""Deterministic graph snapshot serialization for interoperability."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


def _normalized(graph: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = sorted(graph.get("nodes", []), key=lambda n: str(n.get("login", "")))
    edges = []
    for edge in graph.get("edges", []):
        a, b = str(edge.get("a", "")), str(edge.get("b", ""))
        if b < a:
            a, b = b, a
        edges.append({**edge, "a": a, "b": b})
    edges.sort(key=lambda e: (str(e.get("a", "")), str(e.get("b", "")), float(e.get("weight", 0))))
    return nodes, edges


def to_edge_list(graph: dict[str, Any]) -> str:
    _, edges = _normalized(graph)
    lines = ["source	target	weight"]
    lines.extend(
        f"{e.get('a','')}\t{e.get('b','')}\t{float(e.get('weight', 0)):g}"
        for e in edges
    )
    return "\n".join(lines) + "\n"


def to_graphml(graph: dict[str, Any]) -> str:
    nodes, edges = _normalized(graph)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="score" for="node" attr.name="score" attr.type="double"/>',
        '<key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
        '<graph id="security-network" edgedefault="undirected">',
    ]
    for node in nodes:
        login = escape(str(node.get("login", "")))
        lines.append(f'<node id="{login}"><data key="score">{float(node.get("score", 0)):g}</data></node>')
    for index, edge in enumerate(edges):
        a, b = escape(str(edge.get("a", ""))), escape(str(edge.get("b", "")))
        lines.append(f'<edge id="e{index}" source="{a}" target="{b}"><data key="weight">{float(edge.get("weight", 0)):g}</data></edge>')
    lines.extend(["</graph>", "</graphml>"])
    return "\n".join(lines) + "\n"


def to_gexf(graph: dict[str, Any]) -> str:
    nodes, edges = _normalized(graph)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">',
        '<graph mode="static" defaultedgetype="undirected">',
        "<nodes>",
    ]
    for node in nodes:
        login = escape(str(node.get("login", "")))
        lines.append(f'<node id="{login}" label="{login}"/>')
    lines.append("</nodes>")
    lines.append("<edges>")
    for index, edge in enumerate(edges):
        a, b = escape(str(edge.get("a", ""))), escape(str(edge.get("b", "")))
        lines.append(f'<edge id="e{index}" source="{a}" target="{b}" weight="{float(edge.get("weight", 0)):g}"/>')
    lines.extend(["</edges>", "</graph>", "</gexf>"])
    return "\n".join(lines) + "\n"


def serialize_graph(graph: dict[str, Any], format: str) -> str:
    """Serialize a graph as JSON, edge list, GraphML, or GEXF."""
    if format == "json":
        return json.dumps(graph, indent=2, sort_keys=True) + "\n"
    if format in {"edge-list", "edgelist", "tsv"}:
        return to_edge_list(graph)
    if format == "graphml":
        return to_graphml(graph)
    if format == "gexf":
        return to_gexf(graph)
    raise ValueError("format must be json, edge-list, graphml, or gexf")


def write_graph_snapshot(graph: dict[str, Any], path: str | Path, format: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialize_graph(graph, format), encoding="utf-8")
    return target
