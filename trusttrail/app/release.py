"""Turning a granted profile into the attribute values a service receives."""
from . import settings
from .errors import ABOVE_TIER_CAP, UNDECLARED_ATTRIBUTE, Refusal

SCOPE_PREFIX = "profile-"


def lower_profile(a: str, b: str) -> str:
    order = settings.profiles()["order"]
    return a if order.index(a) <= order.index(b) else b


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


def choose_attributes(requested: list[str] | None, declared: list[str],
                      allowed: set[str], entitled: set[str]) -> list[str]:
    """Which attributes to release, or a Refusal naming what is not covered.

    allowed   what the granted profile allows right now (token scope, capped by current tier)
    entitled  what the service's base tier cap allows (its agreement with the university)

    Asking for nothing explicit means "everything my declaration covers that I'm
    allowed now". Asking explicitly for more is refused; it is a violation when
    it breaks the signed purpose (rule 1) or the tier cap (rule 3). Asking above
    a *lowered* cap but within the agreement is refused without a new violation,
    so a demoted service isn't punished again for its old, legitimate requests.
    """
    if requested is None:
        return sorted(set(declared) & allowed)
    not_declared = sorted(set(requested) - set(declared))
    if not_declared:
        raise Refusal(403, "attribute_not_declared", f"not covered by the signed declaration: {not_declared}",
                      rule=UNDECLARED_ATTRIBUTE, requested=requested)
    above_cap = sorted(set(requested) - entitled)
    if above_cap:
        raise Refusal(403, "attribute_above_tier_cap", f"above this service's tier cap: {above_cap}",
                      rule=ABOVE_TIER_CAP, requested=requested)
    above = sorted(set(requested) - allowed)
    if above:
        raise Refusal(403, "attribute_above_profile", f"not allowed by the granted profile: {above}")
    return sorted(set(requested))


def build_release(names: list[str], attrs: dict, pseudonym: str) -> dict:
    return {name: (pseudonym if name == "sub" else attrs.get(name)) for name in names}
