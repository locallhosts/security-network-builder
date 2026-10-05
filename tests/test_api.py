from fastapi.testclient import TestClient

from snb.api.app import app
from snb.models import Recommendation


def test_home_page():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Security Network Builder" in response.text


def test_health():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_interactive_docs_are_renderable_under_csp():
    client = TestClient(app)
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger-ui-bundle.js" in docs.text
    assert "cdn.jsdelivr.net" in docs.text
    assert "https://cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    redoc = client.get("/redoc")
    assert redoc.status_code == 200
    assert "redoc.standalone.js" in redoc.text


def test_public_graph_build_rejects_empty_analysis_with_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30, page=1, sort="stars": [
            {"full_name": "acme/runtime-security", "description": "runtime security", "stargazers_count": 25, "language": "Go", "owner": {"login": "alice", "type": "User", "html_url": "https://github.com/alice"}},
            {"full_name": "acme/ebpf-tool", "description": "eBPF security", "stargazers_count": 20, "language": "Go", "owner": {"login": "bob", "type": "User", "html_url": "https://github.com/bob"}},
        ],
    )
    monkeypatch.setattr("snb.api.app.analyse", lambda *args, **kwargs: [])
    response = TestClient(app).post("/api/public/graph/build", json={"query": "runtime security"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "no_engineers_matched"
    assert detail["candidates"] == 2
    assert "broader query" in detail["message"]


def test_public_graph_build_persists_and_reloads_current_snapshot(monkeypatch, tmp_path):
    db = str(tmp_path / "history.db")
    monkeypatch.setenv("SNB_HISTORY_DB", db)
    search_items = [
        {"full_name": "acme/runtime-security", "description": "runtime security", "stargazers_count": 25, "language": "Go", "owner": {"login": "alice", "type": "User", "html_url": "https://github.com/alice"}},
        {"full_name": "acme/ebpf-tool", "description": "eBPF security", "stargazers_count": 20, "language": "Go", "owner": {"login": "bob", "type": "User", "html_url": "https://github.com/bob"}},
    ]
    monkeypatch.setattr("snb.api.app.GitHubClient.search_repositories", lambda self, query, per_page=30, page=1, sort="stars": search_items)
    monkeypatch.setattr("snb.api.app.enrich_rest", lambda *args, **kwargs: None)

    def fake_analyse(client, ranked, profile, api, min_score):
        return [
            Recommendation(login=login, url=f"https://github.com/{login}", score=score, matched_domains=["eBPF", "Cloud Security"], breakdown={}, evidence=[], matched_repos=[], orgs=["AcmeSec"])
            for login, score in (("alice", 30.0), ("bob", 20.0))
        ]

    monkeypatch.setattr("snb.api.app.analyse", fake_analyse)
    client = TestClient(app)

    first = client.post("/api/public/graph/build", json={"query": "runtime security"})
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["run_id"] == 1
    assert first_data["engineers"] == 2
    assert [node["login"] for node in first_data["graph"]["nodes"]] == ["alice", "bob"]
    assert len(first_data["graph"]["edges"]) == 1

    loaded = client.get("/api/graph")
    assert loaded.status_code == 200
    assert loaded.json()["generated_at"]
    assert [node["login"] for node in loaded.json()["nodes"]] == ["alice", "bob"]
    assert loaded.json()["edges"] == first_data["graph"]["edges"]

    search_items[:] = [
        {"full_name": "acme/cloud", "description": "cloud security", "stargazers_count": 40, "language": "Python", "owner": {"login": "carol", "type": "User", "html_url": "https://github.com/carol"}},
    ]
    monkeypatch.setattr(
        "snb.api.app.analyse",
        lambda client, ranked, profile, api, min_score: [
            Recommendation(login="carol", url="https://github.com/carol", score=45.0, matched_domains=["Cloud Security"], breakdown={}, evidence=[], matched_repos=[])
        ],
    )
    second = client.post("/api/public/graph/build", json={"query": "cloud security"})
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["run_id"] == 2
    assert [node["login"] for node in second_data["graph"]["nodes"]] == ["carol"]

    reloaded = client.get("/api/graph")
    assert [node["login"] for node in reloaded.json()["nodes"]] == ["carol"]


def test_protected_endpoint_requires_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = TestClient(app)
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/runs", headers={"X-API-Key": "secret"}).status_code == 200


def test_search_is_public_even_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30, page=1, sort="stars": [{"full_name": "acme/ebpf", "description": "runtime security", "stargazers_count": 4, "language": "Go", "owner": {"login": "acme"}, "html_url": "https://github.com/acme/ebpf"}],
    )
    client = TestClient(app)
    response = client.get("/api/search?q=ebpf")
    assert response.status_code == 200
    assert response.json()["results"][0]["repository"] == "acme/ebpf"


def test_graph_is_public_even_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = TestClient(app)
    assert client.get("/api/graph").status_code == 200


def test_security_headers_and_github_url_validation(monkeypatch):
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30, page=1, sort="stars": [
            {"full_name": "acme/safe", "html_url": "https://github.com/acme/safe"},
            {"full_name": "acme/unsafe", "html_url": "https://evil.example/acme/unsafe"},
        ],
    )
    response = TestClient(app).get("/api/search?q=security")
    assert response.status_code == 200
    assert response.json()["results"][0]["url"] == "https://github.com/acme/safe"
    assert response.json()["results"][1]["url"] is None
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"].startswith("public, max-age=30")


def test_search_validates_query_and_limit():
    client = TestClient(app)
    assert client.get("/api/search?q=x").status_code == 422
    assert client.get("/api/search?q=security&limit=31").status_code == 422
    assert client.get("/api/search?q=security&page=35").status_code == 422


def test_search_translates_github_error_to_502(monkeypatch):
    from snb.github_api import GitHubError

    def fail(*args, **kwargs):
        raise GitHubError("upstream unavailable")

    monkeypatch.setattr("snb.api.app.GitHubClient.search_repositories", fail)
    response = TestClient(app).get("/api/search?q=security")
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream unavailable"


def test_private_route_rejects_wrong_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    response = TestClient(app).get("/api/runs", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid API key"


def test_private_route_is_unprotected_when_api_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = TestClient(app).get("/api/runs")
    assert response.status_code == 200


def test_runs_limit_is_bounded():
    client = TestClient(app)
    assert client.get("/api/runs?limit=0").status_code == 422
    assert client.get("/api/runs?limit=101").status_code == 422


def test_run_lookup_validates_positive_id():
    client = TestClient(app)
    assert client.get("/api/runs/0").status_code == 404


def test_latest_run_returns_404_when_history_is_empty(monkeypatch):
    class EmptyHistory:
        def latest_run_id(self):
            return None

    monkeypatch.setattr("snb.api.app.get_history", lambda: EmptyHistory())
    response = TestClient(app).get("/api/runs/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "no runs recorded"


def test_latest_run_returns_404_when_run_disappears(monkeypatch):
    class MissingHistory:
        def latest_run_id(self):
            return 7

        def get_run(self, run_id):
            return None

    monkeypatch.setattr("snb.api.app.get_history", lambda: MissingHistory())
    response = TestClient(app).get("/api/runs/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_run_lookup_returns_404_for_unknown_run(monkeypatch):
    class MissingHistory:
        def get_run(self, run_id):
            return None

    monkeypatch.setattr("snb.api.app.get_history", lambda: MissingHistory())
    response = TestClient(app).get("/api/runs/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_engineer_history_contract(monkeypatch):
    class HistoryStub:
        def engineer_history(self, login):
            return [{"run_id": 1, "score": 12}]

    monkeypatch.setattr("snb.api.app.get_history", lambda: HistoryStub())
    response = TestClient(app).get("/api/engineers/alice")
    assert response.status_code == 200
    assert response.json() == {"login": "alice", "history": [{"run_id": 1, "score": 12}]}


def test_search_rate_limit_returns_retry_after(monkeypatch):
    import snb.api.app as api_app

    api_app._PUBLIC_RATE_LIMITER.reset()
    monkeypatch.setenv("SNB_RATE_LIMIT_SEARCH", "1")
    client = TestClient(app)
    monkeypatch.setattr(api_app.GitHubClient, "search_repositories", lambda *args, **kwargs: [])
    assert client.get("/api/search?q=security").status_code == 200
    response = client.get("/api/search?q=security")
    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    api_app._PUBLIC_RATE_LIMITER.reset()
    monkeypatch.delenv("SNB_RATE_LIMIT_SEARCH", raising=False)


def test_public_github_url_validation_rejects_non_https_and_subdomains():
    from snb.api.app import _public_github_url

    assert _public_github_url("http://github.com/acme/repo") is None
    assert _public_github_url("https://evil.github.com/acme/repo") is None
    assert _public_github_url("https://github.com/acme/repo") == "https://github.com/acme/repo"


def test_openapi_contract_exposes_public_and_private_routes():
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/health" in paths
    assert "/api/search" in paths
    assert "/api/graph" in paths
    assert "/api/public/graph/build" in paths
    assert "/api/public/engineers/{login}" in paths
    assert "/api/runs" in paths
    assert "/api/runs/latest" in paths
    assert "/api/runs/{run_id}" in paths
    assert "/api/engineers/{login}" in paths


def test_public_response_models_are_exposed_in_openapi():
    schema = TestClient(app).get("/openapi.json").json()
    components = schema["components"]["schemas"]
    assert "HealthResponse" in components
    assert "SearchResponse" in components
    assert "SearchResult" in components
    assert "GraphResponse" in components


def test_search_response_contract_rejects_unexpected_upstream_shape(monkeypatch):
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30, page=1, sort="stars": [
            {"full_name": "acme/valid", "stargazers_count": 3, "html_url": "https://github.com/acme/valid"},
            {"full_name": "acme/bad", "stargazers_count": "not-an-integer", "html_url": "https://github.com/acme/bad"},
        ],
    )
    response = TestClient(app).get("/api/search?q=security")
    assert response.status_code == 500


def test_api_settings_normalize_environment(monkeypatch):
    monkeypatch.setenv("SNB_HISTORY_DB", "/tmp/snb-test.db")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.test, api.example.test ")
    from snb.api.app import load_settings

    settings = load_settings()
    assert settings.history_db == "/tmp/snb-test.db"
    assert settings.github_token == "token"
    assert settings.api_key == "secret"
    assert settings.allowed_hosts == ("example.test", "api.example.test")


def test_api_settings_use_safe_defaults(monkeypatch):
    for name in ("SNB_HISTORY_DB", "GITHUB_TOKEN", "API_KEY", "SNB_ALLOWED_HOSTS"):
        monkeypatch.delenv(name, raising=False)
    from snb.api.app import load_settings

    settings = load_settings()
    assert settings.history_db == "data/history.db"
    assert settings.github_token is None
    assert settings.api_key is None
    assert settings.allowed_hosts == ("*",)


def test_graph_response_contract_handles_missing_run(monkeypatch):
    class EmptyHistory:
        def latest_run_id(self):
            return 1

        def get_run(self, run_id):
            return None

    monkeypatch.setattr("snb.api.app.get_history", lambda: EmptyHistory())
    response = TestClient(app).get("/api/graph")
    assert response.status_code == 200
    assert response.json()["nodes"] == []
    assert response.json()["edges"] == []
    assert response.json()["communities"] == []


def test_public_web_ui_exposes_secure_search_controls():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert 'id="language"' in response.text
    assert 'id="min-stars"' in response.text
    assert 'id="prev"' in response.text
    assert 'id="next"' in response.text
    assert "createElementNS" in response.text
    assert "innerHTML" not in response.text
    assert 'id="zoom-in"' in response.text
    assert 'id="zoom-out"' in response.text
    assert "drag empty space to pan" in response.text
    assert "GitHub discovery" in response.text
    assert "does not modify the Security Intelligence Graph" in response.text
    assert "Refresh intelligence" in response.text


def test_public_engineer_profile_is_sanitized_and_public(monkeypatch):
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.get_user",
        lambda self, login: {
            "login": login,
            "name": "<script>ignored</script>",
            "bio": "security engineer",
            "company": "Example",
            "followers": "7",
            "public_repos": 4,
            "created_at": "2020-01-01T00:00:00Z",
            "html_url": "https://github.com/alice",
            "email": "private@example.com",
        },
    )
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.list_user_orgs",
        lambda self, login: ["ExampleOrg"],
    )
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.list_user_repos",
        lambda self, login, limit=100: [
            {
                "name": "secure-tool",
                "description": "runtime security",
                "stargazers_count": "5",
                "language": "Go",
                "html_url": "https://github.com/alice/secure-tool",
                "pushed_at": "2026-09-20T00:00:00Z",
            },
        ],
    )
    response = TestClient(app).get("/api/public/engineers/alice")
    assert response.status_code == 200
    data = response.json()
    assert data["login"] == "alice"
    assert data["followers"] == 7
    assert data["repositories"][0]["stars"] == 5
    assert "email" not in data
    assert data["repositories"][0]["url"] == "https://github.com/alice/secure-tool"
    assert data["organizations"] == ["ExampleOrg"]
    assert data["activity"][0]["repository"] == "secure-tool"
    assert "security_domains" in data
    assert "Go" in data["skills"]
    assert data["contribution_trends"]["last_365_days"] == 1
    assert data["repository_signals"][0]["maintenance"] == "active"


def test_public_engineer_intelligence_classifies_real_profile_metadata(monkeypatch):
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.get_user",
        lambda self, login: {
            "login": login,
            "name": "Alice",
            "followers": 12,
            "public_repos": 2,
            "html_url": "https://github.com/alice",
        },
    )
    monkeypatch.setattr("snb.api.app.GitHubClient.list_user_orgs", lambda self, login: [])
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.list_user_repos",
        lambda self, login, limit=100: [
            {
                "name": "ebpf-runtime-security",
                "description": "eBPF runtime security",
                "topics": ["ebpf", "runtime-security"],
                "stargazers_count": 10,
                "forks_count": 2,
                "open_issues_count": 1,
                "language": "Go",
                "pushed_at": "2026-10-01T00:00:00Z",
                "archived": False,
                "fork": False,
                "html_url": "https://github.com/alice/ebpf-runtime-security",
            },
            {
                "name": "old-fork",
                "description": "old copy",
                "topics": [],
                "stargazers_count": 1,
                "forks_count": 0,
                "open_issues_count": 0,
                "language": "Python",
                "pushed_at": "2024-01-01T00:00:00Z",
                "archived": True,
                "fork": True,
                "html_url": "https://github.com/alice/old-fork",
            },
        ],
    )
    response = TestClient(app).get("/api/public/engineers/alice")
    assert response.status_code == 200
    data = response.json()
    assert data["security_domains"]
    assert "eBPF" in " ".join(data["skills"]).lower() or "ebpf" in " ".join(data["skills"]).lower()
    assert data["contribution_trends"]["last_30_days"] >= 1
    assert data["repository_signals"][0]["maintenance"] == "active"
    assert any(item["maintenance"] == "archived" for item in data["repository_signals"])


def test_public_engineer_profile_rejects_invalid_login():
    response = TestClient(app).get("/api/public/engineers/not valid!")
    assert response.status_code == 422


def test_public_engineer_profile_returns_404_for_unknown_user(monkeypatch):
    monkeypatch.setattr("snb.api.app.GitHubClient.get_user", lambda self, login: {})
    response = TestClient(app).get("/api/public/engineers/ghost")
    assert response.status_code == 404
    assert response.json()["detail"] == "engineer not found"


def test_public_web_ui_exposes_profile_and_graph_controls():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert 'id="community"' in response.text
    assert 'id="centrality"' in response.text
    assert 'id="apply-graph"' in response.text
    assert 'id="refresh-graph"' in response.text
    assert "loadEngineer(login)" in response.text
    assert "Security Intelligence Graph" in response.text
    assert "Build graph from search" not in response.text
    assert "Relationship details" in response.text
    assert "Repository contribution" in response.text
    assert "Shared organization" in response.text
    assert "Shared security domains" in response.text
    assert "evidence-backed signals" in response.text


def test_private_engineer_analysis_returns_score_breakdown_and_history(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.get_user",
        lambda self, login: {"login": login},
    )
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.list_user_repos",
        lambda self, login, limit=100: [
            {
                "name": "ebpf-runtime-security",
                "full_name": f"{login}/ebpf-runtime-security",
                "description": "eBPF runtime security tooling",
                "topics": ["ebpf", "runtime-security"],
                "stargazers_count": 25,
                "language": "Go",
                "pushed_at": "2026-09-20T00:00:00Z",
                "html_url": f"https://github.com/{login}/ebpf-runtime-security",
            }
        ],
    )
    class FakeHistory:
        def engineer_history(self, login):
            return [{"run_id": 4, "created_at": "2026-09-20 00:00:00", "score": 16.0}]
    monkeypatch.setattr("snb.api.app.get_history", lambda: FakeHistory())
    response = TestClient(app).get("/api/engineers/alice/analysis", headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    data = response.json()
    assert data["login"] == "alice"
    assert data["score"] is not None
    assert data["matched_domains"]
    assert data["breakdown"]
    assert data["evidence"]
    assert data["matched_repositories"][0]["url"] == "https://github.com/alice/ebpf-runtime-security"
    assert data["history"][0]["score"] == 16.0


def test_private_engineer_analysis_requires_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    response = TestClient(app).get("/api/engineers/alice/analysis")
    assert response.status_code == 401


def test_private_engineer_analysis_rejects_invalid_login(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = TestClient(app).get("/api/engineers/not valid!/analysis")
    assert response.status_code == 422


def test_public_user_search_contract(monkeypatch):
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_users",
        lambda self, query, per_page=30, sort="followers", page=1: [
            {
                "login": "alice",
                "type": "User",
                "followers": 42,
                "public_repos": 8,
                "avatar_url": "https://avatars.githubusercontent.com/u/1",
                "html_url": "https://github.com/alice",
            }
        ],
    )
    response = TestClient(app).get("/api/users/search?q=security")
    assert response.status_code == 200
    user = response.json()["results"][0]
    assert user["login"] == "alice"
    assert user["followers"] == 42
    assert user["url"] == "https://github.com/alice"


def test_repository_search_accepts_public_filters(monkeypatch):
    seen = {}
    def fake_search(self, query, per_page=30, sort="stars", page=1):
        seen["query"] = query
        seen["sort"] = sort
        return []
    monkeypatch.setattr("snb.api.app.GitHubClient.search_repositories", fake_search)
    response = TestClient(app).get("/api/search?q=security&language=Go&min_stars=25&sort=updated")
    assert response.status_code == 200
    assert "language:Go" in seen["query"]
    assert "stars:>=25" in seen["query"]
    assert seen["sort"] == "updated"


def test_public_web_ui_has_export_and_graph_controls():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert 'data-tab="users"' in response.text
    assert 'id="export-results"' in response.text
    assert 'id="download-svg"' in response.text
    assert 'id="download-graph"' in response.text
    assert 'id="node-filter"' in response.text
    assert "--bg:#f7f9fc" in response.text


def test_public_search_exposes_freshness_and_advanced_filters(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30, page=1, sort="stars": (seen.update(query=query) or []),
    )
    response = TestClient(app).get("/api/search?q=security&owner=alice&topic=ebpf&archived=false&fork=false")
    assert response.status_code == 200
    assert "user:alice" in seen["query"]
    assert "topic:ebpf" in seen["query"]
    assert "archived:false" in seen["query"]
    assert response.json()["source"] == "github"
    assert response.json()["generated_at"]


def test_graph_filters_are_server_validated():
    assert TestClient(app).get("/api/graph?edge_type=invalid").status_code == 422
    assert TestClient(app).get("/api/graph?min_centrality=1.5").status_code == 422


def test_workspace_is_private_and_supports_timeline_export(monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("SNB_WORKSPACE_DB", str(tmp_path / "workspace.db"))
    client = TestClient(app)
    created = client.post("/api/workspaces", headers={"X-API-Key": "secret"}, json={"title": "Research"})
    assert created.status_code == 201
    wid = created.json()["id"]
    assert client.post(f"/api/workspaces/{wid}/items", headers={"X-API-Key": "secret"}, json={"kind": "engineer", "value": "alice", "source_url": "https://github.com/alice"}).status_code == 200
    assert client.post(f"/api/workspaces/{wid}/notes", headers={"X-API-Key": "secret"}, json={"body": "Review eBPF evidence"}).status_code == 200
    data = client.get(f"/api/workspaces/{wid}", headers={"X-API-Key": "secret"}).json()
    assert len(data["items"]) == 1
    assert len(data["notes"]) == 1
    assert [e["action"] for e in data["timeline"]] == ["created", "evidence_added", "note_added"]
    bundle = client.get(f"/api/workspaces/{wid}/export", headers={"X-API-Key": "secret"})
    assert bundle.status_code == 200
    assert bundle.json()["schema_version"] == 1
    assert "Review eBPF evidence" in bundle.text
    assert client.get(f"/api/workspaces/{wid}").status_code == 401


def test_public_engineer_compare_contract(monkeypatch):
    monkeypatch.setattr("snb.api.app.GitHubClient.get_user", lambda self, login: {"login": login, "name": login, "html_url": f"https://github.com/{login}"})
    monkeypatch.setattr("snb.api.app.GitHubClient.list_user_repos", lambda self, login, limit=100: [{"name": "security-tool", "description": "runtime security", "topics": ["runtime-security"], "stargazers_count": 5, "language": "Go", "pushed_at": "2026-10-01T00:00:00Z", "html_url": f"https://github.com/{login}/security-tool"}])
    compare = TestClient(app).get("/api/public/engineers/compare?first=alice&second=bob")
    assert compare.status_code == 200
    assert len(compare.json()["profiles"]) == 2