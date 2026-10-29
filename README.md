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
docker compose exec trusttrail pytest -m "not integration"   # unit: pairwise algorithm, profile filtering
docker compose exec trusttrail pytest                        # + integration against the seeded stack
```

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
