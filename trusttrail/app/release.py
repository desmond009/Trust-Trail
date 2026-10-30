"""Turning a granted profile into the attribute values a service receives."""
from . import settings
from .errors import Refusal

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


def profile_attributes(profile: str, profiles: dict | None = None) -> set[str]:
    """Everything a profile may reveal, with the pseudonym counted as attribute `sub`."""
    spec = (profiles or settings.profiles()["profiles"])[profile]
    return set(spec["attributes"]) | ({"sub"} if spec["sub"] else set())


def choose_attributes(requested: list[str] | None, declared: list[str], allowed: set[str]) -> list[str]:
    """Which attributes to release, or a Refusal naming what is not covered.

    Asking for nothing explicit means "everything my declaration covers that my
    profile allows". Explicitly asking for more than either is refused.
    """
    if requested is None:
        return sorted(set(declared) & allowed)
    not_declared = sorted(set(requested) - set(declared))
    if not_declared:
        # Phase 4 records this as a violation (rule 1).
        raise Refusal(403, "attribute_not_declared",
                      f"not covered by the signed declaration: {not_declared}")
    above = sorted(set(requested) - allowed)
    if above:
        # Phase 4 records this as a violation (rule 3).
        raise Refusal(403, "attribute_above_profile",
                      f"not allowed by the granted profile: {above}")
    return sorted(set(requested))


def build_release(names: list[str], attrs: dict, pseudonym: str) -> dict:
    return {name: (pseudonym if name == "sub" else attrs.get(name)) for name in names}
