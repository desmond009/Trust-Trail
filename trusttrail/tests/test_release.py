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
    assert choose_attributes(None, declared, profile_attributes("partial")) == ["affiliation", "department", "sub"]


def test_request_beyond_declaration_is_refused():
    with pytest.raises(Refusal) as e:
        choose_attributes(["email"], ["sub", "affiliation"], profile_attributes("total"))
    assert e.value.code == "attribute_not_declared"


def test_request_beyond_profile_is_refused():
    with pytest.raises(Refusal) as e:
        choose_attributes(["roll_no"], ["sub", "roll_no"], profile_attributes("pseudonym"))
    assert e.value.code == "attribute_above_profile"


def test_build_release_fills_values_and_pseudonym():
    released = build_release(["sub", "name", "year"], student_attributes(USER), "pseudo-123")
    assert released == {"sub": "pseudo-123", "name": "Asha Kulkarni", "year": "2"}


def test_anonymous_release_has_no_identifier():
    names = choose_attributes(None, ["sub", "affiliation"], profile_attributes("anonymous"))
    assert build_release(names, student_attributes(USER), "pseudo-123") == {"affiliation": "student"}
