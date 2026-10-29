"""A generic invented campus service (library / LMS / exam portal).

It logs students in through Keycloak with an ordinary OIDC library (Authlib),
asking for the profile scope from config/services.yaml, then asks TrustTrail
for the attributes. The page shows exactly what the service ended up knowing.
"""
import html
import json
import os

import httpx
import yaml
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

SERVICE_ID = os.environ["SERVICE_ID"]
SVC = yaml.safe_load(open("/config/services.yaml"))["services"][SERVICE_ID]
KC = os.environ.get("KC_INTERNAL_URL", "http://keycloak:8080")
REALM = os.environ.get("KC_REALM", "trusttrail")
TRUSTTRAIL = os.environ.get("TRUSTTRAIL_URL", "http://trusttrail:8000")

app = FastAPI(title=SVC["name"])
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"],
                   session_cookie=f"{SERVICE_ID}_session")
oauth = OAuth()
oauth.register(
    "keycloak", client_id=SERVICE_ID, client_secret=os.environ["CLIENT_SECRET"],
    server_metadata_url=f"{KC}/realms/{REALM}/.well-known/openid-configuration",
    client_kwargs={"scope": f"openid profile-{SVC['wants']}"})


def page(body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><meta charset=utf-8><title>{SVC['name']}</title>
<style>body{{font-family:system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}}
pre{{background:#f4f4f4;padding:1rem;overflow:auto}}</style>
<h1>{SVC['name']}</h1><p><small>invented test service · asks for profile <b>{SVC['wants']}</b></small></p>{body}""")


@app.get("/")
def home(request: Request):
    seen = request.session.get("seen")
    if not seen:
        return page('<p><a href="/login">Log in with university SSO</a></p>')
    return page(f"""<h2>What this service learned</h2>
<h3>From Keycloak (ID token)</h3><pre>{html.escape(json.dumps(seen['id_token'], indent=2))}</pre>
<h3>From TrustTrail (/release)</h3><pre>{html.escape(json.dumps(seen['release'], indent=2))}</pre>
<p><a href="/logout">Log out</a></p>""")


@app.get("/login")
async def login(request: Request):
    return await oauth.keycloak.authorize_redirect(request, f"{SVC['url']}/callback")


@app.get("/callback")
async def callback(request: Request):
    token = await oauth.keycloak.authorize_access_token(request)
    r = httpx.post(f"{TRUSTTRAIL}/release",
                   headers={"Authorization": f"Bearer {token['access_token']}"})
    request.session["seen"] = {"id_token": dict(token["userinfo"]),
                               "release": r.json() if r.status_code == 200 else {"refused": r.text}}
    return RedirectResponse("/")


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
