"""Unit tests for the trust score and tiers (config/trust.yaml values)."""
import pytest

from app import settings
from app.trust import profiles_up_to, score, tier_after

RULES = settings.trust_rules()
S = RULES["score"]
COMPLETE = {"name": "Library", "description": "Lending", "rootUrl": "http://x",
            "attributes": {"policyUri": "http://x/privacy", "tosUri": "http://x/terms"}}


def test_complete_registration_scores_full_marks():
    r = score(COMPLETE, violations=0)
    assert r["score"] == S["start"] and r["demotions"] == 0
    assert r["privacy_policy_declared"] and r["missing_metadata"] == []


def test_missing_privacy_policy_costs_points():
    client = {**COMPLETE, "attributes": {"tosUri": "http://x/terms"}}
    assert score(client, 0)["score"] == S["start"] - S["no_privacy_policy"]


def test_missing_metadata_costs_points_once():
    client = {"name": "X", "attributes": {"policyUri": "http://x/privacy"}}
    r = score(client, 0)
    assert r["score"] == S["start"] - S["incomplete_metadata"]
    assert set(r["missing_metadata"]) == {"description", "rootUrl", "tosUri"}


def test_each_violation_costs_one_step_and_one_tier():
    for n in range(1, 4):
        r = score(COMPLETE, violations=n)
        assert r["score"] == S["start"] - n * S["violation_step"]
        assert r["demotions"] == n     # step == band, so one violation = one tier


def test_score_never_goes_negative():
    assert score(COMPLETE, violations=50)["score"] == 0


def test_registration_gaps_alone_can_cost_a_tier():
    bare = {"name": "X", "attributes": {}}            # no policy, incomplete metadata
    assert score(bare, 0)["demotions"] == (S["no_privacy_policy"] + S["incomplete_metadata"]) // S["tier_band"]


@pytest.mark.parametrize("base,demotions,expected", [
    ("fully_trusted", 0, "fully_trusted"),
    ("fully_trusted", 1, "semi_trusted"),
    ("semi_trusted", 1, "untrusted"),
    ("untrusted", 1, "blocked"),
    ("untrusted", 5, "blocked"),                     # floor
])
def test_tier_moves_down_one_step_per_demotion(base, demotions, expected):
    assert tier_after(base, demotions) == expected


def test_caps_follow_tiers():
    assert [settings.tier_cap(t) for t in RULES["tier_order"]] == ["anonymous", "pseudonym", "partial", "total"]
    assert profiles_up_to("partial") == ["anonymous", "pseudonym", "partial"]
