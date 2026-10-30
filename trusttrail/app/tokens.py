import jwt

from . import settings

JWKS_URL = f"{settings.OIDC_BASE}/certs"
_jwks = jwt.PyJWKClient(JWKS_URL, cache_keys=True)


class TokenError(Exception):
    pass


def _signing_key(token: str):
    global _jwks
    try:
        return _jwks.get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientError:
        # Unknown key ID: Keycloak rotated keys or the realm was re-seeded.
        # PyJWKClient's caches don't recover from that on their own, so start fresh once.
        _jwks = jwt.PyJWKClient(JWKS_URL, cache_keys=True)
        return _jwks.get_signing_key_from_jwt(token).key


def verify_access_token(token: str) -> dict:
    """Check a service's Keycloak access token locally (signature, issuer, expiry).

    No audience check: Keycloak does not put our services in `aud` by default,
    so the calling service is identified by `azp` (the client the token was issued to).
    Revocation is not checked; a token stays usable until it expires.
    """
    try:
        key = _signing_key(token)
        claims = jwt.decode(token, key, algorithms=["RS256"], issuer=settings.ISSUER,
                            options={"verify_aud": False})
    except jwt.PyJWTError as e:
        raise TokenError(str(e)) from e
    if claims.get("typ") != "Bearer" or not claims.get("azp") or not claims.get("sub"):
        raise TokenError("not a Keycloak access token for a client")
    return claims


def verify_service_token(token: str) -> dict:
    """A service acting as itself (client-credentials grant), not on behalf of a student.

    Keycloak puts `client_id` only in service-account tokens, so a student's
    login token for the same service is rejected here.
    """
    claims = verify_access_token(token)
    if claims.get("client_id") != claims["azp"]:
        raise TokenError("expected a client-credentials token for the service itself")
    return claims
