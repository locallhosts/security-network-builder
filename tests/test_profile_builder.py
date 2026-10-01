import yaml

from snb.config import Profile
from conftest import repo
from snb.explain import LLM
from snb.profile_builder import refine_with_llm, suggest_profile, to_yaml
from test_explain import FakeSession, Resp

BASE = yaml.safe_load(open("profiles/security_profile.yaml"))


def mine():
    return [
        repo("tracer", "ebpf runtime security tool", topics=["ebpf", "bpf-tools"], lang="Go", owner="me"),
        repo("probe", "falco rules for ebpf", topics=["ebpf", "bpf-tools"], lang="Go", owner="me"),
        repo("rules", "sigma detection rules", lang="Python", owner="me"),
        repo("dotfiles", "my dotfiles", owner="me"),
        repo("forked", "ebpf", fork=True, owner="me"),
    ]


def test_heuristic_weights_languages_and_topics():
    out, notes = suggest_profile("me", mine(), Profile.from_dict(BASE), BASE)
    assert out["github_username"] == "me"
    d = out["domains"]
    assert d["ebpf_linux_security"]["weight"] == 10 > d["detection_engineering"]["weight"]
    assert "bpf tools" in d["ebpf_linux_security"]["keywords"]      # co-occurring topic promoted
    assert "cloud_security" not in d                                # no evidence -> dropped
    assert out["settings"]["preferred_languages"][0] == "Go"
    Profile.from_dict(out)                                          # still a valid profile
    assert BASE["domains"]["cloud_security"]                        # base dict not mutated


def test_no_matches_keeps_base():
    out, notes = suggest_profile("me", [repo("x", "todo app", owner="me")], Profile.from_dict(BASE), BASE)
    assert set(out["domains"]) == set(BASE["domains"]) and "unchanged" in notes[0]


def test_llm_refinement_validated_and_falls_back():
    draft, _ = suggest_profile("me", mine(), Profile.from_dict(BASE), BASE)
    good = {"name": "AI", "github_username": "evil", "domains": {"x": {"label": "X", "weight": 9, "keywords": ["kw"], "search_queries": ["q"]}}}
    s = FakeSession(Resp(200, {"content": [{"type": "text", "text": "Here you go: " + __import__("json").dumps(good)}]}))
    out, note = refine_with_llm(LLM("k", session=s), "me", mine(), draft)
    assert out["domains"]["x"]["weight"] == 9 and out["github_username"] == "me" and "applied" in note

    bad = FakeSession(Resp(200, {"content": [{"type": "text", "text": '{"domains": {}}'}]}))
    out, note = refine_with_llm(LLM("k", session=bad), "me", mine(), draft)
    assert out == draft and "skipped" in note

    junk = FakeSession(Resp(200, {"content": [{"type": "text", "text": "no json here"}]}))
    assert refine_with_llm(LLM("k", session=junk), "me", mine(), draft)[0] == draft


def test_yaml_roundtrip():
    out, _ = suggest_profile("me", mine(), Profile.from_dict(BASE), BASE)
    assert yaml.safe_load(to_yaml(out)) == out
