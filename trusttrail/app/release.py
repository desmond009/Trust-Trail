"""Turning a granted profile into the attribute values a service receives."""
from . import settings

SCOPE_PREFIX = "profile-"


def granted_profile(scope: str, order: list[str] | None = None) -> str:
    """Most revealing profile-* scope Keycloak put in the token; none means anonymous."""
    order = order or settings.profiles()["order"]
    granted = {s[len(SCOPE_PREFIX):] for s in scope.split() if s.startswith(SCOPE_PREFIX)}
    ranked = [p for p in order if p in granted]
    return ranked[-1] if ranked else order[0]


def student_attributes(user: dict) -> dict:
    """Flatten a Keycloak user representation into our attribute vocabulary."""
    attrs = {k: v[0] for k, v in (user.get("attributes") or {}).items() if v}
    attrs["name"] = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
    attrs["email"] = user.get("email", "")
    return attrs


def build_release(profile: str, attrs: dict, pseudonym: str, profiles: dict | None = None) -> dict:
    spec = (profiles or settings.profiles()["profiles"])[profile]
    released = {name: attrs.get(name) for name in spec["attributes"]}
    if spec["sub"]:
        released = {"sub": pseudonym, **released}
    return released
