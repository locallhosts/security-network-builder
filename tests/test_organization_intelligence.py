from snb.models import Recommendation
from snb.organization_intelligence import analyze_organization_intelligence


def rec(login, score, orgs, domains):
    return Recommendation(
        login=login,
        url=f"https://github.com/{login}",
        score=score,
        matched_domains=domains,
        breakdown={},
        evidence=[],
        matched_repos=[],
        orgs=orgs,
    )


def test_organization_intelligence_aggregates_public_signals():
    result = analyze_organization_intelligence(
        [
            rec("alice", 20, ["Acme"], ["cloud", "iam"]),
            rec("bob", 10, ["Acme", "Other"], ["cloud"]),
            rec("carol", 5, ["Other"], ["detection"]),
        ]
    )
    assert result[0]["login"] == "Acme"
    assert result[0]["member_count"] == 2
    assert result[0]["domain_diversity"] == 2
    assert result[0]["top_member_score"] == 20
    assert result[0]["score_share_percent"] == round(30 / 35 * 100, 1)


def test_organization_intelligence_deduplicates_membership():
    result = analyze_organization_intelligence(
        [rec("alice", 10, ["Acme", "Acme"], ["cloud"])]
    )
    assert result[0]["member_count"] == 1
    assert result[0]["members"] == ["alice"]


def test_organization_intelligence_bounds():
    try:
        analyze_organization_intelligence([], max_orgs=0)
    except ValueError as exc:
        assert "max_orgs" in str(exc)
    else:
        raise AssertionError("expected ValueError")
