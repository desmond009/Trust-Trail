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

ACCENTS = {"library": ("#0e9f6e", "#0b7d57"), "lms": ("#4f46e5", "#7c3aed"), "exam": ("#d97706", "#b45309")}
ICONS = {"library": "M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 006.5 22H20V2H6.5A2.5 2.5 0 004 4.5v15z",
         "lms": "M22 10L12 5 2 10l10 5 10-5zM6 12v5c3 2 9 2 12 0v-5",
         "exam": "M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"}

CSS = """
:root{--bg:#f5f6fa;--surface:#fff;--surface-2:#f0f2f7;--line:#e3e6ee;--fg:#141a2a;--muted:#5f6880;--code:#0f1420;--code-fg:#d6dcf0}
@media (prefers-color-scheme:dark){:root{--bg:#0d1017;--surface:#151a24;--surface-2:#1c2230;--line:#262d3d;--fg:#e8ebf3;--muted:#9aa3b8;--code:#0a0d14}}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--fg);background:var(--bg);-webkit-font-smoothing:antialiased}
.top{background:linear-gradient(135deg,var(--a1),var(--a2));color:#fff}.top .wrap{display:flex;align-items:center;gap:14px;padding:22px 20px}
.wrap{max-width:820px;margin:0 auto;padding:0 20px}.icon{width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,.18);display:grid;place-items:center}
h1{margin:0;font-size:22px;letter-spacing:-.01em}.top small{opacity:.85}main{padding:24px 0 48px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px;margin:0 0 14px;box-shadow:0 1px 2px rgba(20,26,42,.04),0 4px 16px rgba(20,26,42,.06)}
.card h2{margin:0 0 6px;font-size:17px}.muted{color:var(--muted);font-size:14px}.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.chip{font-size:13px;font-weight:600;padding:3px 9px;border-radius:8px;background:color-mix(in srgb,var(--a1) 14%,var(--surface));color:var(--a2)}
@media (prefers-color-scheme:dark){.chip{color:#fff}}
.purpose{border-left:3px solid var(--a1);padding:2px 0 2px 12px;margin:10px 0;color:var(--fg)}
.btn{display:inline-flex;align-items:center;gap:8px;font:inherit;font-weight:600;text-decoration:none;color:#fff;background:linear-gradient(135deg,var(--a1),var(--a2));padding:10px 18px;border-radius:10px}
.btn.ghost{background:var(--surface);color:var(--fg);border:1px solid var(--line)}.btn:hover{filter:brightness(1.06)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.kv{background:var(--surface-2);border-radius:10px;padding:10px 12px;font-size:13px;color:var(--muted)}
.kv b{display:block;color:var(--fg);font-size:15px}
.panel h3{margin:0 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
pre{margin:0;background:var(--code);color:var(--code-fg);padding:14px 16px;border-radius:10px;overflow:auto;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
.bad{color:#c62f2f;font-weight:600}@media (max-width:640px){.grid{grid-template-columns:1fr}}
"""


def page(body: str) -> HTMLResponse:
    a1, a2 = ACCENTS.get(SERVICE_ID, ("#4f46e5", "#7c3aed"))
    icon = ICONS.get(SERVICE_ID, ICONS["lms"])
    return HTMLResponse(f"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>{SVC['name']}</title>
<style>:root{{--a1:{a1};--a2:{a2}}}{CSS}</style>
<header class=top><div class=wrap><div class=icon><svg width=22 height=22 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="{icon}"/></svg></div>
<div><h1>{SVC['name']}</h1><small>Invented test service · asks Keycloak for the <b>{SVC['wants']}</b> profile</small></div></div></header>
<main><div class=wrap>{body}</div></main></html>""")


def pre(title: str, data) -> str:
    return f"<section class='card panel'>\n<h3>{title}</h3><pre>{html.escape(json.dumps(data, indent=2))}</pre>\n</section>"


def chips(names) -> str:
    return "<div class=chips>" + "".join(f"<span class=chip>{html.escape(str(n))}</span>" for n in names) + "</div>"


@app.get("/")
def home(request: Request):
    seen = request.session.get("seen")
    spec = SVC["declaration"]
    if not seen:
        return page(f"""<section class=card><h2>What this service promises</h2>
<p class=muted>Before it receives anything, the service signs this promise. TrustTrail refuses any request it does not cover.</p>
{chips(spec['attributes'])}
<p class=purpose>{html.escape(spec['purpose'])}</p>
<div class=grid><div class=kv><b>{spec['retention_days']} days</b>kept at most</div>
<div class=kv><b>{html.escape(SVC['wants'])}</b>profile requested</div>
<div class=kv><b>{html.escape(SVC['tier'].replace('_', ' '))}</b>base trust tier</div></div></section>
<p><a class=btn href="/login">Log in with university SSO</a></p>""")
    released = (seen.get("release") or {}).get("released")
    summary = (f"<section class=card><h2>What this service received</h2>"
               f"<p class=muted>Attribute values come only from TrustTrail, under the signed promise above. "
               f"The Keycloak token itself carries no personal data.</p>{chips(released)}</section>"
               if released else
               f"<section class=card><h2>Release refused</h2><p class=bad>"
               f"{html.escape(str((seen.get('release') or {}).get('error', 'unknown error')))}</p></section>")
    return page(summary
                + pre("From Keycloak (ID token)", seen["id_token"])
                + pre("From TrustTrail (/release)", seen["release"])
                + pre("Receipt payload (signed by TrustTrail)", seen.get("receipt"))
                + '<p><a class="btn ghost" href="/logout">Log out</a></p>')


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
