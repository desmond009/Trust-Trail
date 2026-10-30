# TrustTrail

Privacy-aware federated login with accountable, purpose-bound disclosure.
Student project, IIIT Dharwad. Follow-up to Werner, Westphall & Westphall (2017),
"Cloud Identity Management: A Survey on Privacy Strategies".

All students, services and secrets in this repo are invented demo data.

## Run it

```bash
cp .env.example .env                                         # local demo values only
docker compose up -d --build                                 # Keycloak + TrustTrail + 3 test services
docker compose run --rm trusttrail python -m scripts.seed    # creates/RESETS the realm
```

| What | URL |
|---|---|
| Keycloak admin console | http://localhost:8080 (credentials in `.env`) |
| TrustTrail API | http://localhost:8000/docs |
| Student dashboard | http://localhost:8000/dashboard |
| Digital Library | http://library.localhost:8001 |
| Learning System | http://lms.localhost:8002 |
| Examination Portal | http://exam.localhost:8003 |

The first build compiles the custom Keycloak mapper with Maven inside Docker (a few minutes,
needs internet). TrustTrail and service code is mounted into the containers, so edits to
scripts and tests apply without rebuilding; restart a container after changing app code.

Students: `asha`, `rohan`, `meera`, `kabir`, `zoya`, password from `STUDENT_DEMO_PASSWORD`.
`*.localhost` resolves to your machine in Chrome, Firefox and curl without any hosts-file change.

## Phase 1: profiles and per-service pseudonyms

**How a login works**

1. The service sends the student to Keycloak asking for `openid profile-<x>`.
2. Keycloak authenticates the student and grants the profile scope only if it is assigned
   to that client (the tier cap). Over-cap requests fail with `invalid_scope`.
3. The tokens carry a **pairwise `sub`** (different for every service) and no personal claims.
4. The service calls `POST /release` on TrustTrail with its access token. TrustTrail verifies
   the token, maps the pairwise `sub` back to the student, and returns only the attributes of
   the granted profile (`config/profiles.yaml`).

Keycloak decides *which* profile a service may get; TrustTrail decides *what* that profile
contains and is the only path for attribute values. That is what will let Phase 2 refuse
releases and Phase 3 log every one.

| Profile | Released by TrustTrail |
|---|---|
| anonymous | affiliation |
| pseudonym | sub, affiliation |
| partial | sub, affiliation, department, program, year |
| total | sub, affiliation, department, program, year, name, email, roll_no |

| Service | Wants | Initial tier | Highest profile Keycloak will grant |
|---|---|---|---|
| library | pseudonym | untrusted | pseudonym |
| lms | partial | semi_trusted | partial |
| exam | total | fully_trusted | total |

**Keycloak features used (26.8.1):**
- `oidc-sha256-pairwise-sub-mapper` on each service client (empty salt, so Keycloak picks a random one)
- **one custom protocol mapper**, `trusttrail-strip-sid-mapper` ([keycloak/strip-sid-mapper](keycloak/strip-sid-mapper)),
  built into the Keycloak image by `keycloak/Dockerfile`. It implements the `protocol-mapper`
  SPI (`OIDCAccessTokenMapper`, `OIDCIDTokenMapper`) and removes `sid` (see below).
  Keycloak logs a warning at startup that this SPI is internal and may change between versions.
- client attributes `exclude.session.state.from.auth.response=true` and `use.refresh.tokens=false` on service clients
- client scopes `profile-anonymous|pseudonym|partial|total`, assigned as *optional* client scopes up to the tier cap
- realm default scopes removed from service clients except `basic`; the `auth_time` mapper removed from `basic`
- user profile `unmanagedAttributePolicy = ADMIN_EDIT` for the extra student attributes
- Admin REST API (seed script, and TrustTrail's read-only service account with `view-users` and `view-clients`)
- password grant on the test clients, **for test scripts only**

**Mapping table.** TrustTrail recomputes each pairwise `sub` with a port of Keycloak's
algorithm (`app/pseudonyms.py`) and stores student ↔ pseudonym rows in
`/data/identity_map.db`, kept apart from the ledger. A test checks that the recomputation
matches Keycloak for every student and service.

### Demo

```bash
docker compose exec trusttrail python -m scripts.demo_phase1   # pseudonym table, releases, tier-cap matrix
scripts/check_browser_sso.sh                                   # real browser flow (curl as browser), library then LMS
```

`check_browser_sso.sh` ends with PASS/FAIL checks: different `sub`, and no `sid`,
`session_state` or `auth_time` reaching either service. To see why the custom mapper exists,
delete "strip session id" from the library and LMS clients in the admin console and rerun it:
the `sid` check fails because both services receive the same session ID. Re-seed afterwards.

Or by hand: open the library, log in as `asha`, then open the LMS in the same browser.
Single sign-on logs you straight in, and each page shows a different `sub`.

### Tests

```bash
docker compose exec trusttrail pytest -m "not integration"   # unit: pairwise algorithm, profile filtering, declarations
docker compose exec trusttrail pytest                        # + integration against the seeded stack
```

## Phase 2: signed purpose declarations and receipts

Before a service gets any attribute, it signs a **purpose declaration** (which attributes, why,
and when it will delete them) with its own key. TrustTrail checks the signature, stores the
declaration verbatim, and refuses any release the declaration does not cover. Each release
returns a **receipt** signed by TrustTrail that links what was released to what was promised.
This gives non-repudiable evidence of what a service promised. It does not guarantee the
service keeps the promise.

**Flow**
1. The service registers its public key: `POST /services/keys` (authenticated as the service).
2. The service signs a declaration and submits it: `POST /declarations`.
3. A student logs in through Keycloak (Phase 1).
4. The service calls `POST /release` with the student's token and the `declaration_id`.

Test services generate their key on first use into the `svc-keys` Docker volume, and their
declarations come from `config/services.yaml`. Declaration rules (accepted algorithms, maximum
lifetime, clock skew) are in `config/declarations.yaml`. TrustTrail's receipt key is generated
into the `tt-data` volume. No private key is ever in the repo.

### API

**`POST /services/keys`**: header `Authorization: Bearer <client-credentials token of the service>`.
A student's login token for the same service is rejected, because only client-credentials tokens
carry `client_id`.
```json
{"keys": [{"kty": "EC", "crv": "P-256", "x": "...", "y": "...", "kid": "<RFC 7638 thumbprint>", "alg": "ES256", "use": "sig"}]}
```
→ `200 {"client_id": "lms", "kids": ["..."]}`. Keys are append-only: re-registering the same key
is fine, but reusing a `kid` for a different key returns `409 kid_conflict`, so old declarations
stay verifiable.

**`POST /declarations`**: body `{"declaration": "<compact JWS>"}`. No bearer token; the
signature is the authentication.

| JWS header | |
|---|---|
| `alg` | `ES256` or `RS256` |
| `kid` | a key registered by this service |
| `typ` | `purpose-declaration+jwt` |

| JWS payload | |
|---|---|
| `client_id` | the service, e.g. `"lms"` |
| `aud` | `"trusttrail"` |
| `attributes` | names from the profile vocabulary; `sub` = the per-service pseudonym |
| `purpose` | free text, 1–500 characters |
| `retention_until` | ISO date by which the service promises to delete the data |
| `nonce` | unique per service (replay protection) |
| `iat`, `exp` | when the declaration was issued and until when it may back releases (max 90 days) |

→ `201` with the stored declaration: `declaration_id` (first 16 hex digits of `jws_sha256`),
`client_id`, `nonce`, `attributes`, `purpose`, `retention_until`, `issued_at`, `expires_at`,
`kid`, `jws`, `jws_sha256`. `GET /declarations/{id}` returns the same object.

**`POST /release`**: header `Authorization: Bearer <student's access token for this service>`.
```json
{"declaration_id": "226617abd0d39a21", "attributes": ["sub", "department"]}
```
`attributes` is optional; leaving it out means "everything my declaration covers that my
profile allows". → `200`:
```json
{"service": "lms", "profile": "partial", "declaration_id": "226617abd0d39a21",
 "released": {"sub": "97d4…", "department": "Computer Science"},
 "receipt": "<JWS signed by TrustTrail, typ release-receipt+jwt>"}
```
The receipt payload contains `iss`, `iat`, `jti`, `service`, `profile`, `attributes` (names only,
never values), `subject` (only if the pseudonym was released), `purpose`, `retention_until`,
`declaration_id`, `declaration_sha256` and `released_at`. Verify it with
**`GET /.well-known/jwks.json`**.

**Refusals** are always `{"error": "<code>", "detail": "..."}`:

| Code | Status | When |
|---|---|---|
| `invalid_token` / `missing_token` | 401 | bad or missing bearer token |
| `invalid_jwks`, `kid_conflict` | 400, 409 | key registration problems |
| `malformed`, `unsupported_alg` | 400 | not a valid declaration JWS |
| `unknown_key` | 400 | `kid` not registered for that `client_id` |
| `bad_signature` | 400 | signature doesn't match the registered key |
| `expired`, `not_yet_valid`, `lifetime_too_long` | 400 | `exp`/`iat` out of bounds at submission |
| `wrong_audience` | 400 | `aud` isn't `trusttrail` |
| `unknown_attribute` | 400 | attribute not in the vocabulary |
| `retention_in_past` | 400 | `retention_until` already over |
| `replayed_nonce` | 409 | nonce reused by the same service |
| `no_declaration` | 403 | release without a declaration, or with another service's |
| `declaration_expired` | 403 | the declaration's `exp` has passed |
| `retention_passed` | 403 | release after the promised deletion date *(becomes violation rule 2 in Phase 4)* |
| `attribute_not_declared` | 403 | asks for an attribute the purpose doesn't cover *(rule 1)* |
| `attribute_above_profile` | 403 | asks for more than the Keycloak-granted profile allows *(rule 3)* |

### Demo and tests

```bash
docker compose exec trusttrail python -m scripts.demo_phase2   # full request/response formats + refusal table
```
In the browser, each test service's front page shows its declared purpose; after login it
shows the release and the receipt payload.

Tests: `tests/test_declarations.py` (unit, fixed clock) covers a valid signature, a bad
signature (wrong key and tampered payload), expired, not yet valid, too long, wrong audience,
unknown attribute, retention over, missing claim, wrong `typ`, another client's key, and
`alg: none`. `tests/test_phase2_integration.py` covers the same cases end to end, plus
releases refused for a missing, expired, foreign or too-narrow declaration, nonce replay, key
registration with the wrong token, private key material, and receipt verification.

## Phase 3: hash-chained ledger and student dashboard

Every successful `/release` now writes one ledger entry and a TrustTrail-signed receipt, in
the same transaction. Refused requests write nothing (Phase 4 records them as violations).

**Entry format** (table `ledger` in `/data/trusttrail.db`):

| Field | |
|---|---|
| `entry_id` | 1, 2, 3, ... assigned by TrustTrail, so gaps are visible |
| `kind` | `release` (Phase 4 adds `violation`) |
| `time` | ISO 8601 UTC, microseconds |
| `service_id` | client ID of the service |
| `student_pseudonym` | the per-service pairwise ID, **never** the Keycloak user ID |
| `profile` | profile Keycloak granted |
| `attributes_released` | sorted list of names, never values |
| `purpose`, `retention_until`, `declaration_id` | copied from the signed declaration |
| `service_signature` | signature part of the service's declaration JWS (full JWS kept in `declarations`) |
| `prev_hash` | `entry_hash` of the previous entry; 64 zeros for entry 1 |
| `entry_hash` | SHA-256 (hex) of the canonical JSON of all fields above |

Canonical JSON = all fields except `entry_hash`, keys sorted, no whitespace, UTF-8
(`app/ledger.py:canonical`). Verification (`ledger.verify`) recomputes the chain from the
genesis hash and stops at the first entry whose number, `prev_hash` or content doesn't match.
SQLite triggers reject `UPDATE` and `DELETE` on the ledger. That only stops edits through
normal SQL use, so the hash chain is what makes tampering *evident*. The student ↔ pseudonym
mapping stays in a separate file (`identity_map.db`), read only by the dashboard for the
logged-in student.

Receipts now also carry `entry_id` and `entry_hash`, so a receipt a student downloaded earlier
can be checked against the ledger later.

**Endpoints**
- `GET /ledger/verify`: public; returns only `{ok, entries_checked, head_hash, first_bad_entry, reason}`.
- `GET /dashboard`: student page (log in with Keycloak through the `dashboard` client).
- `GET /dashboard/api/releases`: the logged-in student's releases, newest first.
- `GET /dashboard/api/verify/{entry_id}`: four checks. The entry matches its hash; the chain is
  intact up to it; the receipt is signed by TrustTrail; the receipt matches the entry.
- `GET /dashboard/receipts/{entry_id}` and `GET /dashboard/receipts`: download a receipt bundle
  (receipt JWS + decoded payload, TrustTrail's public key, the ledger entry, and the service's
  signed declaration), so the student can check it without trusting TrustTrail's server.

Students only see entries whose (service, pseudonym) pair is theirs; any other entry returns 404.

### Demo

```bash
# Browser: log in to http://library.localhost:8001 and http://lms.localhost:8002, then open
# http://localhost:8000/dashboard (same user). Each row has Receipt and Verify buttons.
scripts/check_dashboard.sh                                      # same flow scripted, with PASS/FAIL checks

docker compose exec trusttrail python -m scripts.demo_tamper    # 5 attacks on a COPY of the ledger, result table
docker compose exec trusttrail python -m scripts.demo_tamper --live --entry 3   # break the real ledger...
curl localhost:8000/ledger/verify                               # ...see it fail (or press Verify on the dashboard)
docker compose exec trusttrail python -m scripts.demo_tamper --restore          # ...and put it back
```

Tamper demo output (attacking entry #11 of 22):

| Attack | Chain check | Student receipts | Earlier head hash |
|---|---|---|---|
| A. change entry's attributes, leave its hash | detected at #11 | 1 fails | n/a (chain broken) |
| B. change entry's purpose, recompute its hash | detected at #12 | 1 fails | n/a |
| C. delete the entry | detected at #12 | 1 fails | n/a |
| D. change entry, recompute every hash after it | **not detected** | 12 fail | detected |
| E. delete the newest entry | **not detected** | 1 fails | detected |

D and E are why Phase 5 anchors the head hash outside the database.

### Tests

`tests/test_ledger.py` (unit, in-memory database) covers linking, canonical hashing, the
append-only triggers, and detection of an edited, edited-and-rehashed, deleted or renumbered
entry. It also has two tests that *document the limits*: a full rewrite and a cut-off tail
both pass the chain check. `tests/test_phase3_integration.py` checks that a release writes
exactly one matching entry, the receipt points at it, a refusal writes nothing, the public
check matches the ledger, 10 concurrent releases keep the chain intact, and the dashboard API
needs login.

## Known limits (Phase 1)

- **Why `sid` is stripped, and what that costs.** Keycloak 26 adds the SSO session ID (`sid`)
  to every token with no built-in way to turn it off, and every service in one SSO session
  gets the same value, which would let colluding services link their pseudonyms. The custom
  mapper removes it, and the client settings also hide `session_state` and `auth_time`.
  The cost: service tokens no longer point to a Keycloak session, so refresh tokens (switched
  off), the userinfo endpoint and `id_token_hint` logout don't work for the test services.
  TrustTrail checks tokens locally, so it isn't affected.
  Keycloak 26.8 marks the "exclude session state" switch as deprecated; if a later version
  removes it, `session_state` would come back in the login redirect, and
  `scripts/check_browser_sso.sh` would catch that.
- **Timing can still link.** Two services that compare login times (`iat`) could still guess
  which pseudonyms belong to the same student. Pairwise IDs and the stripped session ID
  remove *identifiers*, not traffic analysis.
- **Anonymous profile.** TrustTrail returns no `sub` for `anonymous`, but the service's
  Keycloak ID token still contains its pairwise `sub`, so the service can still recognise
  a returning student.
- **We only see requests made to our system.** TrustTrail controls attribute values because
  Keycloak tokens contain none. It cannot control what a service does with data afterwards.
- Access tokens are checked locally (signature, issuer, expiry). Revocation before expiry is not checked.

## Known limits (Phase 2)

- **A declaration is a promise, not a guarantee.** TrustTrail can prove what a service
  promised and what it was given. It cannot see what the service does with the data
  afterwards, and it cannot prove deletion by `retention_until`.
- **Non-repudiation rests on key custody.** A signed declaration binds the service only as
  long as its private key is not shared or stolen. Registering a key requires the service's
  Keycloak client secret, so the client secret is the root of trust for key registration.
- **Purpose text is not checked for meaning.** TrustTrail checks attribute names against the
  declaration; it cannot judge whether the stated purpose is honest or proportionate.

## Known limits (Phase 3)

- **We only see requests made to our system.** The ledger records every release TrustTrail
  makes. It cannot record what a service does with the data afterwards.
- **The chain alone can't catch a full rewrite or a cut-off tail.** Someone with write access
  to the database file can drop the triggers, edit an entry and recompute every hash after it,
  or delete the newest entries; the chain still verifies. Students' receipts catch this for
  their own entries; Phase 5 anchoring catches it for everyone, but only from the moment of
  each anchor.
- **Tamper-evident, not tamper-proof.** The triggers only stop edits through normal SQL use.
  Verification shows that something changed; it cannot restore what was there.
- **The dashboard's Verify uses the receipt stored by TrustTrail.** An attacker who also
  rewrote the receipts table would pass that check. Receipts the student downloaded earlier
  are independent evidence (check them against the ledger entry, as the receipt file explains).
