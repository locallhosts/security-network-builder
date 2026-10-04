from snb.config import Profile
from snb.profile_compare import compare_profiles


class FakeClient:
    def list_user_repos(self, login, limit):
        return [{
            "name": "sigma-tool",
            "full_name": f"{login}/sigma-tool",
            "description": "Sigma detection engineering security tooling",
            "topics": ["sigma"],
            "stargazers_count": 10,
            "language": "Python",
            "pushed_at": "2026-09-30T00:00:00+00:00",
        }]


def profile(name, keyword):
    return Profile.from_dict({
        "name": name,
        "github_username": "",
        "settings": {"min_stars": 0},
        "domains": {
            "security": {
                "label": "Security",
                "weight": 5,
                "keywords": [keyword],
                "search_queries": [keyword],
            }
        },
    })


def test_compare_profiles_reuses_same_candidate_set():
    result = compare_profiles(
        FakeClient(),
        {
            "detection": profile("Detection", "sigma"),
            "cloud": profile("Cloud", "kubernetes"),
        },
        ["alice", "alice"],
    )
    assert result["profiles"] == ["detection", "cloud"]
    assert result["candidates"][0]["login"] == "alice"
    assert result["candidates"][0]["profiles"]["detection"]["score"] > 0
    assert result["candidates"][0]["profiles"]["cloud"] is None


def test_compare_profiles_is_bounded():
    try:
        compare_profiles(FakeClient(), {}, ["alice"])
        assert False
    except ValueError:
        pass
    try:
        compare_profiles(FakeClient(), {"one": profile("One", "sigma")}, [])
        assert False
    except ValueError:
        pass
