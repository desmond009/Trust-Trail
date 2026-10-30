#!/bin/bash
# Phase 3 check of the student dashboard through the real browser login (curl as browser).
# Logs the student into the library and LMS (creating two releases), then into the
# dashboard, and checks what the dashboard shows and verifies.
# Usage: scripts/check_dashboard.sh [username] [password]
set -euo pipefail
USER_NAME=${1:-asha}; PASSWORD=${2:-student123}
JAR=$(mktemp); trap 'rm -f "$JAR"' EXIT
c() { curl -s --max-time 20 -c "$JAR" -b "$JAR" "$@"; }

login_via() {  # $1 = URL that starts the login, $2 = name for messages
  auth_url=$(c -o /dev/null -w '%{redirect_url}' "$1")
  page=$(c "$auth_url")
  if grep -q 'name="password"' <<<"$page"; then
    action=$(grep -o 'action="[^"]*"' <<<"$page" | head -1 | sed 's/^action="//; s/"$//; s/&amp;/\&/g')
    callback=$(c -o /dev/null -w '%{redirect_url}' --data-urlencode "username=$USER_NAME" \
               --data-urlencode "password=$PASSWORD" "$action")
  else
    callback=$(c -o /dev/null -w '%{redirect_url}' "$auth_url")
  fi
  c -o /dev/null "$callback"
  echo "logged in to $2"
}

login_via http://library.localhost:8001/login library
login_via http://lms.localhost:8002/login lms
login_via http://localhost:8000/dashboard/login dashboard

# Anchor now (admin) so the newest release is on-chain before we verify it.
ADMIN_TOKEN=$(grep '^TRUSTTRAIL_ADMIN_TOKEN=' "$(dirname "$0")/../.env" | cut -d= -f2-)
curl -s --max-time 120 -X POST -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8000/anchors/run >/dev/null

releases=$(c http://localhost:8000/dashboard/api/releases)
newest=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["releases"][0]["entry_id"])' "$releases")
verify=$(c "http://localhost:8000/dashboard/api/verify/$newest")
receipt=$(c "http://localhost:8000/dashboard/receipts/$newest")
other=$(c -o /dev/null -w '%{http_code}' "http://localhost:8000/dashboard/receipts/999999")
# The downloaded receipt, checked with only the file and the chain (no TrustTrail API or DB).
standalone=$(cd "$(dirname "$0")/.." && echo "$receipt" | docker compose exec -T trusttrail python -m scripts.verify_receipt - 2>&1) \
  && standalone_ok=1 || standalone_ok=0

echo "===== standalone receipt check (file + chain only) ====="
echo "$standalone"

python3 - "$releases" "$verify" "$receipt" "$other" "$newest" "$standalone_ok" <<'PY'
import json, sys
releases, verify, receipt = (json.loads(x) for x in sys.argv[1:4])
other, newest, standalone_ok = sys.argv[4], int(sys.argv[5]), sys.argv[6] == "1"

print("===== dashboard: newest releases =====")
print("student:", releases["student"])
for r in releases["releases"][:4]:
    print(f"#{r['entry_id']:<4} {r['service']:18} {r['profile']:9} delete by {r['delete_by']}  {r['attributes']}")

print("===== checks =====")
checks = {
    "dashboard lists library and LMS releases":
        {"Digital Library", "Learning System"} <= {r["service"] for r in releases["releases"]},
    f"verify button: all checks pass for entry #{newest}": verify["ok"],
    "receipt download has receipt, entry and declaration":
        bool(receipt["receipt_jws"]) and receipt["ledger_entry"]["entry_id"] == newest
        and bool(receipt["service_declaration_jws"]),
    "an entry that is not yours returns 404": other == "404",
    f"verify button: entry #{newest} matches the blockchain anchor": verify["anchor"]["status"] == "anchored",
    "downloaded receipt verifies against the chain without TrustTrail": standalone_ok,
}
for name, ok in checks.items():
    print(("PASS  " if ok else "FAIL  ") + name)
sys.exit(0 if all(checks.values()) else 1)
PY
