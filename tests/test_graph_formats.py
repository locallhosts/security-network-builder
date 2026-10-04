from snb.graph_formats import serialize_graph


GRAPH = {
    "nodes": [
        {"login": "bob", "score": 2},
        {"login": "alice", "score": 4},
    ],
    "edges": [{"a": "bob", "b": "alice", "weight": 3}],
    "communities": [],
}


def test_graph_formats_are_deterministic():
    assert "alice\tbob\t3" in serialize_graph(GRAPH, "edge-list")
    assert 'node id="alice"' in serialize_graph(GRAPH, "graphml")
    assert 'source="alice" target="bob"' in serialize_graph(GRAPH, "gexf")


def test_json_snapshot_is_stable():
    output = serialize_graph(GRAPH, "json")
    assert output.startswith("{")
    assert '"nodes"' in output


def test_graph_format_validation():
    try:
        serialize_graph(GRAPH, "yaml")
    except ValueError as exc:
        assert "format" in str(exc)
    else:
        raise AssertionError("expected ValueError")
