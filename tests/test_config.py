import pytest
from config import Profile, compile_keyword, normalize


def test_normalize_separators():
    assert normalize("MITRE-ATT&CK_x") == "mitre att&ck x"


def test_keyword_word_boundaries():
    pat = compile_keyword("iam")
    assert pat.search("aws iam roles")
    assert not pat.search("william")      # no substring matches
    assert compile_keyword("mitre attack").search(normalize("mitre-attack mapping"))


def test_invalid_profiles():
    with pytest.raises(ValueError):
        Profile.from_dict({"domains": {}})
    with pytest.raises(ValueError):
        Profile.from_dict({"domains": {"x": {"keywords": []}}})
    with pytest.raises(ValueError):
        Profile.from_dict({"domains": {"x": {"keywords": ["a"]}}, "settings": {"bogus": 1}})


def test_shipped_profile_loads():
    p = Profile.load("profiles/security_profile.yaml")
    assert len(p.domains) == 6
