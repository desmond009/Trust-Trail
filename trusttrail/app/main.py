from fastapi import FastAPI, Header, HTTPException

from . import release as rel
from .keycloak import KeycloakAdmin
from .pseudonyms import PseudonymMap
from .tokens import TokenError, verify_access_token

app = FastAPI(title="TrustTrail")
kc = KeycloakAdmin()
pmap = PseudonymMap(kc)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/release")
def release(authorization: str = Header(...)):
    """The only path by which a service learns student attributes.

    Phase 1: profile filtering only. Phase 2 adds the signed purpose
    declaration requirement; Phase 3 writes every release to the ledger.
    """
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = verify_access_token(token)
    except TokenError as e:
        raise HTTPException(401, f"invalid access token: {e}")

    service = claims["azp"]
    profile = rel.granted_profile(claims.get("scope", ""))
    user_id = pmap.resolve(service, claims["sub"])
    if user_id is None:
        raise HTTPException(403, "unknown pseudonym for this service")

    attrs = rel.student_attributes(kc.user(user_id))
    return {"service": service, "profile": profile,
            "released": rel.build_release(profile, attrs, claims["sub"])}
