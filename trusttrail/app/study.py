"""Usability study (Phase 6): Keycloak's default consent screen vs. a TrustTrail consent screen.

Participants act as an invented student (config/study.yaml) and do four short
tasks: two scenarios on each screen. Condition and scenario order are
counterbalanced by participant number. Only the participant code, choices,
answers and timings are stored, in their own database (study.db); no names.

The TrustTrail screen here is a study PROTOTYPE: in the running system students
cannot yet deselect attributes per release (see README, Phase 6 limits).
"""
import html
import json
import os
import re
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import settings

PUBLIC_URL = os.environ.get("TT_PUBLIC_URL", "http://localhost:8000")
ATTRS = ["name", "email", "roll_no", "department", "program", "year"]
Q1_OPTIONS = ATTRS + ["service_id", "account_id"]
NOTHING = "nothing"
TEST_CODES = {"P98", "P99"}   # reserved for scripts/check_study.py; excluded from analysis
SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    participant TEXT NOT NULL, trial INTEGER NOT NULL, condition TEXT NOT NULL, scenario TEXT NOT NULL,
    outcome TEXT NOT NULL,          -- shared | declined
    received TEXT NOT NULL,         -- JSON: what the service actually got (Q1_OPTIONS keys)
    matched INTEGER NOT NULL,       -- 1 if what was shared is exactly what the task asked for
    decision_ms INTEGER,            -- TrustTrail: screen shown -> choice. Baseline: includes any login.
    q1 TEXT, q1_confidence INTEGER, recorded_at TEXT NOT NULL,
    PRIMARY KEY (participant, trial));
CREATE TABLE IF NOT EXISTS conditions (
    participant TEXT NOT NULL, condition TEXT NOT NULL,
    purpose_answer TEXT, purpose_correct INTEGER, retention_answer TEXT, retention_correct INTEGER,
    likert TEXT, comment TEXT, recorded_at TEXT NOT NULL,
    PRIMARY KEY (participant, condition));
"""
DB_PATH = settings.DATA_DIR / "study.db"
_lock = threading.Lock()


def cfg() -> dict:
    return settings.load("study")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def plan_for(code: str) -> list[dict]:
    """4 groups by participant number: which screen first x which scenario first."""
    n = int(code[1:])
    conditions = ["baseline", "trusttrail"] if n % 2 else ["trusttrail", "baseline"]
    scenarios = ["P", "F"] if n % 4 in (1, 2) else ["F", "P"]
    return [{"condition": c, "scenario": s} for c in conditions for s in scenarios]


def received_for(condition: str, outcome: str, chosen: list[str]) -> list[str]:
    if outcome == "declined":
        return []
    if condition == "baseline":
        return list(cfg()["baseline_receives"])
    return sorted(set(chosen) | set(cfg()["trusttrail_always"]))


def matched(scenario: str, outcome: str, received: list[str]) -> bool:
    intended = set(cfg()["scenarios"][scenario]["intended"])
    return outcome == "shared" and {a for a in received if a in ATTRS} == intended


def delete_by(scenario: str) -> str:
    return (date.today() + timedelta(days=cfg()["scenarios"][scenario]["keep_days"])).strftime("%d %B %Y")


# --- HTML ------------------------------------------------------------------------------

CSS = """
:root{--fg:#1d2433;--muted:#5d6678;--line:#dfe3ea;--bg:#f7f8fa;--accent:#2f5bd3;--ok:#1e7d4f}
*{box-sizing:border-box}body{margin:0;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--fg);background:var(--bg)}
main{max-width:640px;margin:0 auto;padding:24px 16px}.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:20px;margin:16px 0}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:0 0 8px}.muted{color:var(--muted);font-size:14px}
.task{border-left:4px solid var(--accent);background:#eef2fd}.btn{font:inherit;border:0;border-radius:8px;padding:10px 18px;cursor:pointer;
background:var(--accent);color:#fff;text-decoration:none;display:inline-block}.btn.secondary{background:#fff;color:var(--fg);border:1px solid var(--line)}
label.opt{display:flex;gap:10px;align-items:flex-start;padding:10px;border:1px solid var(--line);border-radius:8px;margin:6px 0;cursor:pointer}
label.opt input{margin-top:4px;width:18px;height:18px}.badge{display:inline-block;font-size:13px;padding:2px 8px;border-radius:999px;background:#eef1f6}
.fixed{padding:8px 10px;border-radius:8px;background:#f2f4f7;margin:6px 0}.likert{display:flex;gap:8px;flex-wrap:wrap}
.likert label{border:1px solid var(--line);border-radius:6px;padding:4px 10px;cursor:pointer}dl{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:0}
dt{color:var(--muted)}.proto{font-size:12px;color:var(--muted);text-align:center;margin-top:24px}
"""


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"<!doctype html><html lang=en><meta charset=utf-8>"
                        f"<meta name=viewport content='width=device-width,initial-scale=1'>"
                        f"<title>{html.escape(title)}</title><style>{CSS}</style><main>{body}</main></html>")


def e(text) -> str:
    return html.escape(str(text))


def persona_card() -> str:
    p = cfg()["persona"]
    return (f"<div class=card><h2>You are playing {e(p['name'])}</h2><dl>"
            f"<dt>Email</dt><dd>{e(p['email'])}</dd><dt>Roll number</dt><dd>{e(p['roll_no'])}</dd>"
            f"<dt>Department</dt><dd>{e(p['department'])}</dd><dt>Programme</dt><dd>{e(p['program'])}, "
            f"year {e(p['year'])}</dd></dl><p class=muted>An invented student. Never enter your own details.</p></div>")


# --- routes --------------------------------------------------------------------------------

def router() -> APIRouter:
    r = APIRouter(prefix="/study")
    oauth = OAuth()
    for s in cfg()["scenarios"].values():
        oauth.register(s["baseline_client"], client_id=s["baseline_client"],
                       client_secret=os.environ.get("STUDY_CLIENT_SECRET", ""),
                       server_metadata_url=f"{settings.KC_INTERNAL_URL}/realms/{settings.REALM}/.well-known/openid-configuration",
                       client_kwargs={"scope": "openid profile email"})

    def state(request: Request) -> dict | None:
        return request.session.get("study")

    def current(request: Request) -> tuple[dict, dict] | None:
        st = state(request)
        if not st or st["i"] >= len(st["plan"]):
            return None
        return st, st["plan"][st["i"]]

    def record_trial(st: dict, step: dict, outcome: str, chosen: list[str], decision_ms: int | None):
        received = received_for(step["condition"], outcome, chosen)
        st["received"] = received
        with _lock, db() as conn:
            conn.execute("INSERT OR REPLACE INTO trials VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (st["participant"], st["i"] + 1, step["condition"], step["scenario"], outcome,
                          json.dumps(received), int(matched(step["scenario"], outcome, received)),
                          decision_ms, None, None, datetime.now(timezone.utc).isoformat()))

    @r.get("", response_class=HTMLResponse)
    def start_page(error: str = ""):
        msg = f"<p style='color:#b3261e'>{e(error)}</p>" if error else ""
        return page("Study", f"""<h1>Consent screen study</h1>
<p class=muted>Facilitator: enter the next participant code from the sign-up sheet (P01, P02, ...).
Never enter names. The participant then follows the screens.</p>{msg}
<form class=card method=post action=/study/start><label>Participant code<br>
<input name=code required pattern="P[0-9]{{2}}" placeholder=P01 style="font:inherit;padding:8px;width:8em"></label>
<p><button class=btn>Start</button></p></form>""")

    @r.post("/start")
    async def start(request: Request):
        code = (await request.form()).get("code", "").strip().upper()
        if not re.fullmatch(r"P\d{2}", code) or code == "P00":
            return RedirectResponse("/study?error=Use+a+code+like+P01", status_code=303)
        with _lock, db() as conn:
            if code in TEST_CODES:      # test runs may repeat; real codes never overwrite
                conn.execute("DELETE FROM trials WHERE participant = ?", (code,))
                conn.execute("DELETE FROM conditions WHERE participant = ?", (code,))
            if conn.execute("SELECT 1 FROM trials WHERE participant = ?", (code,)).fetchone():
                return RedirectResponse(f"/study?error={code}+already+has+results;+use+the+next+code",
                                        status_code=303)
        request.session["study"] = {"participant": code, "plan": plan_for(code), "i": 0}
        return RedirectResponse("/study/task", status_code=303)

    @r.get("/task", response_class=HTMLResponse)
    def task(request: Request):
        cur = current(request)
        if cur is None:
            return RedirectResponse("/study")
        st, step = cur
        s = cfg()["scenarios"][step["scenario"]]
        login_hint = ""
        if step["condition"] == "baseline":
            login_hint = (f"<p class=muted>If you are asked to log in, use username "
                          f"<b>{e(cfg()['persona']['username'])}</b> and password "
                          f"<b>{e(os.environ.get('STUDENT_DEMO_PASSWORD', ''))}</b> (a demo account).</p>")
        return page("Task", f"""<p class=muted>Task {st['i'] + 1} of {len(st['plan'])}</p>
<div class="card task"><h2>{e(s['service'])}</h2><p>{e(s['task'])}</p></div>{persona_card()}{login_hint}
<p>When you are ready, press Continue. You will see a screen from the {e(s['service'])}.</p>
<a class=btn href=/study/go>Continue</a>""")

    @r.get("/go")
    async def go(request: Request):
        cur = current(request)
        if cur is None:
            return RedirectResponse("/study")
        st, step = cur
        st["shown_at"] = time.time()
        request.session["study"] = st
        if step["condition"] == "trusttrail":
            return RedirectResponse("/study/trusttrail")
        client = oauth.create_client(cfg()["scenarios"][step["scenario"]]["baseline_client"])
        # prompt=consent: show Keycloak's consent page every time, even if this
        # demo account already consented for an earlier participant.
        return await client.authorize_redirect(request, f"{PUBLIC_URL}/study/baseline/callback", prompt="consent")

    @r.get("/baseline/callback")
    async def baseline_callback(request: Request):
        cur = current(request)
        if cur is None:
            return RedirectResponse("/study")
        st, step = cur
        if request.query_params.get("error"):          # "No" on Keycloak's consent page
            outcome = "declined"
        else:
            client = oauth.create_client(cfg()["scenarios"][step["scenario"]]["baseline_client"])
            await client.authorize_access_token(request)
            outcome = "shared"
        record_trial(st, step, outcome, [], int((time.time() - st.get("shown_at", time.time())) * 1000))
        request.session["study"] = st
        return RedirectResponse("/study/q1", status_code=303)

    def trusttrail_html(key: str, preview: bool = False) -> str:
        s = cfg()["scenarios"][key]
        labels = cfg()["labels"]
        options = "".join(f"<label class=opt><input type=checkbox name=attr value={e(a)}>"
                          f"<span>{e(labels[a])}</span></label>" for a in s["optional"])
        signed = date.today().strftime("%d %B %Y")
        action = "" if preview else "action=/study/trusttrail"
        note = " · PREVIEW, nothing is recorded" if preview else ""
        return f"""
<div class=card><p class=muted>University sign-in · TrustTrail</p>
<h1>{e(s['service'])} would like some of your details</h1>
<p><span class=badge>{e(s['tier'])}</span></p>
<h2 style="margin-top:16px">What it will use them for</h2>
<p>“{e(s['purpose'])}”</p>
<p class=muted>The service signed this promise on {signed}. It must delete your details by
<b>{delete_by(key)}</b>. Every release is recorded, and you can see it later on your TrustTrail page.</p>
<form method=post {action} id=f onsubmit="return {'false' if preview else 'true'}">
<h2>Always shared</h2>
<div class=fixed>{e(labels['service_id'])}</div><div class=fixed>That you are a current student</div>
<h2 style="margin-top:16px">You choose</h2>
<p class=muted>Tick only what you want to share. Nothing is ticked for you.</p>{options}
<input type=hidden name=ms id=ms>
<p style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px">
<button class=btn name=decision value=share>Share selected</button>
<button class="btn secondary" name=decision value=decline>Don't share anything</button></p></form></div>
<p class=proto>Study prototype · invented data · not connected to real university systems{note}</p>
<script>const t0=performance.now();document.getElementById('f').addEventListener('submit',
()=>{{document.getElementById('ms').value=Math.round(performance.now()-t0)}});</script>"""

    @r.get("/trusttrail", response_class=HTMLResponse)
    def trusttrail_screen(request: Request):
        cur = current(request)
        if cur is None or cur[1]["condition"] != "trusttrail":
            return RedirectResponse("/study")
        s = cfg()["scenarios"][cur[1]["scenario"]]
        return page(f"{s['service']} asks for your data", trusttrail_html(cur[1]["scenario"]))

    @r.get("/preview/{key}", response_class=HTMLResponse)
    def preview(key: str):
        """The TrustTrail screen for task P or F, for screenshots and piloting. Records nothing."""
        if key not in cfg()["scenarios"]:
            return RedirectResponse("/study")
        return page("Preview", trusttrail_html(key, preview=True))

    @r.post("/trusttrail")
    async def trusttrail_choice(request: Request):
        cur = current(request)
        if cur is None or cur[1]["condition"] != "trusttrail":
            return RedirectResponse("/study", status_code=303)
        st, step = cur
        form = await request.form()
        offered = set(cfg()["scenarios"][step["scenario"]]["optional"])
        chosen = [a for a in form.getlist("attr") if a in offered]
        outcome = "declined" if form.get("decision") == "decline" else "shared"
        ms = form.get("ms")
        record_trial(st, step, outcome, chosen if outcome == "shared" else [], int(ms) if ms and ms.isdigit() else None)
        request.session["study"] = st
        return RedirectResponse("/study/q1", status_code=303)

    @r.get("/q1", response_class=HTMLResponse)
    def q1_page(request: Request):
        cur = current(request)
        if cur is None:
            return RedirectResponse("/study")
        s = cfg()["scenarios"][cur[1]["scenario"]]
        labels = cfg()["labels"]
        boxes = "".join(f"<label class=opt><input type=checkbox name=q1 value={k}><span>{e(labels[k])}</span></label>"
                        for k in Q1_OPTIONS)
        boxes += f"<label class=opt><input type=checkbox name=q1 value={NOTHING}><span>Nothing at all</span></label>"
        scale = "".join(f"<label><input type=radio name=conf value={i} required> {i}</label>" for i in range(1, 6))
        return page("Question", f"""<form class=card method=post action=/study/q1>
<h2>Which of these does the {e(s['service'])} now have?</h2><p class=muted>Tick all that apply.</p>{boxes}
<h2 style="margin-top:16px">How sure are you?</h2><p class=muted>1 = guessing, 5 = completely sure</p>
<div class=likert>{scale}</div><p><button class=btn>Next</button></p></form>""")

    @r.post("/q1")
    async def q1_answer(request: Request):
        cur = current(request)
        if cur is None:
            return RedirectResponse("/study", status_code=303)
        st, step = cur
        form = await request.form()
        with _lock, db() as conn:
            conn.execute("UPDATE trials SET q1 = ?, q1_confidence = ? WHERE participant = ? AND trial = ?",
                         (json.dumps(sorted(form.getlist("q1"))), int(form.get("conf", 0)),
                          st["participant"], st["i"] + 1))
        # After the second task on a screen, ask about that screen as a whole.
        last_of_condition = st["i"] + 1 >= len(st["plan"]) or st["plan"][st["i"] + 1]["condition"] != step["condition"]
        st["i"] += 1
        request.session["study"] = st
        if last_of_condition:
            st["condition_done"] = step["condition"]
            request.session["study"] = st
            return RedirectResponse("/study/screen", status_code=303)
        return RedirectResponse("/study/task", status_code=303)

    def screen_questions(condition: str) -> tuple[list[str], list[str], str, str]:
        p = cfg()["scenarios"]["P"]
        purposes = [p["purpose"], "To show you advertising from partner companies",
                    "The screen did not say", "I don't know"]
        retention = [f"Until {delete_by('P')}", "For as long as it likes", "The screen did not say", "I don't know"]
        truth = (purposes[0], retention[0]) if condition == "trusttrail" else (purposes[2], retention[2])
        return purposes, retention, truth[0], truth[1]

    @r.get("/screen", response_class=HTMLResponse)
    def screen_page(request: Request):
        st = state(request)
        if not st or "condition_done" not in st:
            return RedirectResponse("/study")
        purposes, retention, _, _ = screen_questions(st["condition_done"])

        def radios(name, opts):
            return "".join(f"<label class=opt><input type=radio name={name} value='{e(o)}' required><span>{e(o)}</span></label>"
                           for o in opts)
        likert = "".join(f"<p>{e(text)}</p><div class=likert>"
                         + "".join(f"<label><input type=radio name=l{i} value={v} required> {v}</label>" for v in range(1, 6))
                         + "</div>" for i, text in enumerate(cfg()["likert"]))
        return page("About these screens", f"""<form class=card method=post action=/study/screen>
<p class=muted>Think about the two screens you just used.</p>
<h2>What did the Learning System say it would use your data for?</h2>{radios('purpose', purposes)}
<h2 style="margin-top:16px">Until when may the Learning System keep your data?</h2>{radios('retention', retention)}
<h2 style="margin-top:16px">How much do you agree?</h2><p class=muted>1 = strongly disagree, 5 = strongly agree</p>{likert}
<h2 style="margin-top:16px">Anything else? (optional)</h2>
<textarea name=comment rows=3 style="width:100%;font:inherit" placeholder="Please don't include names or personal details"></textarea>
<p><button class=btn>Next</button></p></form>""")

    @r.post("/screen")
    async def screen_answer(request: Request):
        st = state(request)
        if not st or "condition_done" not in st:
            return RedirectResponse("/study", status_code=303)
        form = await request.form()
        condition = st.pop("condition_done")
        _, _, purpose_truth, retention_truth = screen_questions(condition)
        likert = [int(form.get(f"l{i}", 0)) for i in range(len(cfg()["likert"]))]
        with _lock, db() as conn:
            conn.execute("INSERT OR REPLACE INTO conditions VALUES (?,?,?,?,?,?,?,?,?)",
                         (st["participant"], condition, form.get("purpose"), int(form.get("purpose") == purpose_truth),
                          form.get("retention"), int(form.get("retention") == retention_truth), json.dumps(likert),
                          (form.get("comment") or "").strip()[:1000], datetime.now(timezone.utc).isoformat()))
        request.session["study"] = st
        return RedirectResponse("/study/task" if st["i"] < len(st["plan"]) else "/study/done", status_code=303)

    @r.get("/done", response_class=HTMLResponse)
    def done(request: Request):
        st = state(request) or {}
        request.session.pop("study", None)
        return page("Thank you", f"""<div class=card><h1>Thank you!</h1>
<p>That's all. Your answers are stored under the code <b>{e(st.get('participant', ''))}</b> only.</p>
<p class=muted>Facilitator: hand back the sheet, then start the next participant.</p>
<a class="btn secondary" href=/study>Next participant</a></div>""")

    return r
