import pytest

from app import settings
from app.errors import Refusal
from app.release import (build_release, choose_attributes, granted_profile,
                         profile_attributes, student_attributes)

ORDER = settings.profiles()["order"]
USER = {"firstName": "Asha", "lastName": "Kulkarni", "email": "asha@students.example.edu",
        "attributes": {"affiliation": ["student"], "roll_no": ["TT24CS001"],
                       "department": ["Computer Science"], "program": ["B.Tech"], "year": ["2"]}}


@pytest.mark.parametrize("scope,expected", [
    ("openid profile-partial", "partial"),
    ("openid profile-pseudonym profile-total", "total"),  # highest wins
    ("profile-anonymous", "anonymous"),
    ("openid", "anonymous"),                               # no profile scope at all
    ("openid profile-bogus", "anonymous"),
])
def test_granted_profile(scope, expected):
    assert granted_profile(scope) == expected


def test_profile_attributes_match_config():
    assert profile_attributes("anonymous") == {"affiliation"}
    assert profile_attributes("pseudonym") == {"sub", "affiliation"}
    assert "roll_no" in profile_attributes("total") and "roll_no" not in profile_attributes("partial")


def test_profiles_are_nested():
    # Each profile must reveal at least what the one below it does; tier caps rely on this.
    sets = [profile_attributes(p) for p in ORDER]
    assert all(lower <= upper for lower, upper in zip(sets, sets[1:]))


def test_default_request_is_declared_and_allowed():
    declared = ["sub", "affiliation", "department", "roll_no"]
    allowed = profile_attributes("partial")
    assert choose_attributes(None, declared, allowed, allowed) == ["affiliation", "department", "sub"]


def refusal(requested, declared, allowed, entitled) -> Refusal:
    with pytest.raises(Refusal) as e:
        choose_attributes(requested, declared, profile_attributes(allowed), profile_attributes(entitled))
    return e.value


def test_undeclared_attribute_is_rule_1():
    r = refusal(["email"], ["sub", "affiliation"], "total", "total")
    assert (r.code, r.rule) == ("attribute_not_declared", "undeclared_attribute")


def test_above_tier_cap_is_rule_3():
    r = refusal(["roll_no"], ["sub", "roll_no"], "pseudonym", "pseudonym")
    assert (r.code, r.rule) == ("attribute_above_tier_cap", "above_tier_cap")


def test_above_granted_profile_but_within_cap_is_not_a_violation():
    # e.g. the LMS logged the student in with `pseudonym` but asks for department
    r = refusal(["department"], ["sub", "department"], "pseudonym", "partial")
    assert (r.code, r.rule) == ("attribute_above_profile", None)


def test_above_lowered_cap_but_within_agreement_is_not_counted_again():
    # a demoted service (now pseudonym) asking what its agreement (partial) allowed
    r = refusal(["year"], ["sub", "year"], "pseudonym", "partial")
    assert r.rule is None


def test_build_release_fills_values_and_pseudonym():
    released = build_release(["sub", "name", "year"], student_attributes(USER), "pseudo-123")
    assert released == {"sub": "pseudo-123", "name": "Asha Kulkarni", "year": "2"}


def test_anonymous_release_has_no_identifier():
    names = choose_attributes(None, ["sub", "affiliation"], profile_attributes("anonymous"), profile_attributes("total"))
    assert build_release(names, student_attributes(USER), "pseudo-123") == {"affiliation": "student"}
