"""Phase 6 check: play two scripted participants through the real study flow
(Keycloak login and consent included), then check the analysis scores them right.

    .venv/bin/python scripts/check_study.py

Uses the reserved codes P98 and P99, which the analysis excludes by default and
which may be re-run. Needs the stack running and the host venv (see README).
"""
import json
import os
import warnings
import re
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CONFIG_DIR", str(ROOT / "config"))
sys.path.insert(0, str(ROOT / "trusttrail"))
warnings.filterwarnings("ignore", message="The httpx module is deprecated")
from app import study  # noqa: E402  (plan_for / cfg only; no database access here)

BASE = "http://localhost:8000"
PASSWORD = next(l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text().splitlines()
                if l.startswith("STUDENT_DEMO_PASSWORD="))


def client() -> httpx.Client:
    c = httpx.Client(follow_redirects=True, timeout=30)

    def browser_like_cookies(_):
        # Keycloak marks its cookies Secure; browsers still send them to http://localhost,
        # Python's cookie jar does not.
        for cookie in c.cookies.jar:
            cookie.secure = False
    c.event_hooks["response"] = [browser_like_cookies]
    return c


def form_action(r: httpx.Response) -> str:
    action = re.search(r'<form[^>]*action="([^"]+)"', r.text).group(1).replace("&amp;", "&")
    return str(r.url.join(action))


def run_participant(code: str, script: list[dict]):
    """script: per trial {"choice": [...] | "decline" | "accept", "q1": [...], "screen": (purpose_i, retention_i)}"""
    c = client()
    c.post(f"{BASE}/study/start", data={"code": code})
    for step, answers in zip(study.plan_for(code), script):
        c.get(f"{BASE}/study/task").raise_for_status()
        r = c.get(f"{BASE}/study/go")
        if step["condition"] == "baseline":
            if 'name="password"' in r.text:                      # first baseline task: log in
                r = c.post(form_action(r), data={"username": "asha", "password": PASSWORD})
            assert "Grant Access to" in r.text, f"{code}: expected Keycloak's consent page"
            code_value = re.search(r'name="code" value="([^"]+)"', r.text).group(1)
            button = {"accept": "Yes"} if answers["choice"] == "accept" else {"cancel": "No"}
            r = c.post(form_action(r), data={"code": code_value, **button})
        else:
            assert "You choose" in r.text, f"{code}: expected the TrustTrail screen"
            decision = "decline" if answers["choice"] == "decline" else "share"
            r = c.post(f"{BASE}/study/trusttrail", data={"attr": [] if decision == "decline" else answers["choice"],
                                                          "decision": decision, "ms": "4200"})
        assert r.url.path == "/study/q1", f"{code}: expected question 1, got {r.url}"
        r = c.post(f"{BASE}/study/q1", data={"q1": answers["q1"], "conf": "4"})
        if r.url.path == "/study/screen":
            opts = re.findall(r"name=(purpose|retention) value='([^']+)'", r.text)
            purposes = [v for k, v in opts if k == "purpose"]
            retention = [v for k, v in opts if k == "retention"]
            pi, ri = answers["screen"]
            r = c.post(f"{BASE}/study/screen", data={"purpose": purposes[pi].replace("&#x27;", "'"),
                                                      "retention": retention[ri].replace("&#x27;", "'"),
                                                      "l0": "4", "l1": "3", "l2": "5", "comment": ""})
    assert r.url.path == "/study/done", f"{code}: did not reach the end ({r.url})"


ALL = ["name", "email", "roll_no", "department", "program", "year"]
# P99: odd -> Keycloak first; n % 4 == 3 -> task F first. Answers everything correctly.
P99 = [{"choice": "accept", "q1": ALL + ["account_id"]},                               # baseline F
       {"choice": "accept", "q1": ALL + ["account_id"], "screen": (2, 2)},             # baseline P ("did not say")
       {"choice": ALL, "q1": ALL + ["service_id"]},                                    # TrustTrail F
       {"choice": ["department", "program", "year"],
        "q1": ["department", "program", "year", "service_id"], "screen": (0, 0)}]     # TrustTrail P
# P98: even -> TrustTrail first; n % 4 == 2 -> task P first. Makes mistakes on purpose.
P98 = [{"choice": ["department", "program", "year", "email"], "q1": ["department", "program", "year"]},
       {"choice": "decline", "q1": ["nothing"], "screen": (2, 3)},
       {"choice": "decline", "q1": ["nothing"]},
       {"choice": "accept", "q1": ["name", "email", "roll_no"], "screen": (2, 2)}]


def main():
    for code, script in (("P99", P99), ("P98", P98)):
        run_participant(code, script)
        print(f"{code}: completed 4 tasks and both screen questionnaires")
    out = subprocess.run(["docker", "compose", "exec", "-T", "trusttrail", "python", "-m", "eval.analyze_study",
                          "--participants", "P98,P99", "--json"], cwd=ROOT, capture_output=True, text=True, check=True)
    a = json.loads(out.stdout)
    checks = {
        "both participants complete": a["complete"] == ["P98", "P99"],
        "chose as intended: TrustTrail P (P99 yes, P98 no)": sorted(a["intended"]["trusttrail/P"]) == [0, 1],
        "chose as intended: Keycloak P impossible (0/2)": a["intended"]["baseline/P"] == [0, 0],
        "chose as intended: Keycloak F (P99 yes, P98 yes)": a["intended"]["baseline/F"] == [1, 1],
        "Q1 exactly right: P99 all 4, P98 2 of 4": sum(a["comprehension"]["trusttrail"]["exact"])
            + sum(a["comprehension"]["baseline"]["exact"]) == 6,
        "purpose/retention scored per screen": a["screens"]["baseline"]["purpose"].count(1) == 2
            and a["screens"]["trusttrail"]["retention"] == [0, 1],
    }
    for name, ok in checks.items():
        print(("PASS  " if ok else "FAIL  ") + name)
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
