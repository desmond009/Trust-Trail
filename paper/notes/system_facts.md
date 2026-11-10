# TrustTrail: technical fact sheet (source of truth for the paper)

Scope: derived from the repo at `/Users/vijender/Trust Trail` (branch `main`, HEAD `5de1f34`). Paths are relative to the repo root. `file:line` refs refer to the working tree as read. Where a number comes only from the README (not reproducible from code or a results file), that is flagged "README only". Nothing here was executed against the live stack; unit-test counts were obtained with `pytest --collect-only`, integration-test counts by static reading.

Important data-provenance caveats (read first):
- `trusttrail/eval/results/{latency,tamper,violations}.md`, their `_raw.csv`, and `taxonomy_chart.svg` are **modified in the working tree (uncommitted)** and were regenerated on 2026-11-10; the committed (HEAD) versions are from 2026-10-30. The latency numbers in README.md (17.1 / 21.2 / +4.0 ms) match the HEAD (committed) results, not the working tree (16.0 / 19.6 / +3.6 ms). Both are given in section 7. Decide which one the paper cites and state the date.
- README is 739 lines (not ~750).
- `eval/results/study.md` does not exist (the usability study has not been run).
- The paper PDF in repo root is `1-s2.0-S1389128617301664-main.pdf` (Werner, Westphall & Westphall 2017, Computer Networks 122:29-42); untracked. `paper/notes/werner2017_notes.md` already exists (not read for this sheet).
- All students, services and secrets are invented demo data (README:7; `config/students.yaml:1`).

---------------------------------------------------------------------------------------------------

## 1. Overview, motivation, phases

### 1.1 What it is (README:1-7)
"Privacy-aware federated login with accountable, purpose-bound disclosure." Student project, IIIT Dharwad. Follow-up to Werner, Westphall & Westphall (2017), "Cloud Identity Management: A Survey on Privacy Strategies". All commits authored by `desmond009`.

Core idea (README:52-54, 300): Keycloak (OIDC identity provider) decides **which profile** (disclosure level) a service may get and issues tokens with a per-service pairwise `sub` and **no personal claims**. TrustTrail (a FastAPI service) decides **what that profile contains** and is "the only path for attribute values". The loop (README:300): **signed promise -> ledger record -> violation detected -> trust lowered -> less data released.** Records stay off-chain; only Merkle roots are anchored on an Ethereum-compatible chain.

Trust tiers are taken from Werner et al. 2017 (`config/trust.yaml:1`): fully_trusted, semi_trusted, untrusted (plus a bottom tier `blocked` for repeated violations).

### 1.2 Phase history (git log; commit times +0530)
| Phase | Commit / time | Subject | What it added |
|---|---|---|---|
| 1 | `eeff728`, 2026-10-29 23:23 | "feat: Implement TrustTrail session ID stripping mapper for Keycloak" (33 files, +1236) | Keycloak 26.8.1 realm via seed; 4 profiles (anonymous/pseudonym/partial/total) as client scopes; pairwise sub mapper + custom `trusttrail-strip-sid-mapper` (Java); `/release` (token -> profile attributes); student<->pseudonym map (`identity_map.db`); 3 test services (library, lms, exam); `check_browser_sso.sh`. |
| 2 | `2ba951e`, 2026-10-30 13:03 | "Implement signed purpose declarations and attribute release mechanism" (26 files, +1148) | JWS purpose declarations (ES256/RS256), service key registration, TrustTrail-signed receipts (ES256), refusal codes, `config/declarations.yaml`, `declarations`/`service_keys` tables. |
| 3 | `b8aada5`, 2026-10-30 13:21 | "feat: Implement hash-chained ledger for data releases" (16 files, +978) | Hash-chained append-only SQLite `ledger`, `receipts` table, student dashboard (`/dashboard`), receipt bundles, `/ledger/verify`, `demo_tamper.py`, `check_dashboard.sh`. |
| 4 | `f742cde`, 2026-10-30 13:40 | "Implement bad services for TrustTrail demo and enhance integration tests" (30 files, +1173/-95) | 3 violation rules, `violation`/`trust_reset` ledger kinds, trust score + tier caps enforced in Keycloak via Admin API, Keycloak LOGIN_ERROR event polling, 3 scripted bad services, `trust.py`, expanded `config/trust.yaml`. |
| 5 | `6d898e1`, 2026-10-30 15:04 | "feat: Implement Phase 5 anchoring for ledger entries" (31 files, +4394, mostly lockfile) | `TrustTrailAnchor.sol`, Hardhat 3 chain + deploy, `merkle.py`, `anchoring.py`, `/anchors*`, `/ledger/proof`, `verify_receipt.py`, `verify_anchors.py`, `demo_phase5.py`. |
| 6 | `5de1f34`, 2026-10-30 15:45 | "Add evaluation scripts and usability study materials" (35 files, +5784/-33) | `trusttrail/eval/` (latency, tamper, violation, taxonomy, usability analysis), `/study` prototype consent screens (`app/study.py`), `config/study.yaml`, `bench-baseline`/`study-*` Keycloak clients, usability materials. |

Whole history spans about 16.5 hours (2026-10-29 23:23 to 2026-10-30 15:45). Phase structure is also the README's section structure ("Phase 1 ... Phase 6").

---------------------------------------------------------------------------------------------------

## 2. Architecture

### 2.1 Containers (`docker-compose.yml`; project name `trusttrail`, l.1)
| Service | Build/image | Role | Ports | Volumes | depends_on |
|---|---|---|---|---|---|
| `keycloak` (l.12-31) | `./keycloak` -> `quay.io/keycloak/keycloak:26.8.1` + `strip-sid-mapper-1.0.0.jar` in `/opt/keycloak/providers/` (`keycloak/Dockerfile:10-11`); command `start-dev` | OIDC identity provider; realm `trusttrail`; issues tokens with pairwise `sub` | 8080:8080 (health on management port 9000, internal) | `kc-data:/opt/keycloak/data` | none |
| `chain` (l.35-42) | `./chain`, `node:22-slim` (`chain/Dockerfile:1`), CMD `npx hardhat node --hostname 0.0.0.0` | Local in-memory Hardhat 3 Ethereum node | 8545:8545 | none (restart = fresh chain) | none |
| `chain-deploy` (l.44-51) | `./chain`; `npx hardhat run scripts/deploy.ts --network chainNode`; `restart: "no"` | One-shot deploy of `TrustTrailAnchor`; writes `chain/deployments/localhost.json` | none | `./chain/deployments:/app/deployments` | chain healthy |
| `trusttrail` (l.53-69) | `./trusttrail`, `python:3.12-slim`, `uvicorn app.main:app --host 0.0.0.0 --port 8000` | Disclosure layer: API, ledger, trust, anchoring, dashboard, study | 8000:8000 | `./trusttrail:/app` (code mounted), `./config:/config:ro`, `tt-data:/data`, `./chain/deployments:/deployments:ro` | keycloak healthy, chain-deploy completed |
| `library` (l.71), `lms` (l.76), `exam` (l.81) | `./services` (`python:3.12-slim`; `uvicorn app:app --port $PORT`) | Three invented honest campus services (same code, `SERVICE_ID` env) | 8001, 8002, 8003 | `./services:/app`, `./config:/config:ro`, `svc-keys:/keys` | keycloak healthy, trusttrail started |

Named volumes (l.86-89): `kc-data` (Keycloak dev DB), `tt-data` (`/data`: `trusttrail.db`, `identity_map.db`, `receipt_signing_key.pem`, `study.db`, `tamper_backup.json` during live-tamper demo), `svc-keys` (`/keys/<service>.pem`, service declaration-signing keys).

Keycloak host config (l.18-23): `KC_HOSTNAME=http://localhost:8080` (fixed frontend URL so the token issuer is identical for browser and containers), `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`, `KC_HEALTH_ENABLED=true`, bootstrap admin from `KC_ADMIN_USER`/`KC_ADMIN_PASSWORD`. Healthcheck is hand-rolled over `/dev/tcp` to `:9000/health/ready` (image has no curl), interval 5 s, 40 retries.

TrustTrail environment (l.55-63): `env_file: .env`, `KC_INTERNAL_URL=http://keycloak:8080`, `KC_PUBLIC_URL=http://localhost:8080`, `CHAIN_RPC_URL` (default `http://chain:8545`), `ANCHOR_DEPLOYMENT=/deployments/${ANCHOR_NETWORK:-localhost}.json`, `ANCHOR_PRIVATE_KEY`, `ANCHOR_INTERVAL_SECONDS` (empty default).

Not in compose: the three scripted bad services (no web app; run via `scripts/bad_services.py` inside the trusttrail container). Their Keycloak clients are nonetheless created by the seed.

Host names: `*.localhost` (library.localhost:8001, lms.localhost:8002, exam.localhost:8003; scripted: overasker.localhost:8011, retainer.localhost:8012, tiercap.localhost:8013 in `services.yaml`). Each service has its own host because Keycloak's pairwise mapper derives the "sector" from the redirect-URI host (`config/services.yaml:1-3`; `app/pseudonyms.py:29-35`).

### 2.2 Technology and versions
- Keycloak 26.8.1 (`keycloak/Dockerfile:10`; pom `keycloak.version` 26.8.1); mapper built with `maven:3.9-eclipse-temurin-21`, `maven.compiler.release` 21; jar `strip-sid-mapper-1.0.0`. Keycloak logs a startup warning that the protocol-mapper SPI is internal (README:73-74).
- Python 3.12-slim in containers (`trusttrail/Dockerfile:1`, `services/Dockerfile:1`). Host `.venv` is Python 3.13 (used for `scripts/check_study.py` and test collection only).
- `trusttrail/requirements.txt`: fastapi==0.162.0, uvicorn==0.54.0, httpx==0.28.1, pyjwt[crypto]==2.15.1, pyyaml==6.0.3, pytest==9.2.0, authlib==1.9.1, itsdangerous==2.2.0, web3==7.16.0, matplotlib==3.11.2, python-multipart==0.0.32.
- `services/requirements.txt`: fastapi==0.162.0, uvicorn==0.54.0, httpx==0.28.1, authlib==1.9.1, itsdangerous==2.2.0, pyyaml==6.0.3, pyjwt[crypto]==2.15.1.
- Chain (`chain/package.json`): Node 22 (`node:22-slim`), `hardhat` 3.20.0 (pinned; README:723 says 3.21.x exists), `@nomicfoundation/hardhat-toolbox-mocha-ethers` 4.0.0, `ethers` 6.16.0, `mocha` 12.0.3, `chai` 6.2.2, `typescript` 5.9.3, `@types/node` 22.19.1; `"type": "module"`. Solidity **0.8.28**, optimizer enabled, runs 200 (`chain/hardhat.config.ts:6-9`); contract pragma `^0.8.28`, SPDX MIT.
- Hardhat networks (`hardhat.config.ts:10-25`): `chainNode` (http, chainType l1, URL `CHAIN_RPC_URL` or `http://127.0.0.1:8545`) and `sepolia` (URL and key from `configVariable("SEPOLIA_RPC_URL")` / `SEPOLIA_PRIVATE_KEY`).
- SQLite (stdlib `sqlite3`) for all state; Authlib (Starlette client) for OIDC in dashboard/study/services; Starlette `SessionMiddleware` (itsdangerous-signed cookies).
- web3.py 7.16.0 for anchoring (README:724: web3 8.0 exists, stayed on 7.x).

### 2.3 TrustTrail modules (`trusttrail/app/`: 20 .py modules + `__init__.py` + 1 static HTML)
| Module | Lines | Responsibility |
|---|---|---|
| `main.py` | 258 | FastAPI app, core endpoints, `Refusal` handler, lifespan starts background threads (`trust.start()`, `anchorer.start()`), `SessionMiddleware(session_cookie="tt_dashboard", same_site="lax")` (l.34-38) |
| `settings.py` | 51 | env + YAML config loader (`lru_cache`), `ISSUER = {KC_PUBLIC_URL}/realms/{REALM}`, `OIDC_BASE` (internal URL), attribute vocabulary |
| `tokens.py` | 51 | Keycloak access-token verification (RS256, JWKS via `PyJWKClient`, issuer check, no audience check, `azp` identifies the service) |
| `keycloak.py` | 73 | `KeycloakAdmin`: client-credentials token (refreshed 30 s before expiry; retry once on 401), Admin REST wrappers |
| `pseudonyms.py` | 78 | pairwise-sub port + `PseudonymMap` (identity_map.db) |
| `release.py` | 65 | `granted_profile`, `lower_profile`, `choose_attributes` (rules 1/3), `build_release` |
| `declarations.py` | 170 | JWS declaration verification/storage |
| `service_keys.py` | 39 | append-only public-key registry |
| `jose_util.py` | 24 | RFC 7638 thumbprint, public JWK, sha256 |
| `receipts.py` | 51 | ES256 release receipts, key in `/data/receipt_signing_key.pem` |
| `ledger.py` | 131 | canonical JSON, hash chain, verify, queries |
| `db.py` | 128 | schema + `tx()` (global `threading.Lock`, one shared connection) |
| `trust.py` | 168 | score, tier, enforcement, event polling, reset |
| `merkle.py` | 56 | RFC 6962-style Merkle tree |
| `anchoring.py` | 179 | `Anchorer`: contract access, `run_once`, proofs, verification |
| `dashboard.py` | 152 | student dashboard router |
| `study.py` | 375 | usability-study router (Phase 6) |
| `errors.py` | 19 | `Refusal` exception + 3 rule constants |
| `demo_login.py` / `demo_service.py` | 30 / 61 | TEST/DEMO ONLY helpers (password grant; act as a service) |
| `static/dashboard.html` | 139 | dashboard single page (vanilla JS) |

### 2.4 Trust boundaries and what each party holds
- **Student/browser**: Keycloak SSO session cookie at Keycloak; `tt_dashboard` session cookie at TrustTrail (stores `{user_id (real Keycloak sub), name}`; `dashboard.py:62-63`).
- **Keycloak (realm `trusttrail`)**: real user records including extra attributes (`affiliation, roll_no, department, program, year`, `firstName/lastName/email`), client definitions, per-client pairwise salts (random: mapper configured with empty salt; `seed.py:147-151`), LOGIN_ERROR events only, kept 86400 s (`seed.py:56-57`). Tokens issued to services carry only the pairwise `sub`, `scope` (including `profile-*`), no personal claims, no `sid`.
- **TrustTrail**: (a) `trusttrail.db`: tables `service_keys`, `declarations`, `ledger`, `receipts`, `trust_state`, `anchors`, `processed_events` (`db.py:11-93`); (b) `identity_map.db`: table `pseudonyms(client_id, pseudonym, user_id, PRIMARY KEY (client_id, pseudonym))` (`pseudonyms.py:44-46`), the only student<->pseudonym mapping, kept separate from the ledger "so the ledger can be inspected without exposing who is who" (`pseudonyms.py:8-9`); (c) the receipt-signing EC P-256 private key (`/data/receipt_signing_key.pem`, mode 0600; `receipts.py:19-35`); (d) `study.db` (usability data). TrustTrail reads attribute values from Keycloak via its service account at release time; the ledger stores attribute **names** only, never values.
- **Services**: own Keycloak client secret, own declaration-signing EC P-256 key (`/keys/<id>.pem` in `svc-keys`; `services/app.py:33,47-54`), the received attributes (outside TrustTrail's control), the receipt.
- **Chain**: only `{root bytes32, firstEntryId, lastEntryId, anchoredAt}` per batch. Owner key (`ANCHOR_PRIVATE_KEY`) is held by TrustTrail; on the local chain it is Hardhat's public test account #0 (`.env.example` comment).
- TrustTrail's Keycloak service account (client `trusttrail`; `serviceAccountsEnabled`; standard flow and direct grants disabled; `seed.py:91-105`) has realm-management roles `view-users`, `view-clients`, `view-events`, `manage-clients`.
- Secrets live in `.env` (gitignored; template `.env.example`). Variable names: `KC_ADMIN_USER`, `KC_ADMIN_PASSWORD`, `TRUSTTRAIL_CLIENT_SECRET`, `LIBRARY_CLIENT_SECRET`, `LMS_CLIENT_SECRET`, `EXAM_CLIENT_SECRET`, `DASHBOARD_CLIENT_SECRET`, `OVERASKER_CLIENT_SECRET`, `RETAINER_CLIENT_SECRET`, `TIERCAP_CLIENT_SECRET`, `BENCH_BASELINE_CLIENT_SECRET`, `STUDY_CLIENT_SECRET`, `TRUSTTRAIL_ADMIN_TOKEN`, `SESSION_SECRET`, `STUDENT_DEMO_PASSWORD`, `ANCHOR_PRIVATE_KEY`; commented optional: `ANCHOR_INTERVAL_SECONDS`, `ANCHOR_NETWORK`, `CHAIN_RPC_URL`. Others read by code: `TT_PUBLIC_URL` (default `http://localhost:8000`), `KC_REALM` (default `trusttrail`), `CONFIG_DIR` (default `/config`), `DATA_DIR` (default `/data`), `TRUSTTRAIL_URL`.

### 2.5 Keycloak realm created by `scripts/seed.py` (destructive: deletes an existing realm `trusttrail` first; `seed.py:46-60`)
- Realm `trusttrail`, display name "TrustTrail Demo University (fake data)", registration disabled.
- Events: enabled, `enabledEventTypes: ["LOGIN_ERROR"]`, `eventsExpiration: 86400` (`seed.py:56-57`).
- User profile `unmanagedAttributePolicy = ADMIN_EDIT` (custom attributes survive; `seed.py:58-60`).
- Client scopes `profile-anonymous|pseudonym|partial|total`: openid-connect, **no claim mappers**, attributes `include.in.token.scope=true`, `display.on.consent.screen=true`, consent text "Share your <profile> profile" (`seed.py:63-75`). Keycloak only records which profile was granted (in token `scope`).
- Built-in `basic` scope: `auth_time` mapper deleted (`seed.py:82-88`).
- Client `trusttrail` (confidential, service account).
- Service clients (all six in `services.yaml`; `seed.py:108-157`): confidential, `rootUrl` = service url, redirect `{url}/callback`, `standardFlowEnabled`, `fullScopeAllowed=false`, `serviceAccountsEnabled` (no roles; lets the service authenticate to TrustTrail to register its key), `directAccessGrantsEnabled=true` (TEST ONLY), attributes `policyUri`, `tosUri`, `post.logout.redirect.uris`, `exclude.session.state.from.auth.response=true`, `use.refresh.tokens=false`. All default and optional client scopes removed except `basic` (default) and `service_account`. Optional scopes: `profile-*` up to the tier cap. Protocol mappers: `oidc-sha256-pairwise-sub-mapper` ("pairwise subject identifier"; `sectorIdentifierUri=""`, `pairwiseSubAlgorithmSalt=""` so Keycloak generates a random salt) and `trusttrail-strip-sid-mapper` ("strip session id").
- Client `dashboard`: confidential, standard flow, redirect `{TT_PUBLIC_URL}/dashboard/callback`, **no pairwise mapper** (TrustTrail needs the real user ID), direct grants off (`seed.py:160-169`).
- Evaluation clients (`seed.py:172-201`): `bench-baseline` (plain OIDC, keeps default scopes, `oidc-usermodel-attribute-mapper` for `affiliation, department, program, year, roll_no` into id/access/userinfo tokens, direct grants on, redirect `http://bench.localhost:8020/callback`); `study-lms` and `study-exam` (same mappers, `consentRequired=true`, direct grants off, redirect `{TT_PUBLIC_URL}/study/baseline/callback`; both use `STUDY_CLIENT_SECRET`).
- 5 users from `config/students.yaml`; attributes `affiliation=["student"]`, `roll_no`, `department`, `program`, `year`; password from `STUDENT_DEMO_PASSWORD` (non-temporary); `emailVerified=true`.

### 2.6 Custom Keycloak SPI `trusttrail-strip-sid-mapper`
`keycloak/strip-sid-mapper/src/main/java/edu/trusttrail/keycloak/StripSessionIdMapper.java` (72 lines). Extends `AbstractOIDCProtocolMapper`, implements `OIDCAccessTokenMapper`, `OIDCIDTokenMapper`. `PROVIDER_ID = "trusttrail-strip-sid-mapper"`; display type "TrustTrail: strip session ID (sid)"; no config properties; `transformAccessToken` and `transformIDToken` call `token.setSessionId(null)` (l.59-71). Registered via `META-INF/services/org.keycloak.protocol.ProtocolMapper` (`edu.trusttrail.keycloak.StripSessionIdMapper`). Rationale (class comment l.17-25; README:644-653): Keycloak 26 adds `sid` unconditionally and every client in one SSO session gets the same value, which would let colluding services link pairwise pseudonyms. `session_state` hidden via client attribute `exclude.session.state.from.auth.response=true` (deprecated in 26.8; `check_browser_sso.sh` would catch removal); `auth_time` removed from `basic`. Side effects: refresh tokens (switched off), userinfo endpoint and `id_token_hint` logout do not work for those clients; TrustTrail validates tokens locally so is unaffected. README:97 describes an experiment: delete "strip session id" from library/LMS clients and the `sid` check in `check_browser_sso.sh` fails.

### 2.7 Component-diagram edges
- Browser <-> Keycloak (login UI, SSO session); Browser -> Service (`/login`, `/callback`); Service <-> Keycloak (authorization-code flow, client secret).
- Service -> Keycloak token endpoint (client_credentials) -> Service -> TrustTrail `POST /services/keys` (Bearer service token).
- Service -> TrustTrail `POST /declarations` (no bearer; JWS signature).
- Service -> TrustTrail `POST /release` (Bearer student's access token; body `declaration_id`, optional `attributes`).
- TrustTrail -> Keycloak: JWKS (`/realms/trusttrail/protocol/openid-connect/certs`), Admin REST (users, clients, client-scopes, optional-client-scopes, protocol-mappers, events), token endpoint (client_credentials as `trusttrail`).
- TrustTrail -> SQLite files in `tt-data` (`trusttrail.db`, `identity_map.db`, `study.db`).
- TrustTrail (anchoring thread) -> Chain JSON-RPC `http://chain:8545`: `anchor`, `getBatch`, `batchCount`, `lastAnchoredEntryId`. `chain-deploy` -> Chain; writes deployment JSON that TrustTrail reads read-only from `/deployments`.
- Browser -> TrustTrail `/dashboard` (OIDC via client `dashboard`) and `/study` (OIDC via `study-lms`/`study-exam` for baseline screens).
- Verifier (`scripts/verify_receipt.py`) -> Chain RPC only (no TrustTrail API).

---------------------------------------------------------------------------------------------------

## 3. End-to-end flows (sequences)

Notation: `A -> B: message`.

### 3.1 Realm seeding (`python -m scripts.seed`)
1. seed -> Keycloak master realm: password grant, client `admin-cli`, with `KC_ADMIN_USER/PASSWORD` -> admin token (`seed.py:20-26`).
2. seed -> Keycloak Admin API: delete realm `trusttrail` if it exists; create realm; set events config and user-profile policy; create 4 profile scopes; trim `basic`; create clients `trusttrail`, six service clients, `dashboard`, three evaluation clients; create 5 students (`seed.py:216-227`).
Seeding resets Keycloak only; TrustTrail's own DBs persist in `tt-data`. Re-seed is tolerated by the pseudonym-map refresh-on-miss and JWKS client rebuild (`tokens.py:13-21`, `pseudonyms.py:67-73`).

### 3.2 Service key registration (Phase 2)
1. Service -> Keycloak `POST /realms/trusttrail/protocol/openid-connect/token` (`grant_type=client_credentials`, `client_id`, `client_secret`) -> access token containing a `client_id` claim (from the retained `service_account` scope; `services/app.py:68-70`).
2. Service -> TrustTrail `POST /services/keys`, `Authorization: Bearer <token>`, body `{"keys":[<public JWK>]}`; JWK is EC P-256 `{kty,crv,x,y,kid=RFC 7638 thumbprint,alg:"ES256",use:"sig"}`.
3. TrustTrail verifies token (`verify_service_token`: RS256 signature via Keycloak JWKS, issuer match, `typ=="Bearer"`, `azp` and `sub` present, `client_id == azp`) (`tokens.py:24-51`).
4. `service_keys.register(azp, keys)`: empty -> 400 `invalid_jwks`; private members `{d,p,q,dp,dq,qi,oth,k}` present -> 400 `invalid_jwks`; `kty` must be EC or RSA and `kid` present; new kid inserted; same kid with different key or different owner -> 409 `kid_conflict`; re-registering the identical key is OK (`service_keys.py:14-32`). Keys are append-only.
5. TrustTrail -> Service: `200 {"client_id": azp, "kids": [...]}`.

### 3.3 Declaration submission (Phase 2)
1. Service builds claims `{client_id, aud:"trusttrail", attributes, purpose, retention_until (today + retention_days, ISO date), nonce (uuid4), iat: now, exp: now + valid_days*86400}` and signs ES256 with header `{alg, kid, typ:"purpose-declaration+jwt"}` (`services/app.py:74-80`).
2. Service -> TrustTrail `POST /declarations`, body `{"declaration":"<compact JWS>"}` (no bearer).
3. `declarations.verify` order (`declarations.py:63-136`): (a) parse header and unverified payload, else 400 `malformed`; (b) header `typ` must be `purpose-declaration+jwt`, else `malformed`; (c) `alg` in `[ES256, RS256]`, else `unsupported_alg`; (d) look up registered key by (`client_id` from unverified payload, `kid`), else `unknown_key`; (e) verify signature, required claims and `aud=="trusttrail"` (`jwt.decode`, `require=[client_id, aud, attributes, purpose, retention_until, nonce, iat, exp]`; library exp/iat/nbf checks disabled): `bad_signature`, `wrong_audience`, other -> `malformed`; (f) `iat` and `exp` must be ints, else `malformed`; (g) `exp < now - skew` -> `expired`; `iat > now + skew` -> `not_yet_valid`; `exp - iat > 90 days` -> `lifetime_too_long`; (h) `attributes` non-empty list of strings, else `malformed`; names outside the vocabulary -> `unknown_attribute`; (i) `purpose` non-blank string of at most 500 chars, else `malformed`; (j) `retention_until` parseable (date `YYYY-MM-DD` or timestamp with timezone), else `malformed`; deadline `< now` -> `retention_in_past`.
4. `declarations.store`: INSERT; `UNIQUE(client_id, nonce)` violation -> 409 `replayed_nonce` (`declarations.py:151-160`).
5. TrustTrail -> Service: `201` with the declaration object (4.3). `declaration_id = sha256(jws)[:16]`. Attributes stored de-duplicated and sorted; purpose stripped.
Services re-sign a fresh declaration when none exists or it expires within 3600 s (`services/app.py:60-64`).

### 3.4 Student login via Keycloak (Phase 1)
1. Student -> Service `GET /login`. Service (Authlib) redirects the browser to Keycloak with scope `openid profile-<wants>` (`wants` from `services.yaml`; `services/app.py:39-42`).
2. Keycloak authenticates the student (SSO if already logged in). The requested `profile-*` scope is granted **only if assigned as an optional client scope** to that client (the tier cap). Over-cap request -> `invalid_scope` and a `LOGIN_ERROR` event whose reason reads "Invalid scopes: ... profile-total" (README:45-47, 312-314).
3. Keycloak -> Service `callback?code=...` (no `session_state`, because of `exclude.session.state.from.auth.response`).
4. Service exchanges the code for tokens. `sub` = pairwise ID for that client (SHA-256 pairwise mapper, random per-client salt, sector = redirect host); `scope` includes `profile-<x>`; no `sid`; no `auth_time`; no personal claims; refresh tokens off.
5. Service -> TrustTrail `POST /release` (3.5).

### 3.5 `POST /release` (`main.py:112-171`)
Request: `Authorization: Bearer <student's access token for this service>`; body `{declaration_id?, attributes?}`. Check order:
1. Bearer present, else 401 `missing_token`.
2. `verify_access_token` else 401 `invalid_token`; `service = claims["azp"]`.
3. Declaration lookup; absent or `decl.client_id != service` -> 403 `no_declaration`.
4. `granted = granted_profile(scope)` (highest-ranked `profile-*` in token scope; none -> `anonymous`; `release.py:13-18`). `profile = lower_profile(granted, trust.current_cap(service))` (tokens issued before a demotion get today's cap).
5. `declarations.check_usable`: `now > expires_at` -> 403 `declaration_expired`; `now > retention_deadline(retention_until)` -> 403 `retention_passed` (**rule 2**, `after_retention`).
6. `choose_attributes(requested, declared, allowed=profile_attributes(profile), entitled=profile_attributes(entitled_cap(service)))` (`release.py:35-61`):
   - `requested is None`: release `sorted(declared ∩ allowed)` (cannot refuse).
   - explicit request: names not in declaration -> 403 `attribute_not_declared` (**rule 1**, `undeclared_attribute`); else names above the **base-tier** cap (`entitled`) -> 403 `attribute_above_tier_cap` (**rule 3**, `above_tier_cap`); else names above the currently allowed profile -> 403 `attribute_above_profile` (no violation); else release `sorted(set(requested))`.
7. If the refusal carries a rule: `trust.record_violation(...)` writes a `violation` ledger entry (`student_pseudonym=claims["sub"]`, `profile=granted`, `attributes_requested = refusal.requested or body.attributes or decl.attributes`, purpose/retention/declaration_id/service_signature from the declaration) and calls `enforce`; the refusal JSON gains `"violation": {"rule","entry_id"}` (`main.py:139-147`, 41-46).
8. `pmap.resolve(service, claims["sub"])` -> Keycloak user id (rebuild once on miss), else 403 `unknown_subject`.
9. `build_release`: `sub` -> pairwise ID; `name` = `firstName lastName` (stripped); `email`; other attributes = first value of the Keycloak user attribute.
10. One DB transaction (`db.tx()`): `ledger.append(kind="release", ...)`, `receipts.sign(...)`, `ledger.store_receipt`. "No release without a record." Response `200 {service, profile, declaration_id, entry_id, released, receipt}`.
Design note (`release.py:35-47`): `attribute_above_profile`, and a demoted service asking within its original agreement, are refused **without** a new violation so one violation cannot snowball into automatic blocking.

### 3.6 Ledger write and receipt (Phase 3)
`ledger.append` (`ledger.py:52-69`): read last (`entry_id`, `entry_hash`); `entry_id = last+1` (or 1); `prev_hash = last.entry_hash` or `GENESIS = "0"*64`; `time` = UTC ISO 8601, microseconds, trailing `Z`; list fields sorted; `entry_hash = SHA-256(canonical JSON)`; INSERT. SQLite triggers `ledger_no_update`/`ledger_no_delete` abort UPDATE/DELETE. Receipt: ES256 JWS signed by TrustTrail's key, stored in `receipts(entry_id, jws)`; not part of the hash chain (embeds the entry hash; evidence about the chain; `db.py:60-65`).

### 3.7 Dashboard view and verification (`dashboard.py`)
1. Browser -> `GET /dashboard`: static HTML (no auth). "Log in" -> `GET /dashboard/login`: Authlib redirect to Keycloak, client `dashboard`, scope `openid profile`, redirect `{TT_PUBLIC_URL}/dashboard/callback`.
2. Keycloak -> `GET /dashboard/callback`: TrustTrail exchanges code, stores `session["student"] = {user_id: userinfo.sub, name}`, redirects to `/dashboard`.
3. Page JS -> `GET /ledger/verify` (public chain status) and `GET /dashboard/api/releases`: `my_pseudonyms(user_id)` from `identity_map.db` (rebuilds mapping for any service missing); `ledger.entries_for` selects entries whose `(service_id, student_pseudonym)` match one of the student's pairs; newest first; includes `violation` entries (shown as red rows, README:366). Fields: `entry_id, kind, rule, time, service, service_id, profile, attributes (released), requested, purpose, delete_by`.
4. "Verify" -> `GET /dashboard/api/verify/{entry_id}` (404 `not_found` if not the student's). Checks: "entry content matches its hash"; "chain intact from the first entry up to this one" (`chain.ok or chain.first_bad_entry > entry_id`); for `kind=="release"`: "receipt signed by TrustTrail" and "receipt matches this ledger entry" (receipt `entry_id` and `entry_hash` equal the entry's recomputed hash); and, when the anchor status is `anchored` or `mismatch`, "matches the blockchain anchor (batch #n)". Response `{entry_id, ok, checks, whole_ledger, anchor}`.
5. "Receipt" -> `GET /dashboard/receipts/{entry_id}`; "Download all" -> `GET /dashboard/receipts`: JSON bundle with `about`, `receipt_jws`, `receipt_payload`, `trusttrail_jwks`, `ledger_entry`, `service_declaration_jws`, `anchor_proof` (attachment `trusttrail-receipt-<id>.json` / `trusttrail-receipts.json`).
6. `GET /dashboard/logout` clears the session. Without session: 401 `not_logged_in`.

### 3.8 Violation detection (Phase 4)
Rules 1 and 2 are detected synchronously in `/release` (3.5 steps 5-7). Rule 3 has two paths: (a) `/release` explicit request above the base-tier cap; (b) at login: the service asks Keycloak for an unassigned `profile-*` scope, Keycloak refuses (`invalid_scope`) and records a `LOGIN_ERROR` event with `details.reason` starting "Invalid scopes" and `clientId`. `Trust.poll_events` (`trust.py:85-113`), run by the background thread every `sync_seconds` (3) and by `POST /trust/sync`:
1. `GET /admin/realms/trusttrail/events?type=LOGIN_ERROR&max=200` (newest first), iterated oldest first.
2. Each event id not yet in `processed_events` is inserted there (so none counts twice).
3. Ignored unless `reason.startswith("Invalid scopes")` and `clientId` is a configured service.
4. `profile-*` words are parsed from the reason and kept if in the profile order; `requested = max(asked, key=order.index)`.
5. If `order.index(requested) > order.index(entitled_cap(service))` (above the **agreement**, i.e. base tier) -> `record_violation(service, above_tier_cap, {profile: requested, attributes_requested: sorted(profile_attributes(requested))})`. Requests above a *lowered* cap but within the agreement are refused by Keycloak but not counted.
Login-time violation entries: `student_pseudonym` is empty (no token was issued).

### 3.9 Trust score recomputation and tier demotion (`trust.py`)
`record_violation` -> ledger append -> `enforce(service)`:
1. `evaluate`: `since = now - violation_window_days (90)`; `violations_since` (kind `violation`, `entry_id >` latest `trust_reset` of the service, `time >= since`); `score(client, n)` from the Keycloak client representation (`policyUri` attribute, required metadata fields); `tier = tier_after(base_tier, demotions)`; `cap = tiers[tier]`; `violations_by_rule`.
2. Under `Trust._lock`: wanted scopes = `{profile-p for p in profiles_up_to(cap)}`; current = the client's optional scopes starting with `profile-`; missing ones added and surplus removed via `PUT`/`DELETE /clients/{id}/optional-client-scopes/{scopeId}` (needs `manage-clients`).
3. State JSON persisted in `trust_state` (`INSERT OR REPLACE`).
Daemon thread `trust-sync` loops `sync()` (= `poll_events()` + `enforce` for every configured service) every 3 s, logging exceptions and retrying, so a re-seeded Keycloak cannot silently undo a demotion (README:336-337). `/release` also applies the current cap to already-issued tokens (3.5 step 4). Reset: `POST /trust/{service}/reset` (admin) -> `trust_reset` ledger entry with `purpose=reason`, then `enforce`.

### 3.10 Anchoring cycle (Phase 5; `anchoring.py`)
Every `interval_seconds` (default 300; env `ANCHOR_INTERVAL_SECONDS` overrides) the `anchoring` daemon thread runs `run_once()` (exceptions logged, retried next interval); also `POST /anchors/run` (admin):
1. Under a lock: Web3 connects to `CHAIN_RPC_URL`; requires `chain_id == deployment.chainId`; contract from `deployment.address/abi`.
2. Requires `account(ANCHOR_PRIVATE_KEY).address == deployment.owner`, else `AnchorUnavailable`.
3. `done = contract.lastAnchoredEntryId()`; `SELECT entry_id, entry_hash FROM ledger WHERE entry_id > done ORDER BY entry_id LIMIT max_batch_entries (5000)`; none -> return `None`, **no transaction**.
4. `root = merkle.root([leaf_hash(entry_hash)...])`; build, sign and send `anchor(root, first, last)`; wait for receipt (timeout `receipt_timeout_seconds` = 180); status != 1 -> `AnchorUnavailable` ("reverted").
5. Parse `Anchored` event; insert row into `anchors` (deployment=`deployedAt`, contract address, chain id, batch id, first/last entry id, root hex, tx hash, block number, gas used, anchored_at = event timestamp).
Bigger backlogs are anchored over several batches. All entry kinds (release, violation, trust_reset) are anchored.

### 3.11 Proof and verification (Phase 5)
- `GET /ledger/proof/{id}` -> `Anchorer.proof`: not covered by a cached batch for the current deployment -> `{entry_id, anchored:false, last_anchored_entry_id, next_anchor_within_seconds}`; else the batch leaves are recomputed from stored ledger hashes and `{entry_id, anchored:true, entry_hash, proof, batch, network, chain_id, contract}` is returned. Reveals only hashes.
- `Anchorer.verify_entry(entry)` (dashboard Verify): leaf recomputed from entry **content** (`ledger.compute_hash(entry)`, not the stored hash), proof walked, `getBatch(batch_id)` read from chain. `status` is `pending` | `anchored` | `mismatch` | `unavailable`; `anchored` requires `computed == chain.root` and `first <= id <= last`.
- `GET /anchors/verify` -> `verify_ledger_against_chain(entries, batches)`: for each on-chain batch recompute the root from ledger content; failure reasons "N anchored entries missing (first #k)" or "root recomputed from the ledger differs".
- `scripts/verify_anchors.py`: same from the DB file (read-only) vs contract; also flags truncation (`newest < last`); exit code 1 on failure.

### 3.12 Receipt verification by a student
`python -m scripts.verify_receipt <file|-> [--rpc URL]` (`verify_receipt.py:32-63`), using only the downloaded bundle and chain RPC:
1. Verify `receipt_jws` with the key in `trusttrail_jwks` (kid from header, ES256) -> "receipt signature valid" (docstring: compare the key with `/.well-known/jwks.json` once, out of band).
2. `compute_hash(ledger_entry) == receipt.entry_hash == ledger_entry.entry_hash` -> "ledger entry matches the receipt".
3. If `anchor_proof.anchored` is false: FAIL "anchored on-chain" (download again after the next batch).
4. `root_from_proof(leaf_hash(content_hash), proof)` -> "Merkle proof computed".
5. RPC chain id must equal the proof's; `getBatch(batch_id)` via minimal ABI; root equal and entry in [first,last] -> "on-chain root matches". Exit code 0 iff all pass.

### 3.13 Usability-study flow: see 7.6.

---------------------------------------------------------------------------------------------------

## 4. Algorithms and data formats

### 4.1 Pairwise subject (`app/pseudonyms.py:21-26`)
Port of Keycloak's `SHA256PairwiseSubMapper.generateSub` (26.x): `digest = SHA-256(utf8(sector + local_sub + salt))`; `sub = str(uuid.UUID(bytes=MD5(digest).digest(), version=3))` (code comment: equals `UUID.nameUUIDFromBytes(hash)`, an MD5-based version-3 UUID).
Inputs: `sector` = the single hostname shared by all of the client's `redirectUris` (`urlparse(u).hostname`; `ValueError` if hosts differ; used when no `sectorIdentifierUri`); `local_sub` = Keycloak user UUID; `salt` = client's mapper config `pairwiseSubAlgorithmSalt` (random per client; read through Admin API `protocol-mappers/models` where `protocolMapper == "oidc-sha256-pairwise-sub-mapper"`).
Mapping table rebuild (`PseudonymMap.rebuild`): for all users (`GET /users?max=1000&briefRepresentation=false`) compute the sub and replace that client's rows. `resolve` rebuilds once on a miss. Integration test `test_trusttrail_recomputes_keycloak_pseudonyms` compares the computed value with live Keycloak for every student x service. Demo-scale limit: 1000 users (`keycloak.py:70`).
Unit tests (`test_pseudonyms.py`, 6 cases): deterministic UUID v3; changes with each of sector/sub/salt (parametrized); sector = single redirect host; mixed hosts rejected.

### 4.2 Profiles -> attributes (`config/profiles.yaml`; order `[anonymous, pseudonym, partial, total]`, later = more revealing)
| Profile | `sub` returned | Attributes |
|---|---|---|
| anonymous | false | affiliation |
| pseudonym | true | affiliation |
| partial | true | affiliation, department, program, year |
| total | true | affiliation, department, program, year, name, email, roll_no |
`profile_attributes(p)` = attributes ∪ {"sub"} if `sub` is true. Attribute vocabulary = {sub} ∪ all profile attributes = {sub, affiliation, department, program, year, name, email, roll_no} (8 names; `settings.py:46-51`). Value sources: Keycloak user attributes (`affiliation, roll_no, department, program, year`), `firstName`+`lastName` -> `name`, `email`. Profiles are nested (test `test_profiles_are_nested`).
Tier -> cap (`trust.yaml:3-7`): fully_trusted -> total; semi_trusted -> partial; untrusted -> pseudonym; blocked -> anonymous. Base tiers: library untrusted, lms semi_trusted, exam fully_trusted; scripted overasker semi_trusted, retainer semi_trusted, tiercap untrusted.
Anonymous caveat: TrustTrail releases no `sub`, but the service's Keycloak ID token still has its pairwise `sub` (README:657-659).

### 4.3 Purpose declaration (compact JWS)
Header: `alg` in {ES256, RS256}; `kid` = registered key id (RFC 7638 thumbprint: SHA-256 of JSON with members `crv,kty,x,y` (EC) or `e,kty,n` (RSA), sorted keys, compact separators, base64url without padding; `jose_util.py:7-15`); `typ` = `purpose-declaration+jwt`.
Payload: `client_id`, `aud` = `trusttrail`, `attributes` (names from vocabulary; `sub` means the per-service pseudonym), `purpose` (1-500 chars), `retention_until` (ISO date `YYYY-MM-DD` meaning end of that day UTC, i.e. 00:00 UTC + 86400 s; or a timestamp with timezone, exact), `nonce` (unique per service; DB `UNIQUE(client_id, nonce)`), `iat`, `exp` (integers; `exp - iat <= 90 days`; 30 s skew tolerance).
`config/declarations.yaml`: `audience: trusttrail`; `algorithms: [ES256, RS256]` ("never none or HMAC"); `max_lifetime_days: 90`; `clock_skew_seconds: 30`; `max_purpose_length: 500`.
Stored record (`declarations` table, `db.py:18-32`): `declaration_id` (PK, first 16 hex of `jws_sha256`), `client_id`, `nonce`, `attributes` (JSON list), `purpose`, `retention_until`, `issued_at`, `expires_at`, `kid`, `jws` (verbatim), `jws_sha256` (SHA-256 hex of the JWS string), `received_at`. Public view = all fields except `received_at`.
Submission refusal codes: 400 `malformed`, `unsupported_alg`, `unknown_key`, `bad_signature`, `wrong_audience`, `expired`, `not_yet_valid`, `lifetime_too_long`, `unknown_attribute`, `retention_in_past`; 409 `replayed_nonce`. Key is selected by the **unverified** `client_id` claim and ownership is then proven by the signature (`declarations.py:81-82`).
Unit tests (`test_declarations.py`, 16): valid; wrong key; tampered payload; expired; iat in future; lifetime too long; wrong audience; unknown attribute; retention over; missing claim; wrong typ; another client's key; `alg:none`; usable window; exact-timestamp retention; timestamp without timezone malformed.

### 4.4 Release receipt (JWS, ES256; `receipts.py`)
Header `{alg: ES256, kid: <thumbprint of TrustTrail public key>, typ: "release-receipt+jwt"}`. Payload: `iss:"trusttrail"`, `iat` (int seconds), `jti` (uuid4), `service`, `profile`, `attributes` (sorted names, never values), `subject` (pairwise sub, **only if `sub` is among released names**), `purpose`, `retention_until`, `declaration_id`, `declaration_sha256`, `entry_id`, `entry_hash`, `released_at` (= ledger entry time). Key: EC P-256 (SECP256R1), PKCS8 PEM, unencrypted, `/data/receipt_signing_key.pem`, mode 0600, generated on first use. Public key at `GET /.well-known/jwks.json` -> `{"keys":[{kty,crv,x,y,kid,alg:"ES256",use:"sig"}]}`. Violations have no receipt.

### 4.5 Ledger entry (`ledger` table, `db.py:36-52`)
Columns (all hashed except `entry_hash`): `entry_id` INTEGER PK (1,2,3,...), `kind` (`release` | `violation` | `trust_reset`), `rule` (`undeclared_attribute` | `after_retention` | `above_tier_cap` | ""), `time` (UTC ISO 8601, microseconds, `Z`), `service_id`, `student_pseudonym` (per-service pairwise ID, never the Keycloak user ID; "" for trust_reset and login-time violations), `profile` (release: granted profile capped by current cap; violation: granted/requested profile; "" for reset), `attributes_requested` (JSON list), `attributes_released` (JSON list of names; `[]` for violation/reset), `purpose` (for `trust_reset` = admin's reason), `retention_until`, `declaration_id`, `service_signature` (third segment of the declaration JWS), `prev_hash`, `entry_hash`. (README's field table omits `rule` and `attributes_requested`; the code is authoritative.)
`HASHED_FIELDS` (14): entry_id, kind, rule, time, service_id, student_pseudonym, profile, attributes_requested, attributes_released, purpose, retention_until, declaration_id, service_signature, prev_hash (`ledger.py:24-26`).
Canonical JSON (`ledger.py:30-34`): dict of HASHED_FIELDS, `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`. Code comment: values are only strings, ints or lists of strings, so this is unambiguous "without a full JCS (RFC 8785) implementation".
Hash chain: `entry_hash = SHA-256(canonical)` (hex); `prev_hash` of entry n = `entry_hash` of n-1; entry 1 uses `GENESIS = "0"*64`. List fields sorted before hashing; `attributes_requested` defaults to `attributes_released`.
`verify` (`ledger.py:120-131`) walks entries and stops at the first one whose id differs from expected ("expected entry N (missing or reordered)"), whose `prev_hash` differs ("prev_hash does not match the previous entry"), or whose recomputed hash differs ("entry content does not match its hash"); returns `ChainCheck{ok, entries_checked, head_hash, first_bad_entry, reason}`.
Violation window query: kind `violation`, same service, `entry_id >` MAX id of that service's `trust_reset`, `time >= since` (string compare of ISO timestamps).
Append-only triggers (`db.py:55-58`): `BEFORE UPDATE`/`BEFORE DELETE` -> `RAISE(ABORT, 'ledger is append-only')` (only stops normal SQL use).
`db.init` raises RuntimeError for a pre-Phase-4 ledger without `rule` column ("reset the demo data with: docker compose down -v"); a pre-final `anchors` table without `deployment` is dropped.
Concurrency: all DB access through `db.tx()` = global `threading.Lock` + single shared connection (`check_same_thread=False`) (`db.py:111-128`).

### 4.6 Violation and reset entries
`kind="violation"`; `rule` constants (`errors.py:17-19`): rule 1 `undeclared_attribute` (refusal `attribute_not_declared`), rule 2 `after_retention` (refusal `retention_passed`), rule 3 `above_tier_cap` (refusal `attribute_above_tier_cap` at `/release`, or Keycloak `invalid_scope` at login detected via events). `attributes_requested` = what was asked; `attributes_released = []`. Login-time rule 3: `profile` = requested profile, `attributes_requested = sorted(profile_attributes(requested))`, no pseudonym or declaration. `trust_reset`: `purpose=reason`, `attributes_requested=[]`.

### 4.7 Trust score and tiers (`trust.py:26-47`, `config/trust.yaml`)
```
score = max(0, start(100)
              - (0 if client has policyUri else no_privacy_policy(15))
              - (incomplete_metadata(10) if any of required_metadata missing else 0)
              - violation_step(25) * violations)
demotions = int((start - score) // tier_band(25))
tier = tier_order[max(index(base_tier) - demotions, 0)]   # tier_order = [blocked, untrusted, semi_trusted, fully_trusted]
cap  = tiers[tier]      # blocked->anonymous, untrusted->pseudonym, semi_trusted->partial, fully_trusted->total
```
Constants: `start: 100`, `no_privacy_policy: 15`, `incomplete_metadata: 10`, `required_metadata: [name, description, rootUrl, tosUri]` (looked up on the Keycloak client object or its `attributes`), `violation_step: 25`, `tier_band: 25`, `violation_window_days: 90`, `sync_seconds: 3`. File header: "Every number here is a starting value to tune, not a validated constant."
Consequences: one violation = -25 = one tier; no privacy policy alone = 85 (no demotion); missing policy + incomplete metadata = 75 (1 demotion; test `test_registration_gaps_alone_can_cost_a_tier`); missing policy + one violation = 60 (floor(40/25) = 1 demotion); missing policy + two violations = 35 (2 demotions). Floors: score 0, tier `blocked`. Alumni Tracker (`retainer`) has no `policy_uri` so starts at 85.
Violations counted: last 90 days **and** after the service's latest `trust_reset`.
`GET /trust` state per service: `{service_id, score, privacy_policy_declared, missing_metadata, violations, demotions, base_tier, tier, cap, violations_by_rule}`.
Double enforcement: (1) Keycloak optional-scope removal (login refused); (2) `/release` caps the token's profile.
Unit tests (`test_trust.py`, 12 cases): complete registration -> full marks; missing policy costs points; missing metadata costs once; each violation = one step and one tier; score never negative; registration gaps alone can cost a tier; tier moves down per demotion (5 parametrized cases incl. floor); caps follow tiers.

### 4.8 Merkle tree (`app/merkle.py`, RFC 6962 conventions)
- `leaf = SHA-256(0x00 || bytes.fromhex(entry_hash))`.
- `node = SHA-256(0x01 || left || right)`.
- Levels: adjacent nodes are paired; an odd last node is **promoted unchanged** (not duplicated: "duplication lets two different batches share a root"). Root of one leaf = its leaf hash. Empty batch -> `ValueError`.
- Proof: list of `{hash (hex), side: "left"|"right"}` from leaf to root; a promoted node contributes no step at that level. `root_from_proof` computes `node_hash(sibling, node)` if side is "left", else `node_hash(node, sibling)`.
- Verification recomputes the leaf from entry **content**, so an edit that leaves the stored hash untouched is also caught.
Tests: `test_merkle.py` (17 cases): single leaf; three-leaf promotion; proofs verify for n in {1,2,3,4,5,7,8,9,16,33}; tampered leaf and sibling fail; domain separation; duplicating the last leaf changes the root; empty rejected. `test_anchoring.py` (5): untouched ledger matches; full rewrite caught; edit with stored hash left alone caught; truncation caught; only the affected batch fails.

### 4.9 Smart contract `TrustTrailAnchor` (`chain/contracts/TrustTrailAnchor.sol`, 56 lines)
- Storage: `address public immutable owner` (= `msg.sender` at construction); `Batch[] private batches`, `struct Batch { bytes32 root; uint64 firstEntryId; uint64 lastEntryId; uint64 anchoredAt; }` (`anchoredAt = block.timestamp`).
- Event: `Anchored(uint256 indexed batchId, bytes32 root, uint64 firstEntryId, uint64 lastEntryId, uint64 anchoredAt)`.
- Custom errors: `NotOwner()`, `EmptyRange()`, `NotContiguous(uint64 expectedFirstEntryId)`.
- `anchor(bytes32 root, uint64 firstEntryId, uint64 lastEntryId) external returns (uint256 batchId)`: `msg.sender != owner` -> `NotOwner`; `lastEntryId < firstEntryId` -> `EmptyRange`; `expected = batches.length == 0 ? 1 : last.lastEntryId + 1`; `firstEntryId != expected` -> `NotContiguous(expected)`; push; emit.
- Views: `batchCount()`, `getBatch(uint256) -> Batch memory`, `lastAnchoredEntryId() -> uint64` (0 if none). The only state-changing function is `anchor`; no function updates or deletes a batch (enforced by a test).
- Anchoring parameters (`config/anchoring.yaml`): `interval_seconds: 300`, `max_batch_entries: 5000`, `receipt_timeout_seconds: 180`; env `ANCHOR_INTERVAL_SECONDS` overrides the interval.
- Deploy script (`chain/scripts/deploy.ts`): writes `deployments/<name>.json` (`localhost` for network `chainNode`, else the network name) with `network, chainId, address, owner, deployBlock, deployTx, deployGas, deployedAt (ISO), abi`; reuses an existing contract when the file exists, chain id matches and code exists at the address, unless `FORCE_DEPLOY` is set. TrustTrail keys its local `anchors` cache by `deployedAt` (a fresh local chain reuses the same address).
- Sepolia: procedure in README:512-533; the README says it was rehearsed against the local chain only, "a real Sepolia run still needs your RPC URL and funded key". **No Sepolia deployment exists in the repo.**
- Gas numbers: 7.2.

### 4.10 Proof format
Anchored: `{"entry_id","anchored":true,"entry_hash","proof":[{"hash","side"},...],"batch":{deployment, contract_address, chain_id, batch_id, first_entry_id, last_entry_id, root, tx_hash, block_number, gas_used, anchored_at},"network","chain_id","contract"}`. Pending: `{"entry_id","anchored":false,"last_anchored_entry_id","next_anchor_within_seconds"}`.

### 4.11 Access-token validation (`tokens.py`)
RS256 only; JWKS from `{KC_INTERNAL_URL}/realms/trusttrail/protocol/openid-connect/certs` (`PyJWKClient`, cached; rebuilt once on unknown kid); `issuer` must equal `ISSUER` (`KC_PUBLIC_URL/realms/trusttrail`); **no `aud` check** (Keycloak does not put services in `aud`; service identified by `azp`); requires `typ == "Bearer"`, `azp`, `sub`. No revocation check (README:662). `verify_service_token` additionally requires `client_id == azp` (only client-credentials tokens carry `client_id`).

### 4.12 Admin auth
`Authorization: Bearer <TRUSTTRAIL_ADMIN_TOKEN>` compared with `hmac.compare_digest`; an empty configured token always yields 401 `not_admin` (`main.py:49-52`).

---------------------------------------------------------------------------------------------------

## 5. HTTP API reference

TrustTrail refusals are `{"error": code, "detail": text}` (`main.py:41-46`); rule-breaking refusals at `/release` add `"violation": {"rule","entry_id"}`. FastAPI validation errors (422) are not customised. Base URL `http://localhost:8000`; interactive docs at `/docs`.

### 5.1 Core (`app/main.py`)
| Method path | Auth | Request | Success | Errors |
|---|---|---|---|---|
| `GET /health` | none | | `200 {"status":"ok"}` | |
| `GET /.well-known/jwks.json` | none | | `{"keys":[ES256 public JWK]}` | |
| `POST /services/keys` | Bearer client-credentials token of the service | `{"keys":[JWK,...]}` | `200 {"client_id","kids"}` | 401 `missing_token`/`invalid_token` (student tokens rejected); 400 `invalid_jwks`; 409 `kid_conflict` |
| `POST /declarations` | none (JWS signature) | `{"declaration":"<JWS>"}` | `201` `{declaration_id, client_id, nonce, attributes, purpose, retention_until, issued_at, expires_at, kid, jws, jws_sha256}` | 400 `malformed`, `unsupported_alg`, `unknown_key`, `bad_signature`, `wrong_audience`, `expired`, `not_yet_valid`, `lifetime_too_long`, `unknown_attribute`, `retention_in_past`; 409 `replayed_nonce` |
| `GET /declarations/{declaration_id}` | none | | same object | 404 `not_found` |
| `POST /release` | Bearer student's access token (for that service) | `{"declaration_id"?: str, "attributes"?: [str]}` | `200 {"service","profile","declaration_id","entry_id","released":{name:value},"receipt":"<JWS>"}` | 401 `missing_token`, `invalid_token`; 403 `no_declaration`, `declaration_expired`, `retention_passed` (rule 2), `attribute_not_declared` (rule 1), `attribute_above_tier_cap` (rule 3), `attribute_above_profile` (no violation), `unknown_subject` |
| `GET /ledger/verify` | none | | `{"ok","entries_checked","head_hash","first_bad_entry","reason"}` (no entry contents) | |
| `GET /ledger/proof/{entry_id}` | none | int | see 4.10 | 503 `anchoring_unavailable` |
| `GET /anchors` | none | | `{"network","chain_id","contract","interval_seconds","batches":[{root, first_entry_id, last_entry_id, anchored_at, batch_id, tx_hash, block_number, gas_used}]}` (tx/block/gas from local cache, may be null) | 503 `anchoring_unavailable` |
| `POST /anchors/run` | admin bearer | | `{"batch":{...}}` or `{"batch":null}` | 401 `not_admin`; 503 |
| `GET /anchors/verify` | none | | `{"ok","batches_checked","anchored_up_to","unanchored_entries","failures":[{batch_id,reason}]}` | 503 |
| `GET /trust` | none | | `{service_id: state}` for all six configured services | |
| `POST /trust/sync` | admin bearer | | `{service_id: state}` after polling events and re-applying caps | 401 `not_admin` |
| `POST /trust/{service_id}/reset` | admin bearer | `{"reason": str}` | `{"entry_id","state"}` | 401 `not_admin`; 404 `not_found` |

### 5.2 Dashboard (`app/dashboard.py`, prefix `/dashboard`; cookie `tt_dashboard`)
| Method path | Auth | Response |
|---|---|---|
| `GET /dashboard` | none | HTML page |
| `GET /dashboard/login` | none | redirect to Keycloak (client `dashboard`, scope `openid profile`) |
| `GET /dashboard/callback` | OIDC code | sets session, redirects to `/dashboard` |
| `GET /dashboard/logout` | | clears session, redirects |
| `GET /dashboard/api/releases` | session | `{"student": name, "releases":[{entry_id, kind, rule, time, service, service_id, profile, attributes, requested, purpose, delete_by}]}` newest first |
| `GET /dashboard/api/verify/{entry_id}` | session | `{entry_id, ok, checks{...}, whole_ledger{...}, anchor{...}}` |
| `GET /dashboard/receipts/{entry_id}` | session | bundle JSON attachment |
| `GET /dashboard/receipts` | session | list of bundles, attachment |
Errors: 401 `not_logged_in`; 404 `not_found` ("no such release for you") for entries not belonging to the student.

### 5.3 Study (`app/study.py`, prefix `/study`; HTML pages, no auth, session cookie via the shared middleware)
`GET /study` (start page, code form), `POST /study/start` (code regex `P\d{2}`, `P00` rejected; reserved codes P98/P99 are reset on start; a real code that already has results is refused), `GET /study/task`, `GET /study/go`, `GET /study/baseline/callback`, `GET /study/trusttrail`, `POST /study/trusttrail`, `GET /study/preview/{key}` (P or F; records nothing), `GET /study/q1`, `POST /study/q1`, `GET /study/screen`, `POST /study/screen`, `GET /study/done`.

### 5.4 Test-service apps (`services/app.py`, ports 8001-8003)
`GET /` (shows declared purpose; after login shows Keycloak ID-token claims, the `/release` result and decoded receipt payload), `GET /login`, `GET /callback` (exchange code, `current_declaration()`, `POST /release` with `{"declaration_id"}`), `GET /logout`. Cookie `{SERVICE_ID}_session`. There are **no `/privacy` or `/terms` routes** although `services.yaml` registers those URIs (metadata strings only).

### 5.5 Keycloak endpoints used
Token `/realms/trusttrail/protocol/openid-connect/token`; JWKS `/certs`; discovery `/.well-known/openid-configuration`; Admin `/admin/realms/trusttrail/...`: `clients`, `client-scopes`, `users`, `users/profile`, `events/config`, `GET /clients/{id}/protocol-mappers/models`, `GET /clients/{id}/optional-client-scopes`, `PUT|DELETE /clients/{id}/optional-client-scopes/{scopeId}`, `GET /events?type=LOGIN_ERROR&max=200`, `GET /users?max=1000&briefRepresentation=false`, `GET /users/{id}`.

---------------------------------------------------------------------------------------------------

## 6. Implementation statistics (`wc -l`; vendored code excluded; blanks and comments included)

| Component | Files | Lines |
|---|---|---|
| TrustTrail app, Python (`trusttrail/app/*.py`) | 20 modules (+ empty `__init__.py`) | 2,159 |
| Dashboard HTML/JS (`app/static/dashboard.html`) | 1 | 139 |
| Scripts (`trusttrail/scripts/*.py`: seed, bad_services, demo_phase1/2/4/5, demo_tamper, verify_anchors, verify_receipt) | 9 (+ `__init__`) | 1,025 |
| Tests, Python (`trusttrail/tests/*.py`) | 13 test files + conftest | 1,198 |
| Evaluation (`trusttrail/eval/*.py`; + `run_all.sh`) | 6 py (+ `__init__`) + 1 sh | 598 (+ 12) |
| Test-service app (`services/app.py` 136, `jwk.py` 14) | 2 | 150 |
| Solidity contract | 1 | 56 |
| Chain TypeScript (deploy 43, test 66, hardhat config 26) | 3 | 135 |
| Java Keycloak mapper | 1 | 72 |
| Host scripts (`check_browser_sso.sh` 38, `check_dashboard.sh` 70, `check_study.py` 116) | 3 | 224 |
| YAML config (`config/*.yaml`) | 7 | 255 |
| `docker-compose.yml` | 1 | 89 |
| Usability materials (md) | 5 | 256 |
| Taxonomy CSVs | 2 | 15 |
| README.md | 1 | 739 |
Python excluding tests: app 2,159 + scripts 1,025 + eval 598 + services 150 + `check_study.py` 116 = 4,048; with tests 5,246. The sum over app, dashboard HTML, scripts, tests, eval py+sh, services, Solidity, TS, Java and host scripts is 5,768 + 12 (eval shell) lines; my own `wc` total over the first set (without eval .sh and with host scripts) was 5,768.
Test file sizes (lines): anchoring 69, declarations 123, eval 70, ledger 132, merkle 58, phase1_int 94, phase2_int 132, phase3_int 87, phase4_int 133, phase5_int 98, pseudonyms 32, release 78, trust 60, conftest 32.

### 6.1 Test counts
**Python** (`pytest.ini`: `testpaths=tests`, `pythonpath=.`, marker `integration: needs the running, seeded docker compose stack`)
- Unit (unmarked; `pytest --collect-only -m "not integration"` reported **94 tests** when `CONFIG_DIR`, `DATA_DIR`, `SESSION_SECRET` were set):
  | File | cases | test functions |
  |---|---|---|
  | `test_anchoring.py` | 5 | 5 |
  | `test_declarations.py` | 16 | 16 |
  | `test_eval.py` | 12 | 7 (`test_chose_as_intended` parametrized) |
  | `test_ledger.py` | 12 | 12 |
  | `test_merkle.py` | 17 | 8 (`test_every_proof_verifies` x10) |
  | `test_pseudonyms.py` | 6 | 4 |
  | `test_release.py` | 14 | 10 |
  | `test_trust.py` | 12 | 8 |
  | **Unit total** | **94** | **70** |
- Integration (module-level skip when the Keycloak realm is unreachable, so not collectable offline). Counts below are derived by **reading** defs and parametrization, not by running:
  | File | functions | cases | notes |
  |---|---|---|---|
  | `test_phase1_integration.py` | 8 | 20 | 5 students x different-ID test; 3 services x each of 4 per-service tests = 12; plus stable pseudonym, recompute check, forged token |
  | `test_phase2_integration.py` | 13 | 13 | |
  | `test_phase3_integration.py` | 6 | 6 | |
  | `test_phase4_integration.py` | 7 | 9 | bad-service test x3 (overasker, retainer, tiercap) |
  | `test_phase5_integration.py` | 7 | 7 | needs the local chain |
  | **Integration total** | **41** | **55** | |
- Python total: **149 test cases** (94 unit + 55 integration, the latter derived), 111 test functions.
- `conftest.py` autouse fixture (integration only): `POST /trust/sync`, then for any service with violations or a non-base tier `POST /trust/{id}/reset` with reason "test isolation" (recorded in the ledger).
**Contract tests**: `chain/test/TrustTrailAnchor.ts`, **6** mocha/chai tests (Hardhat 3, ethers 6): stores a batch and emits `Anchored` (fields, `batchCount`, `lastAnchoredEntryId`); requires contiguity from entry 1 (wrong start -> `NotContiguous(1)`; overlap and gap -> `NotContiguous(6)`; then 6..9 accepted); rejects empty range (`EmptyRange`); only owner can anchor (`NotOwner`); no function can change a batch (writers == `["anchor"]`); gas for a 100,001-id range (entries 2..100001) is lower than the first anchor's gas.
**Shell/script checks (not pytest)**: `check_browser_sso.sh` (4 PASS/FAIL: different `sub`; no `sid`; no `session_state` in redirect; no `auth_time`), `check_dashboard.sh` (6: dashboard lists library+LMS releases; Verify all pass; receipt bundle has receipt/entry/declaration; other entry returns 404; Verify matches blockchain anchor; downloaded receipt verifies via `verify_receipt`), `check_study.py` (plays P98/P99 through real Keycloak and study screens and checks the analysis).

### 6.2 What the tests check (by file)
- `test_release.py`: `granted_profile` from scopes (parametrized); profile attributes match config; profiles nested; default request = declared ∩ allowed; undeclared attribute -> rule 1; above tier cap -> rule 3; above granted profile but within cap -> not a violation; above lowered cap but within agreement -> not counted again; `build_release` fills values and pseudonym; anonymous release has no identifier.
- `test_ledger.py` (in-memory DB): empty ledger verifies; chain links; canonical hash; triggers append-only; edited entry detected; edited and rehashed entry breaks the next link; deleted; renumbered; full rewrite passes the chain check but not the old head (documents the limit); truncating the tail passes the chain check (documents the limit); entries for one student; violations count only after the latest reset.
- `test_eval.py`: nearest-rank percentile; plan counterbalances screens and tasks (4 groups); what the service received per screen; chose-as-intended (parametrized); Q1 scoring; sign test; taxonomy sheet well-formed.
- Phase 1 integration: each service sees a different ID per student; stable across logins; TrustTrail recomputes Keycloak pseudonyms; tokens carry no personal claims; nothing links sessions across services; release matches profile; Keycloak enforces tier cap; forged token rejected.
- Phase 2: key registration needs the service's own token; private key material rejected; valid signature accepted and stored; bad signature refused; expired refused at submission; expired declaration cannot back a release; attribute not covered refused; release without declaration refused; another service's declaration refused; replayed nonce refused; declared but above tier cap refused; above granted profile within cap refused without violation; release returns a receipt signed by TrustTrail.
- Phase 3: release writes exactly one matching entry; receipt points at the entry; refusals never write a release; public verify matches ledger; **10 concurrent releases** keep the chain intact; dashboard API requires login.
- Phase 4: each bad service caught with the right rule, score drops one step, tier and max profile drop one, scope removed in Keycloak, Keycloak refuses the old profile; cascade to anonymous; no double counting after demotion; token issued before demotion capped; honest services get zero violations; reset restores base tier and is recorded; admin endpoints need token.
- Phase 5: anchors contiguous and cover the ledger; nothing new = no transaction; new entry pending until next batch; proof reaches on-chain root and reveals only hashes; whole ledger verifies vs chain; standalone receipt check passes and catches an edited entry; anchoring admin endpoint needs token.

---------------------------------------------------------------------------------------------------

## 7. Evaluation

Environment for all measurements (README:557-559, eval docstrings): one laptop, all Docker containers local, password grant (no browser), invented data. Each results file is stamped "fake data, local machine".

### 7.1 (a) Latency (`eval/bench_latency.py`, `python -m eval.bench_latency [--runs 200] [--warmup 10]`)
Method: baseline = plain Keycloak client `bench-baseline` (all attributes in ID token; one token request; scope `openid`). TrustTrail variant = LMS password-grant token (scope `openid profile-partial`) + `POST /release` (token verification, trust cap, declaration check, pseudonym map, Keycloak user fetch, ledger entry + signed receipt). 10 warm-up iterations of each; then 200 runs of each variant in a **random shuffled interleaved order**, students round-robin over the 5 users; timer `time.perf_counter()`; records `total_ms`, `token_ms`, `release_ms`; stats: median, p95 (nearest-rank), mean, min, max (`eval/common.py:10-19`). Anchoring is asynchronous and excluded; each TrustTrail run adds a real ledger entry. Raw data: `latency_raw.csv` (400 rows). Not measured: browser redirects, concurrency or load.

Committed version (HEAD; generated 2026-10-30 10:00 UTC; matches README):
| Variant | Runs | Median (ms) | p95 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| Plain OIDC login (no privacy layer) | 200 | 17.1 | 19.1 | 17.4 | 15.7 | 27.7 |
| TrustTrail login + release (total) | 200 | 21.2 | 24.7 | 21.6 | 19.3 | 37.1 |
|   of which: Keycloak token | 200 | 16.9 | 19.5 | 17.3 | 15.6 | 33.1 |
|   of which: TrustTrail /release | 200 | 4.2 | 5.8 | 4.4 | 3.4 | 7.4 |
Overhead: median **+4.0 ms** (+24%), p95 **+5.6 ms**. README:557 adds "an earlier run gave +3.4 / +4.5 ms".

Working-tree version (uncommitted; generated 2026-11-10 07:14 UTC; current `trusttrail/eval/results/latency.md`):
| Variant | Runs | Median (ms) | p95 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| Plain OIDC login (no privacy layer) | 200 | 16.0 | 20.2 | 16.7 | 15.1 | 49.4 |
| TrustTrail login + release (total) | 200 | 19.6 | 25.6 | 20.1 | 17.9 | 31.0 |
|   of which: Keycloak token | 200 | 15.9 | 20.8 | 16.4 | 14.9 | 24.6 |
|   of which: TrustTrail /release | 200 | 3.6 | 5.1 | 3.8 | 2.8 | 6.4 |
Overhead: median **+3.6 ms** (+22%), p95 **+5.5 ms**.
File notes: "Password grant on one laptop, all containers local; a browser login adds the same redirects to both variants. TrustTrail's token request is itself slightly different (pairwise ID, sid stripped, no claim mappers). Anchoring is asynchronous and not included."

### 7.2 Phase 5 anchoring measurements (README only; `scripts/demo_phase5.py --batches 3 --interval 12`; local Hardhat chain; a release about every 2 s)
| Batch | Entries | Gas used | Gas per entry | Delay min (s) | Delay median (s) | Delay max (s) | Tx confirmed in (s) |
|---|---|---|---|---|---|---|---|
| 13 | 6 | 77244 | 12874 | 1.1 | 7.3 | 12.1 | 0.03 |
| 14 | 6 | 77244 | 12874 | 1.4 | 6.4 | 12.2 | 0.05 |
| 15 | 6 | 77244 | 12874 | 1.1 | 7.2 | 12.9 | 0.03 |
Over 18 entries: median delay 6.8 s, p95 12.2 s, max 12.9 s. Delay = from the entry's time to the anchor transaction being confirmed on the same clock (block timestamps unused because Hardhat blocks must be at least 1 s apart and timestamps drift ahead). Script: releases at random 0.5-1.5 x `--every` s; anchor triggered via `POST /anchors/run` every `--interval` s; p95 index `round(p/100*(n-1))`.
Gas (README:464-466): **91,659** for the first batch on a new contract (initialises storage); about **77,240** for later ones "whatever the batch size"; the contract test anchors a 100,000-entry range for **77,268**; deployment **361,072** gas. README cost example: 77,240 gas at 1 gwei = 0.000077 ETH per anchor; a busy day at a 5-minute interval (288 anchors) about 0.022 ETH. Delay model (README:467-470): about half the interval on average, at most one interval plus block time; default 300 s -> median about 150 s, worst about 300 s plus ~12 s on Sepolia. These are estimates, not Sepolia measurements.

### 7.3 (b) Tamper test (`eval/tamper_test.py` -> `scripts/demo_tamper.py::tamper_matrix`)
Method: `--repeat 5` repetitions (`random.Random(seed=1)` chooses targets). Each repetition: ensure at least 6 entries; **anchor all entries** (`run_once`); add one release afterwards (for attack F); check that the live chain verifies; capture `held_hashes` = entry hashes from all stored receipts (simulating receipts students hold) and the on-chain batches; target `k` = random release (entry id > 1, not the last release); for each of six attacks, copy the live DB to a temp file, **drop the append-only triggers** (insider with file access), apply the attack, then evaluate three independent detectors: (i) hash chain `ledger.verify`; (ii) student receipts (count of held receipts whose entry is missing or whose recomputed hash differs); (iii) blockchain anchor (`verify_ledger_against_chain` against on-chain batches). The live ledger is never modified. Expected truth table hard-coded as `EXPECTED`; a mismatch is flagged "NO".
Attacks: A change an entry's attributes, leave its hash; B change purpose and recompute that entry's hash; C delete the entry; D change an entry and recompute every later hash; E cut off the tail (`DELETE ... entry_id >= last_anchored`); F change an entry made after the last anchor and fix hashes onward.
Current results file (working tree 2026-11-10; HEAD file has identical table):
| Attack | Hash chain | Student receipts | Blockchain anchor | Any check | As designed |
|---|---|---|---|---|---|
| A. change an entry, leave its hash | 5/5 | 5/5 | 5/5 | 5/5 | yes |
| B. change an entry, recompute its hash | 5/5 | 5/5 | 5/5 | 5/5 | yes |
| C. delete an entry | 5/5 | 5/5 | 5/5 | 5/5 | yes |
| D. change an entry, recompute every later hash | 0/5 | 5/5 | 5/5 | 5/5 | yes |
| E. cut off the tail of the ledger | 0/5 | 5/5 | 5/5 | 5/5 | yes |
| F. change an entry made after the last anchor, fix its hash | 0/5 | 5/5 | 0/5 | 5/5 | yes |
"Every repetition matched the design." Raw: `tamper_raw.csv` (30 rows = 5 x 6; columns repetition, target_entry, attack, chain_detected, receipts_detected, receipts_failed, anchor_detected). Notes: in F the receipts detect only because receipts exist for the edited entry (hash held outside the DB); the file notes "until the next batch, only receipts protect a new entry".
README single-run demos: Phase 3 (entry #11 of 22): A detected at #11 (1 receipt fails); B detected at #12 (1); C detected at #12 (1); D **not detected** by chain (12 receipts fail; earlier head hash detects); E **not detected** (1 fails; earlier head detects) (README:276-286). Phase 5 (entries up to #133 anchored, #134 afterwards): A, B, C detected by chain, 1 receipt fails, anchor detects; D chain not detected, 39 receipts fail, anchor detects; E chain not detected, 2 fail, anchor detects; F chain not detected, 1 fails, anchor **not detected** (README:475-486).

### 7.4 (b) Violation-detection test (`eval/violation_test.py` -> `scripts/demo_phase4.py::detection_run`)
Method: `--repeat 3` repetitions x `--attempts 5` per bad service. Each repetition starts with `reset_all` (sync, then recorded reset for every service) so all services begin at base tier. Honest traffic first: library, lms, exam x 5 students x 2 rounds = 30 releases per repetition (declare, password-grant login with the service's `wants` profile, `/release`). Then for each bad service 5 `misbehave('asha')` attempts, after each polling `POST /trust/sync` every 0.5 s (timeout 15 s) until its violation count rises; records score before/after, tier and cap after every attempt. "Detected" = violation entries with the expected rule; "wrong rule" = any other rule; false positives = violations recorded for honest services; tier changes of honest services. Ends with `reset_all("end of violation test")`.
Results (working tree 2026-11-10; same table content in HEAD):
| Service | Misbehaviour | Rule | Attempts | Detected | Missed | Wrong rule | Detection rate | Tier after each attempt (every repetition) | Max profile |
|---|---|---|---|---|---|---|---|---|---|
| Campus Deals | asks for attributes its declaration doesn't cover | 1 · undeclared attribute | 15 | 15 | 0 | 0 | 100% | semi_trusted → untrusted → blocked → blocked → blocked → blocked | partial → anonymous |
| Alumni Tracker | requests again after its promised deletion time | 2 · after retention | 15 | 15 | 0 | 0 | 100% | semi_trusted → untrusted → blocked → blocked → blocked → blocked | partial → anonymous |
| Career Portal | asks Keycloak for a profile above its tier cap | 3 · above tier cap | 15 | 15 | 0 | 0 | 100% | untrusted → blocked → blocked → blocked → blocked → blocked | pseudonym → anonymous |

| Honest services | Releases | Violations (false positives) | Tier changes |
|---|---|---|---|
| Digital Library, Learning System, Examination Portal | 90 | 0 | 0 |
Tier sequences list the initial state then the state after each of 5 attempts (6 values). `violations_raw.csv` has 9 data rows (3 repetitions x 3 services). README single-run table (`demo_phase4`, 5 attempts): 5/5/5 detected; scores 100→0, 85→0 (Alumni Tracker), 100→0; honest: 30 releases, 0 violations, 0 tier changes (README:368-378). Limits (file note): scripted clients only; "does not estimate how often real services misbehave, nor how often subtler misuse (anything after the data leaves TrustTrail) goes unseen".

### 7.5 (c) Taxonomy (`trusttrail/eval/taxonomy/taxonomy.csv`, `proposals.csv`; `eval/plot_taxonomy.py`)
Columns: `feature_id, feature, definition_in_paper, trusttrail_suggested, trusttrail_score, trusttrail_evidence, trusttrail_scored_by, P1..P4_score, P1..P4_evidence`. Valid scores: `0`, `partial`, `full` (plotted as 0 / 0.5 / 1.0); an empty cell is drawn as "not scored", never as 0. Chart `results/taxonomy_chart.png`/`.svg`: while `trusttrail_score` is empty the TrustTrail column shows the suggested score hatched and starred; per-system coverage total = full 1 + partial 0.5 out of the number of features.
**Every feature name is prefixed `DRAFT:` and every `definition_in_paper` is `TODO`** (README:583-587: the builder could not verify the paper's exact nine features or four proposals). `proposals.csv` holds `P1..P4` with `short_name` "TODO proposal N" and TODO references. **All P1-P4 scores and evidence are `TODO`/empty; `trusttrail_score` is empty and `trusttrail_scored_by` is "TODO: a teammate who did not build this feature" for all nine rows.** A teammate who did not build the feature is meant to score it.
| ID | Draft feature | Suggested | Evidence as written in the CSV (abridged) |
|---|---|---|---|
| F1 | Unlinkability across services | partial | Pairwise sub per service (`test_each_service_sees_a_different_id`); sid, session_state, auth_time stripped (`check_browser_sso.sh`); login timing can still correlate (Phase 1 limits) |
| F2 | Anonymity | partial | Anonymous profile releases only `affiliation` via TrustTrail (`test_anonymous_release_has_no_identifier`), but the service's Keycloak ID token still carries its pairwise sub |
| F3 | Data minimisation / selective disclosure | full | Four profiles as client scopes; tokens carry no personal claims; release = declared ∩ allowed (`test_release_matches_profile`, `test_keycloak_tokens_carry_no_personal_claims`, `test_release.py`) |
| F4 | User control / consent over disclosure | 0 | Profiles and caps are set by the institution and the trust score; students cannot choose per release in the running system; per-attribute choice exists only in the `/study` prototype; 'partial' only if the team counts that prototype |
| F5 | Transparency / user awareness | full | Dashboard lists every release and refused request with service, attributes, purpose, delete-by; signed receipts downloadable (`check_dashboard.sh`, `dashboard.py`) |
| F6 | Purpose specification / use limitation | partial | Signed declaration required; undeclared attributes refused and recorded (rule 1); use after release cannot be enforced: declared and auditable, not guaranteed |
| F7 | Accountability / auditability | full | Signed declarations, hash-chained ledger, signed receipts, on-chain Merkle roots; every tamper attack detected by at least one check; covers only requests made to TrustTrail |
| F8 | Trust assessment of service providers | partial | Score from privacy policy, metadata and recorded violations lowers tier and Keycloak scope cap; heuristic weights, scripted clients only |
| F9 | Retention / deletion control | partial | `retention_until` declared and signed; requests after it refused and recorded (rule 2); deletion cannot be proven; keeping already-released data is invisible |
Suggested tally: full x3 (F3, F5, F7), partial x5 (F1, F2, F6, F8, F9), 0 x1 (F4).

### 7.6 (d) Usability study (design only; **NOT RUN; no results**; `eval/results/study.md` absent)
Materials: `eval/usability/consent_form.md` (53 lines; placeholders for team names, supervisor, contact, deletion date), `data_handling.md` (56), `facilitator_guide.md` (73), `questionnaire.md` (62; paper backup plus team-only answer key), `screens/README.md` (12; no screenshots in repo; suggested names `trusttrail_consent_P.png`, `trusttrail_consent_F.png`, `keycloak_consent_P.png`, `keycloak_consent_F.png`). Code: `app/study.py` (375), `eval/analyze_study.py` (176), `config/study.yaml` (60), `scripts/check_study.py` (116), study logic tests in `test_eval.py`.
Design: within-subject, 2 screens (Keycloak default consent = baseline; TrustTrail prototype consent) x 2 scenarios (P, F) = **4 tasks per participant**; target 15-20 classmates, about 15 min each (10 min of study); persona "Asha Kulkarni" (invented), never real data. Scenario P: Learning System, tier "Semi-trusted (may receive at most your partial profile)", keep 180 days, optional attributes [department, program, year, email, roll_no], intended = [department, program, year] (share some, not email/roll number; **impossible on the baseline by design**). Scenario F: Examination Portal, "Fully trusted (has a contract with the university)", keep 365 days, optional [name, roll_no, email, department, program, year], intended = all six.
Baseline = Keycloak's real consent page for clients `study-lms`/`study-exam` (`consentRequired`; `prompt=consent` forced every time); if accepted it receives `[name, email, roll_no, department, program, year, account_id]`. TrustTrail screen: purpose text, tier badge, "signed this promise on <date>", must-delete-by date, "Always shared" (`service_id`, "that you are a current student"), per-attribute checkboxes with nothing pre-ticked, buttons "Share selected" / "Don't share anything"; TrustTrail always releases `service_id`. It is a **prototype**: in the real system students cannot deselect attributes per release.
Counterbalancing (`plan_for`, `study.py:61-66`): `n = int(code[1:])`; screen order: odd n baseline first, even n TrustTrail first; scenario order: `n % 4 in (1,2)` P then F, else F then P; 4 groups; codes must be given out in order. Code regex `P\d{2}`; P98/P99 reserved for scripted checks and excluded from analysis.
Measures per task (`trials` table): outcome (shared/declined), `received` (JSON), `matched` (shared exactly what the task intended), `decision_ms` (TrustTrail: screen shown to choice measured in browser; baseline: includes any login), Q1 "Which of these does the service now have?" (8 options: name, email, roll_no, department, program, year, service_id, account_id, plus "Nothing at all"), confidence 1-5. Per screen (`conditions` table): purpose question (4 options; truth for TrustTrail = the stated purpose; for baseline = "The screen did not say"), retention question (truth: delete-by date for TrustTrail; "The screen did not say" for baseline), three 1-5 Likert items ("I understood exactly what I was agreeing to share."; "I could share exactly what I wanted to."; "I would be comfortable using this kind of screen for real university services."), optional comment (at most 1000 chars). Storage: `study.db` in the `tt-data` volume; participant code only.
Analysis plan (`analyze_study.py`): Q1 exact match (ticks equal what was received, "nothing" consistent) and per-item accuracy (share of the 8 items judged correctly); intended-choice rate per screen and task; comprehension compared with a **paired exact two-sided sign test** (ties dropped; `min(1, 2*sum_{i<=k} C(n,i)/2^n)`); purpose/retention accuracy; Likert medians; limits section; outputs `results/study.md`, anonymised CSVs, `study_comments.csv`; `--delete-all --yes` wipes the data.
Threats to validity (facilitator guide): convenience sample of students who know the team; a team member as facilitator; invented persona; prototype screen; task P impossible on the baseline by design (comprehension is the fairer comparison). Ethics: check whether IIIT Dharwad requires approval (open TODO). Consent: voluntary, deletion on request by code until a date, group-level reporting only.

### 7.7 Run-all
`eval/run_all.sh`: (a) `bench_latency --runs 200`; (b) `tamper_test --repeat 5` and `violation_test --repeat 3 --attempts 5`; (c) `plot_taxonomy`; "about 3 minutes" (README:541). Usability (d) is excluded.

---------------------------------------------------------------------------------------------------

## 8. Security / threat-model statements and Known Limits

### 8.0 Properties asserted in README/code (informal; no formal proofs)
- "This gives non-repudiable evidence of what a service promised. It does not guarantee the service keeps the promise." (README:113-114)
- "Only hashes go on-chain, never personal data." (README:404-405)
- Tamper-evident (not tamper-proof) ledger; attacks A-F and detectors (7.3).
- TrustTrail is "the only path for attribute values" (README:52-54); Keycloak tokens contain no personal claims.
- No private key in repo (README:126-127); keys generated at first use into Docker volumes; JWKS with private members rejected.
- Student tokens and service tokens are separated by the `client_id` claim (README:131-133).
- A student sees/verifies/downloads only their own entries; others return 404 (README:261).
- Receipt bundle allows verification "without trusting TrustTrail's server" (README:258-259); `verify_receipt.py` uses only the file and the chain.
- Adversaries implicitly modelled: colluding services (linking by sid/auth_time/pairwise IDs), over-asking, retaining and tier-cap-violating services, an insider with DB file access (drops triggers; attacks A-F), forged tokens and receipts.
- Demo-only weaknesses: password grant on service clients; unauthenticated `/study`; Hardhat account #0 key is public; Keycloak `start-dev` with dev database.

### 8.1 Known limits (Phase 1), README:642-662
- **Why `sid` is stripped, and what that costs.** Keycloak 26 adds the SSO session ID (`sid`) to every token with no built-in way to turn it off, and every service in one SSO session gets the same value, which would let colluding services link their pseudonyms. The custom mapper removes it, and the client settings also hide `session_state` and `auth_time`. The cost: service tokens no longer point to a Keycloak session, so refresh tokens (switched off), the userinfo endpoint and `id_token_hint` logout don't work for the test services. TrustTrail checks tokens locally, so it isn't affected. Keycloak 26.8 marks the "exclude session state" switch as deprecated; if a later version removes it, `session_state` would come back in the login redirect, and `scripts/check_browser_sso.sh` would catch that.
- **Timing can still link.** Two services that compare login times (`iat`) could still guess which pseudonyms belong to the same student. Pairwise IDs and the stripped session ID remove *identifiers*, not traffic analysis.
- **Anonymous profile.** TrustTrail returns no `sub` for `anonymous`, but the service's Keycloak ID token still contains its pairwise `sub`, so the service can still recognise a returning student.
- **We only see requests made to our system.** TrustTrail controls attribute values because Keycloak tokens contain none. It cannot control what a service does with data afterwards.
- Access tokens are checked locally (signature, issuer, expiry). Revocation before expiry is not checked.

### 8.2 Known limits (Phase 2), README:664-673
- **A declaration is a promise, not a guarantee.** TrustTrail can prove what a service promised and what it was given. It cannot see what the service does with the data afterwards, and it cannot prove deletion by `retention_until`.
- **Non-repudiation rests on key custody.** A signed declaration binds the service only as long as its private key is not shared or stolen. Registering a key requires the service's Keycloak client secret, so the client secret is the root of trust for key registration.
- **Purpose text is not checked for meaning.** TrustTrail checks attribute names against the declaration; it cannot judge whether the stated purpose is honest or proportionate.

### 8.3 Known limits (Phase 3), README:675-688
- **We only see requests made to our system.** The ledger records every release TrustTrail makes. It cannot record what a service does with the data afterwards.
- **The chain alone can't catch a full rewrite or a cut-off tail.** Someone with write access to the database file can drop the triggers, edit an entry and recompute every hash after it, or delete the newest entries; the chain still verifies. Students' receipts catch this for their own entries; Phase 5 anchoring catches it for everyone, but only from the moment of each anchor.
- **Tamper-evident, not tamper-proof.** The triggers only stop edits through normal SQL use. Verification shows that something changed; it cannot restore what was there.
- **The dashboard's Verify uses the receipt stored by TrustTrail.** An attacker who also rewrote the receipts table would pass that check. Receipts the student downloaded earlier are independent evidence (check them against the ledger entry, as the receipt file explains).

### 8.4 Known limits (Phase 4), README:690-707
- **The trust score is a heuristic.** The weights are hand-picked and were tested only with simulated clients. It ranks services by behaviour TrustTrail can see; it is not a measure of how trustworthy a service really is.
- **Only visible misbehaviour counts.** A service that stays inside its declaration but misuses the data afterwards, or never deletes it, gets a perfect score. Deletion cannot be proven.
- **Rule 2 only sees re-requests.** It catches a service that comes back after its deletion date, not one that quietly keeps what it already has.
- **Rule 3 at login depends on Keycloak's event log.** If events are switched off or expire before the next sync (every 3 s here, events kept for 1 day), those attempts are refused but not counted.
- **`manage-clients` is a broad Keycloak role.** TrustTrail could change any client, not just the scopes it needs to. Keycloak's fine-grained admin permissions could narrow this; not done here.
- **Resets are trusted.** Whoever holds the admin token can forgive a service. The reset is recorded in the ledger, but nothing stops it.
- Authlib 1.9 marks its httpx integration as deprecated in favour of `httpx2`. It works today; the bad-service scripts hide the notice.
Related Phase 4 design statements (README:316-320, 380-381): "Tier cap" means the cap from the service's agreement (base tier). A demoted service that still asks for what its agreement allowed is refused, but not counted again; "otherwise one violation would snowball into automatic blocking." `retention_until` may be a date (end of that day, UTC) or a timestamp with timezone; the retention violator uses a timestamp a few seconds ahead so the demo doesn't wait a day. "These are scripted clients: the counts show the rules fire as designed. They don't measure how often real services misbehave or how often the rules would miss a subtler misuse."

### 8.5 Known limits (Phase 5), README:709-725
- **An anchor proves "unchanged since the anchor", not "true when written".** If TrustTrail records something false, anchoring faithfully preserves the false record.
- **There is an anchoring window.** Entries newer than the last batch (up to one interval) are protected only by the hash chain and students' receipts (tamper attack F).
- **TrustTrail decides what to anchor.** It could leave a release out of the ledger entirely before anchoring; anchoring can't reveal a record that was never written. Receipts held by students are the counter-evidence.
- **The local chain is a stand-in.** Hardhat runs in memory with public test keys; its anchors prove nothing to outsiders. Only a public chain such as Sepolia (or mainnet) gives evidence independent of TrustTrail. Sepolia is a test network and could in principle be reset.
- **Key custody:** whoever holds the anchoring key can add batches, but cannot change or remove existing ones.
- **Library versions:** Hardhat 3.20.0 is pinned (current is 3.21.x, about two weeks newer), with Solidity 0.8.28 and web3.py 7.16.0. web3.py 8.0 exists; we stayed on 7.x, whose API is established.
Local chain lifecycle (README:505-510): the local Hardhat chain is in memory; `chain-deploy` reuses the existing contract if it is still on the chain and deploys a new one only on a fresh chain; TrustTrail then anchors from entry 1 again into the new contract; proofs show "pending" until it has. On Sepolia the contract and its history persist.

### 8.6 Known limits (Phase 6), README:727-739
- **The latency numbers come from one laptop** with everything local. They show the order of magnitude of the privacy layer's cost (a few milliseconds), not production performance or behaviour under load.
- **The tamper and violation tests use our own scripted attacks and clients.** They show the mechanisms work as designed, not how often real attackers or services would be caught.
- **The taxonomy features are a draft and the TrustTrail scores are self-assessed** until a teammate re-scores them; the authors' proposals are unscored until filled in from the paper.
- **The usability study is small and indicative.** It uses a convenience sample of classmates, a team member as facilitator, an invented persona, and a prototype screen. Students cannot yet deselect attributes in the running system. Task P is impossible on the baseline screen by design; comprehension is the fairer comparison.

### 8.7 Additional limits visible in code (author observations, not stated in README)
- Public read endpoints by design: `GET /trust`, `/ledger/verify`, `/anchors`, `/anchors/verify`, `/ledger/proof/{id}` expose service names, scores, entry counts, hashes and batch metadata but no personal data.
- Declaration key lookup uses the unverified `client_id` claim and then verifies the signature.
- `PseudonymMap.rebuild` reads at most 1000 users (`keycloak.py:70`).
- Ledger timestamps come from TrustTrail's own clock (`datetime.now`), not a trusted time source; the contract's `anchoredAt` is `block.timestamp`.
- All DB writes go through one global lock and one SQLite connection; throughput under load was not evaluated (only 10 concurrent releases for chain integrity).
- No per-student consent step in the running flow (taxonomy F4 suggested 0).
- Keycloak runs `start-dev` (no production hardening claimed).

---------------------------------------------------------------------------------------------------

## 9. Config files summary

- **`config/profiles.yaml`**: `order: [anonymous, pseudonym, partial, total]` + `profiles` map (4.2). Header: "Keycloak decides WHICH profile a service may get (via the profile-* client scopes assigned to it); this file decides WHAT each profile contains. TrustTrail's /release endpoint is the only place that turns a profile into attribute values."
- **`config/services.yaml`**: six invented services; per service `name`, `description`, `url`, `policy_uri`, `tos_uri`, `wants`, `tier` (base tier), `declaration{attributes, purpose, retention_days, valid_days}`, optional `scripted: true`.
  | id | name | url | wants | tier | declaration attributes | retention / valid days |
  |---|---|---|---|---|---|---|
  | library | Digital Library | http://library.localhost:8001 | pseudonym | untrusted | sub, affiliation | 30 / 30 |
  | lms | Learning System | http://lms.localhost:8002 | partial | semi_trusted | sub, affiliation, department, program, year | 180 / 30 |
  | exam | Examination Portal | http://exam.localhost:8003 | total | fully_trusted | sub, affiliation, department, program, year, name, email, roll_no | 365 / 30 |
  | overasker | Campus Deals | http://overasker.localhost:8011 | partial | semi_trusted | sub, affiliation | 30 / 30 |
  | retainer | Alumni Tracker | http://retainer.localhost:8012 (**no policy_uri**) | partial | semi_trusted | sub, affiliation, department, program, year | 30 / 30 |
  | tiercap | Career Portal | http://tiercap.localhost:8013 | pseudonym | untrusted | sub, affiliation | 30 / 30 |
  Purposes: library "Confirm you are a current student before lending e-books, and keep your loan history."; lms "Enrol you in the courses of your department, program and year."; exam "Print your name and roll number on hall tickets, and email you your results."; overasker "Check that you are a student before showing student-only discounts."; retainer "Invite you to alumni events for your department and year."; tiercap "Show internship listings open to students."
- **`config/students.yaml`** (header: "Invented students. Any resemblance to real people is accidental."): asha (Asha Kulkarni, Computer Science, B.Tech, year 2, roll TT24CS001), rohan (Rohan Deshpande, Electronics, B.Tech, 2, TT24EC014), meera (Meera Iyer, Data Science, B.Tech, 3, TT23DS007), kabir (Kabir Sethi, Computer Science, M.Tech, 1, TT25CS042), zoya (Zoya Fernandes, Electronics, B.Tech, 4, TT22EC003); emails `<username>@students.example.edu`; shared password from `STUDENT_DEMO_PASSWORD`; `affiliation` is "student" for all (set in `seed.py`).
- **`config/trust.yaml`**: tiers map, `tier_order`, `score.*`, `sync_seconds: 3` (4.7).
- **`config/anchoring.yaml`**: `interval_seconds: 300`, `max_batch_entries: 5000`, `receipt_timeout_seconds: 180`.
- **`config/declarations.yaml`**: 4.3.
- **`config/study.yaml`**: persona (asha), plain-language labels (name "Your full name", email "Your email address", roll_no "Your roll number", department "Your department", program "Your programme", year "Your year of study", service_id "An ID that only this service uses", account_id "Your university account ID (the same for every service)"), scenarios P and F (7.6), `baseline_receives`, `trusttrail_always: [service_id]`, three `likert` items.

---------------------------------------------------------------------------------------------------

## 10. "Bad services" (`scripts/bad_services.py`, `config/services.yaml`)
Three scripted clients with no web app (ports 8011-8013 appear only as URLs). Each uses Authlib `OAuth2Client` (password grant, no browser; TEST/DEMO ONLY) and signs an honest-looking declaration through `DemoService` (in-memory EC key; registers key with a client-credentials token; builds the declaration from `services.yaml`; fresh nonce each time). Then it misbehaves in exactly one observable way. Usage: `python -m scripts.bad_services <overasker|retainer|tiercap> [times]` (student `asha`).
| Id | Name | Base tier / cap | Declared | Misbehaviour (code) | Rule / refusal | Detection path |
|---|---|---|---|---|---|---|
| `overasker` | Campus Deals | semi_trusted / partial | `[sub, affiliation]` | logs in at `min(wants, current cap)` then `/release` with `["sub","affiliation","department","email"]` (`OverAsker.misbehave`, l.58-65) | rule 1 `undeclared_attribute`; 403 `attribute_not_declared` | synchronous in `/release` |
| `retainer` | Alumni Tracker | semi_trusted / partial; no `policy_uri` so score starts at 85 | `[sub, affiliation, department, program, year]` | declares `retention_until` = now + 2 s (ISO timestamp with timezone, seconds precision); releases once (OK); sleeps `keep_seconds + 1` = 3 s; requests again with the same declaration (`Retainer.misbehave`, l.68-79) | rule 2 `after_retention`; 403 `retention_passed` | synchronous in `/release` |
| `tiercap` | Career Portal | untrusted / pseudonym | `[sub, affiliation]` | asks Keycloak for `profile-total`; Keycloak refuses with `invalid_scope` (`TierCap.misbehave`, l.82-90) | rule 3 `above_tier_cap` | asynchronous: LOGIN_ERROR event poll within `sync_seconds` (3 s) |
`BadService.wanted_profile()` = lower of `wants` and the service's current public cap from `GET /trust`, so a demoted service adapts ("ordinary behaviour").
Honest services in demo/eval: `library`, `lms`, `exam` (real FastAPI apps `services/app.py` for the browser flow; script-driven in the evals: `HONEST = ["library","lms","exam"]`, `STUDENTS = asha, rohan, meera, kabir, zoya`).
Observed progression (eval): overasker and retainer semi_trusted → untrusted → blocked (stays); tiercap untrusted → blocked (stays); max profile partial → anonymous or pseudonym → anonymous. At `blocked` the cap is `anonymous` (a release is just `affiliation`, no `sub`). Further violations at the floor are still recorded in the ledger; score floors at 0.

Other demo scripts: `demo_phase1.py` (pseudonym table for 5 students x 3 services; what each service receives; tier-cap matrix read from Keycloak), `demo_phase2.py` (full request/response formats and refusal table), `demo_phase4.py` (detection table; resets), `demo_phase5.py` (anchoring delay and gas table), `demo_tamper.py` (copy mode: attacks A-F; `--live --entry N` edits one real entry's `attributes_released` to `["sub"]` by dropping triggers then restoring schema; `--restore`), `verify_anchors.py`, `verify_receipt.py`, `seed.py`.

---------------------------------------------------------------------------------------------------

## 11. Could not determine / caveats
1. The paper's actual nine features and four proposals (taxonomy) are not in the repo: all `definition_in_paper` and P1-P4 cells are TODO. The PDF in the repo root and `paper/notes/werner2017_notes.md` may hold them; not read.
2. Usability study: no data, no screenshots, no ethics determination; placeholders (names, dates) unfilled.
3. No Sepolia or public-chain run exists; all anchoring numbers come from the local Hardhat chain. Gas figures 91,659 / 77,240 / 77,268 / 361,072 and the delay table are **README only** (not in a results file; Hardhat not re-run).
4. Integration test counts (55 cases) derived by reading, not running (they need the live stack). Unit count (94) from `pytest --collect-only`.
5. Latency numbers exist in two versions (HEAD vs uncommitted working tree). README matches HEAD. Tamper/violation tables are identical in both apart from dates and random targets.
6. `config/trust.yaml` weights and thresholds are explicitly starting values, not validated.
7. Fidelity of the pairwise-sub port to Keycloak's `SHA256PairwiseSubMapper` rests on the code comment and on the integration test comparing against live Keycloak output; I did not see that test run.
8. README's ledger field table omits `rule` and `attributes_requested`; the README `/release` example omits `entry_id` that the code returns. Code is authoritative.
9. `scripts/check_browser_sso.sh` and `check_dashboard.sh` hard-code a default demo password as an argument default (value deliberately omitted here).
