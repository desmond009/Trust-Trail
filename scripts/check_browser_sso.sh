#!/bin/bash
# Phase 1 check of the real browser flow (authorization code + SSO), using curl
# as the browser: one cookie jar, so the second login reuses the Keycloak session.
# Shows what library and LMS each learn about the same student, then checks that
# nothing in what they received links the two pseudonyms.
# Usage: scripts/check_browser_sso.sh [username] [password]
set -euo pipefail
USER_NAME=${1:-asha}; PASSWORD=${2:-student123}
JAR=$(mktemp); OUT=$(mktemp -d); trap 'rm -rf "$JAR" "$OUT"' EXIT
c() { curl -s --max-time 20 -c "$JAR" -b "$JAR" "$@"; }

login_at() {  # $1 = service URL, $2 = name for output files
  auth_url=$(c -o /dev/null -w '%{redirect_url}' "$1/login")
  page=$(c "$auth_url")
  if grep -q 'name="password"' <<<"$page"; then
    action=$(grep -o 'action="[^"]*"' <<<"$page" | head -1 | sed 's/^action="//; s/"$//; s/&amp;/\&/g')
    callback=$(c -o /dev/null -w '%{redirect_url}' --data-urlencode "username=$USER_NAME" \
               --data-urlencode "password=$PASSWORD" "$action")
  else
    callback=$(c -o /dev/null -w '%{redirect_url}' "$auth_url")   # already logged in (SSO)
  fi
  echo "$callback" > "$OUT/$2.callback"
  c -o /dev/null "$callback"
  c "$1/" | sed -n '/<h3>/,/<\/pre>/p' | sed 's/<[^>]*>//g; s/&quot;/"/g' | tee "$OUT/$2.page"
}

echo "===== library.localhost:8001 ====="; login_at http://library.localhost:8001 library
echo "===== lms.localhost:8002 (same browser, single sign-on) ====="; login_at http://lms.localhost:8002 lms

echo "===== checks ====="
fail=0
check() { if eval "$2"; then echo "PASS  $1"; else echo "FAIL  $1"; fail=1; fi; }
sub_of() { grep -m1 '"sub"' "$OUT/$1.page" | sed 's/.*: "//; s/".*//'; }
check "library and LMS got different sub"        '[ "$(sub_of library)" != "$(sub_of lms)" ]'
check "no sid in either ID token"                '! grep -q "\"sid\"" "$OUT/library.page" "$OUT/lms.page"'
check "no session_state in either login redirect" '! grep -q "session_state=" "$OUT/library.callback" "$OUT/lms.callback"'
check "no auth_time in either ID token"          '! grep -q "\"auth_time\"" "$OUT/library.page" "$OUT/lms.page"'
exit $fail
