"""A generic invented campus service (library / LMS / exam portal).

It logs students in through Keycloak with an ordinary OIDC library (Authlib),
asking for the profile scope from config/services.yaml. Before asking TrustTrail
for attributes it signs a purpose declaration with its own key. The page shows
exactly what the service ended up knowing and the receipt it got back.
"""
import html
import json
import os
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx
import jwt
import yaml
from authlib.integrations.starlette_client import OAuth
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from jwk import public_ec_jwk

SERVICE_ID = os.environ["SERVICE_ID"]
SVC = yaml.safe_load(open("/config/services.yaml"))["services"][SERVICE_ID]
KC = os.environ.get("KC_INTERNAL_URL", "http://keycloak:8080")
REALM = os.environ.get("KC_REALM", "trusttrail")
TRUSTTRAIL = os.environ.get("TRUSTTRAIL_URL", "http://trusttrail:8000")
KEY_PATH = Path(os.environ.get("KEY_DIR", "/keys")) / f"{SERVICE_ID}.pem"

app = FastAPI(title=SVC["name"])
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"],
                   session_cookie=f"{SERVICE_ID}_session")
oauth = OAuth()
oauth.register(
    "keycloak", client_id=SERVICE_ID, client_secret=os.environ["CLIENT_SECRET"],
    server_metadata_url=f"{KC}/realms/{REALM}/.well-known/openid-configuration",
    client_kwargs={"scope": f"openid profile-{SVC['wants']}"})


# --- the service's declaration-signing key and declaration ---------------------

def signing_key():
    # Generated once and kept in a Docker volume; never in the repo.
    if not KEY_PATH.exists():
        key = ec.generate_private_key(ec.SECP256R1())
        KEY_PATH.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                               serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    return serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)


_declaration: dict | None = None


def current_declaration() -> dict:
    """Sign and submit a fresh declaration when there is none or it is about to expire."""
    global _declaration
    if _declaration and _declaration["expires_at"] > time.time() + 3600:
        return _declaration

    key = signing_key()
    jwk = public_ec_jwk(key)
    token = httpx.post(f"{KC}/realms/{REALM}/protocol/openid-connect/token", data={
        "grant_type": "client_credentials", "client_id": SERVICE_ID,
        "client_secret": os.environ["CLIENT_SECRET"]}).raise_for_status().json()["access_token"]
    httpx.post(f"{TRUSTTRAIL}/services/keys", json={"keys": [jwk]},
               headers={"Authorization": f"Bearer {token}"}).raise_for_status()

    spec, now = SVC["declaration"], int(time.time())
    claims = {"client_id": SERVICE_ID, "aud": "trusttrail",
              "attributes": spec["attributes"], "purpose": spec["purpose"],
              "retention_until": (date.today() + timedelta(days=spec["retention_days"])).isoformat(),
              "nonce": str(uuid.uuid4()), "iat": now, "exp": now + spec["valid_days"] * 86400}
    jws = jwt.encode(claims, key, algorithm="ES256",
                     headers={"kid": jwk["kid"], "typ": "purpose-declaration+jwt"})
    _declaration = httpx.post(f"{TRUSTTRAIL}/declarations",
                              json={"declaration": jws}).raise_for_status().json()
    return _declaration


# --- pages ---------------------------------------------------------------------

def page(body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><meta charset=utf-8><title>{SVC['name']}</title>
<style>body{{font-family:system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}}
pre{{background:#f4f4f4;padding:1rem;overflow:auto}}</style>
<h1>{SVC['name']}</h1><p><small>invented test service · asks for profile <b>{SVC['wants']}</b></small></p>{body}""")


def pre(title: str, data) -> str:
    return f"\n<h3>{title}</h3><pre>{html.escape(json.dumps(data, indent=2))}</pre>\n"


@app.get("/")
def home(request: Request):
    seen = request.session.get("seen")
    if not seen:
        spec = SVC["declaration"]
        return page(f"""<p>This service promises to use <b>{', '.join(spec['attributes'])}</b>
only to: <i>{html.escape(spec['purpose'])}</i> and to delete it within {spec['retention_days']} days.</p>
<p><a href="/login">Log in with university SSO</a></p>""")
    return page("<h2>What this service learned</h2>"
                + pre("From Keycloak (ID token)", seen["id_token"])
                + pre("From TrustTrail (/release)", seen["release"])
                + pre("Receipt payload (signed by TrustTrail)", seen.get("receipt"))
                + '<p><a href="/logout">Log out</a></p>')


@app.get("/login")
async def login(request: Request):
    return await oauth.keycloak.authorize_redirect(request, f"{SVC['url']}/callback")


@app.get("/callback")
async def callback(request: Request):
    token = await oauth.keycloak.authorize_access_token(request)
    decl = current_declaration()
    r = httpx.post(f"{TRUSTTRAIL}/release", json={"declaration_id": decl["declaration_id"]},
                   headers={"Authorization": f"Bearer {token['access_token']}"})
    body = r.json()
    receipt = jwt.decode(body["receipt"], options={"verify_signature": False}) if r.status_code == 200 else None
    request.session["seen"] = {"id_token": dict(token["userinfo"]),
                               "release": {k: v for k, v in body.items() if k != "receipt"},
                               "receipt": receipt}
    return RedirectResponse("/")


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
