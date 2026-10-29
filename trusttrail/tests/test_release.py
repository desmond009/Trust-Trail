import pytest

from app import settings
from app.release import build_release, granted_profile, student_attributes

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


def test_release_contains_exactly_the_profile_attributes():
    attrs = student_attributes(USER)
    for profile in ORDER:
        spec = settings.profiles()["profiles"][profile]
        released = build_release(profile, attrs, "pseudo-123")
        expected = set(spec["attributes"]) | ({"sub"} if spec["sub"] else set())
        assert set(released) == expected, profile


def test_anonymous_release_has_no_identifier():
    released = build_release("anonymous", student_attributes(USER), "pseudo-123")
    assert "sub" not in released and released == {"affiliation": "student"}


def test_profiles_are_nested():
    # Each profile must reveal at least what the one below it does; tier caps rely on this.
    sets = [set(settings.profiles()["profiles"][p]["attributes"]) for p in ORDER]
    assert all(lower <= upper for lower, upper in zip(sets, sets[1:]))
