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
| Local chain (Hardhat) | http://localhost:8545 (JSON-RPC) |
| Digital Library | http://library.localhost:8001 |
| Learning System | http://lms.localhost:8002 |
| Examination Portal | http://exam.localhost:8003 |

`docker compose up` also starts a local Hardhat chain and deploys the anchor contract
(`chain-deploy`), which writes `chain/deployments/localhost.json`.

The first build compiles the custom Keycloak mapper with Maven inside Docker (a few minutes,
needs internet). TrustTrail and service code is mounted into the containers, so edits to
scripts and tests apply without rebuilding; restart a container after changing app code.

Students: `asha`, `rohan`, `meera`, `kabir`, `zoya`, password from `STUDENT_DEMO_PASSWORD`.

**Upgrading from an earlier phase:** Phase 4 changed the ledger entry format, so old demo data
won't verify. Reset with `docker compose down -v`, then run the three commands above again.
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
| `retention_passed` | 403 | release after the promised deletion time: **violation rule 2** |
| `attribute_not_declared` | 403 | asks for an attribute the purpose doesn't cover: **violation rule 1** |
| `attribute_above_tier_cap` | 403 | asks for an attribute above the service's tier cap: **violation rule 3** |
| `attribute_above_profile` | 403 | asks for more than the granted profile, but within its agreement (not a violation) |

Since Phase 4, the three rule-breaking refusals also return `"violation": {"rule": ..., "entry_id": ...}`.

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
the same transaction. Refused requests never write a release; since Phase 4, the three
rule-breaking refusals write a `violation` entry instead.

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

## Phase 4: violations, trust score and tier caps

The loop: **signed promise → ledger record → violation detected → trust lowered → less data released.**

### The three violation rules (only what TrustTrail can see)

| Rule | Detected where | Refusal code |
|---|---|---|
| 1 · `undeclared_attribute`: asks for an attribute its signed declaration doesn't cover | `/release` | `attribute_not_declared` |
| 2 · `after_retention`: asks again, under a declaration whose `retention_until` has passed | `/release` | `retention_passed` |
| 3 · `above_tier_cap`: asks for more than its tier cap allows | `/release` (attributes), **and Keycloak login** (profile scope) | `attribute_above_tier_cap` / Keycloak `invalid_scope` |

Each rule break is written to the ledger as a `violation` entry (nothing released;
`attributes_requested` shows what was asked for) and returned to the service in the refusal.
Rule 3 at login is refused by Keycloak itself, because the scope isn't assigned. TrustTrail learns of it
by reading Keycloak's `LOGIN_ERROR` events ("Invalid scopes: … profile-total") every
`sync_seconds`. Events are switched on for that event type only and kept for one day.

**"Tier cap" means the cap from the service's agreement** (its base tier in
`config/services.yaml`). A demoted service that still asks for what its agreement allowed is
refused, but not counted again; otherwise one violation would snowball into automatic blocking.
`retention_until` may be a date (end of that day, UTC) or a timestamp with a timezone; the
retention violator uses a timestamp a few seconds ahead so the demo doesn't wait a day.

### Score and tiers (`config/trust.yaml`; all values are starting points to tune)

```
score = 100 − 15 (no privacy policy URL) − 10 (registration metadata incomplete) − 25 × violations
tier  = base tier, moved down one step for every full 25 points below 100; floor: blocked
```
- **Inputs:** privacy policy declared (Keycloak client `policyUri`); registration metadata
  complete (`name`, `description`, `rootUrl`, `tosUri`); violations in the ledger from the last
  90 days, after the most recent trust reset.
- **Tiers and caps:** fully_trusted → total, semi_trusted → partial, untrusted → pseudonym,
  blocked → anonymous. With these numbers, one violation drops exactly one tier.
- **Enforcement:** TrustTrail adds or removes the `profile-*` optional client scopes on the client
  through the Admin REST API, so **Keycloak itself** refuses higher profiles from then on.
  `/release` also applies the current cap to tokens issued before the demotion. A background
  sync re-applies every cap every few seconds, so re-seeding Keycloak can't silently undo a
  demotion.
- **Reset:** `POST /trust/{service}/reset` (admin token) writes a `trust_reset` entry. Earlier
  violations stay in the ledger but stop counting, so restoring a service is itself auditable.

| Endpoint | |
|---|---|
| `GET /trust` | public: score, inputs, tier and cap for every service |
| `POST /trust/sync` | admin: read Keycloak events and re-apply caps now |
| `POST /trust/{service}/reset` | admin: restore after review; body `{"reason": "..."}` |

Admin endpoints need `Authorization: Bearer $TRUSTTRAIL_ADMIN_TOKEN`. TrustTrail's Keycloak
service account now also has `view-events` and `manage-clients`.

### Bad services

Three scripted clients in `config/services.yaml` (no web app). Each uses Authlib's ordinary
OAuth2 client and signs an honest-looking declaration, then misbehaves in one way:

| Service | Base tier | Misbehaviour |
|---|---|---|
| Campus Deals (`overasker`) | semi_trusted | declares `[sub, affiliation]`, then asks for department and email |
| Alumni Tracker (`retainer`) | semi_trusted, **no privacy policy** (score starts at 85) | promises deletion in 2 s, comes back after |
| Career Portal (`tiercap`) | untrusted | asks Keycloak for `profile-total` |

```bash
docker compose exec trusttrail python -m scripts.bad_services overasker 3   # misbehave 3 times
curl localhost:8000/trust                                                   # watch score, tier, cap
docker compose exec trusttrail python -m scripts.demo_phase4               # detection table below
```
Students see refused requests about them on the dashboard as red rows.

### Detection counts (from `demo_phase4`, 5 attempts each)

| Service | Misbehaviour | Rule | Attempts | Detected | Missed | Score | Tier after each attempt | Max profile |
|---|---|---|---|---|---|---|---|---|
| Campus Deals | asks for attributes its declaration doesn't cover | 1 | 5 | 5 | 0 | 100 → 0 | semi_trusted → untrusted → blocked → blocked → blocked → blocked | partial → anonymous |
| Alumni Tracker | requests again after its promised deletion time | 2 | 5 | 5 | 0 | 85 → 0 | semi_trusted → untrusted → blocked → blocked → blocked → blocked | partial → anonymous |
| Career Portal | asks Keycloak for a profile above its tier cap | 3 | 5 | 5 | 0 | 100 → 0 | untrusted → blocked → blocked → blocked → blocked → blocked | pseudonym → anonymous |

| Honest services | Releases | Violations (false positives) | Tier changes |
|---|---|---|---|
| Digital Library, Learning System, Examination Portal | 30 | 0 | 0 |

These are scripted clients: the counts show the rules fire as designed. They don't measure
how often real services misbehave or how often the rules would miss a subtler misuse.

### Tests

- `tests/test_trust.py` (unit): each score input, one tier per violation, the score floor, the
  tier floor, and caps.
- `tests/test_release.py`: which refusals are violations (rules 1 and 3), and which aren't
  (above the granted profile; above a lowered cap).
- `tests/test_declarations.py`: timestamp retention and rule 2.
- `tests/test_ledger.py`: violations count only after the latest reset.
- `tests/test_phase4_integration.py`, for each bad service: the violation is caught with the
  right rule, the score drops by one step, the tier and maximum profile drop by one, the scope
  is removed in Keycloak, and Keycloak refuses the old profile. Also covered: the cascade down
  to anonymous (where a release is just `affiliation`), no double counting after demotion, old
  tokens capped, zero violations from honest traffic, reset, and admin auth.
- `tests/conftest.py` resets trust before each integration test (recorded), so tests that
  break rules on purpose don't leak into each other.

## Phase 5: blockchain anchoring

Records stay off-chain; fingerprints are anchored on-chain. Every `interval_seconds` (300 by
default, `config/anchoring.yaml` or `ANCHOR_INTERVAL_SECONDS`), TrustTrail takes the ledger
entries added since the last anchor (releases, violations and resets alike). It builds a Merkle
tree over their entry hashes and stores the root in the `TrustTrailAnchor` contract. No
transaction is sent when nothing is new. **Only hashes go on-chain, never personal data.**

**Contract** (`chain/contracts/TrustTrailAnchor.sol`): `anchor(root, firstEntryId, lastEntryId)`,
owner-only, stores `{root, firstEntryId, lastEntryId, anchoredAt}` per batch id and emits
`Anchored`. Batches must be **contiguous from entry 1** (no gaps, no overlaps), so anyone can
see exactly which entries are anchored, and a ledger that ends early is caught. There is no
function to change or delete a batch.

**Merkle tree** (`app/merkle.py`), using RFC 6962 conventions:
`leaf = SHA-256(0x00 ‖ entry_hash)` and `node = SHA-256(0x01 ‖ left ‖ right)`. An odd node is
promoted, not duplicated. Verification recomputes each leaf from the entry's **content**, so an
edited entry whose stored hash was left alone is caught too.

**Endpoints**

| | |
|---|---|
| `GET /ledger/proof/{entry_id}` | public Merkle proof: entry hash, sibling hashes, batch, contract, chain. No other entry's content. `anchored: false` until the next batch |
| `GET /anchors` | public: batches read from the contract, plus tx hash, block and gas |
| `GET /anchors/verify` | public: recompute every anchored root from the ledger and compare with the chain |
| `POST /anchors/run` | admin: anchor now instead of waiting (demos, tests) |

**Dashboard:** Verify now also checks "matches the blockchain anchor (batch #n)", recomputing
the root from the entry and its proof and reading the root from the contract. The downloaded
receipt includes the Merkle proof. `scripts/verify_receipt.py` checks a downloaded receipt
using **only the file and the chain**, with no TrustTrail API or database:

```bash
docker compose exec -T trusttrail python -m scripts.verify_receipt - < trusttrail-receipt-12.json
# PASS  receipt signature valid
# PASS  ledger entry matches the receipt
# PASS  Merkle proof computed
# PASS  on-chain root matches          batch #6 at 0x5FbDB231… on chain 31337
```

**Scripts**

```bash
docker compose exec trusttrail python -m scripts.verify_anchors   # every batch: on-chain root vs root recomputed from the ledger
docker compose exec trusttrail python -m scripts.demo_phase5      # delay entry -> anchor, gas per anchor (table)
docker compose exec trusttrail python -m scripts.demo_tamper      # now with a "Blockchain anchor" column
docker compose run --rm chain-deploy npx hardhat test             # contract tests (Hardhat 3, mocha + ethers)
```

### Measurements (local Hardhat chain)

`demo_phase5 --batches 3 --interval 12` (a release about every 2 s):

| Batch | Entries | Gas used | Gas per entry | Delay min (s) | Delay median (s) | Delay max (s) | Tx confirmed in (s) |
|---|---|---|---|---|---|---|---|
| 13 | 6 | 77244 | 12874 | 1.1 | 7.3 | 12.1 | 0.03 |
| 14 | 6 | 77244 | 12874 | 1.4 | 6.4 | 12.2 | 0.05 |
| 15 | 6 | 77244 | 12874 | 1.1 | 7.2 | 12.9 | 0.03 |

Over 18 entries: median delay 6.8 s, p95 12.2 s, max 12.9 s. Delay is measured from the entry's
time to when the anchor transaction was confirmed, both on the same clock. Hardhat's block
timestamps run a few seconds ahead after many quick blocks (each block must be at least 1 s
after the previous one), so they are not used for timing.

- **Gas per anchor:** 91,659 for the first batch on a new contract (it initialises storage),
  then about 77,240 for every later one, **whatever the batch size**. The contract test anchors
  a 100,000-entry range for 77,268. Deployment costs 361,072 gas.
- **Delay** from an entry to its anchor is about half the interval on average and at most one
  interval plus block time. With the default 300 s that means a median of about 150 s and a
  worst case of about 300 s plus ~12 s on Sepolia. Run `demo_phase5` with your own interval
  to measure it.
- **Cost on a public chain** = gas × gas price per *batch*, not per entry. Example: 77,240 gas
  at 1 gwei = 0.000077 ETH per anchor; a busy day at a 5-minute interval (288 anchors) is about
  0.022 ETH. Gas prices vary; quiet periods send no transactions.

Tamper demo with anchoring (all entries up to #133 anchored, #134 made afterwards):

| Attack | Chain check | Student receipts | Blockchain anchor |
|---|---|---|---|
| A. change an entry, leave its hash | detected | 1 fails | **detected** |
| B. change an entry, recompute its hash | detected | 1 fails | **detected** |
| C. delete an entry | detected | 1 fails | **detected** |
| D. change an entry, recompute every hash after it | not detected | 39 fail | **detected** |
| E. cut off the tail | not detected | 2 fail | **detected** |
| F. change the entry made after the last anchor | not detected | 1 fails | not detected |

F is the anchoring window: an entry is protected by the anchor only once its batch is mined.

### Tests

- **Contract** (`chain/test/TrustTrailAnchor.ts`, 6 tests): stores and emits; contiguity (gap,
  overlap, wrong start); empty range; owner-only; no function can change a batch; gas doesn't
  grow with batch size.
- **`tests/test_merkle.py`**: proofs verify for every leaf at sizes 1–33; a tampered leaf or
  sibling fails; leaf and node hashes are domain-separated; duplicating the last leaf changes
  the root; an empty batch is rejected.
- **`tests/test_anchoring.py`**: a full rewrite, an edit that leaves the stored hash alone, and
  truncation are all caught; only the affected batch fails.
- **`tests/test_phase5_integration.py`** (local chain): batches are contiguous and cover the
  ledger; nothing new means no transaction; new entries stay pending until the next batch; a
  proof reaches the on-chain root and reveals only hashes; the whole ledger verifies; the
  standalone receipt check passes and catches an edited entry; admin auth.
- **`scripts/check_dashboard.sh`** now also checks the dashboard's blockchain verification and
  runs `verify_receipt` on a receipt downloaded through the dashboard.

### Local chain lifecycle

The local Hardhat chain is in memory. `chain-deploy` reuses the existing contract if it's still
on the chain, and deploys a new one only on a fresh chain (for example after `docker compose
down` or restarting `chain`). TrustTrail then anchors from entry 1 again into the new contract;
proofs show "pending" until it has. On Sepolia the contract and its history persist.

### Switching to Sepolia

You need a Sepolia RPC URL (e.g. from Alchemy or Infura) and a key holding some Sepolia ETH
(faucets often require a small mainnet balance). The same key deploys the contract and anchors
(it is the contract owner). Keep both in `.env`, never in the repo.

```bash
# 1. Deploy once; writes chain/deployments/sepolia.json (public info, safe to commit)
docker compose run --rm -e SEPOLIA_RPC_URL="https://..." -e SEPOLIA_PRIVATE_KEY="0x..." \
  chain-deploy npx hardhat run scripts/deploy.ts --network sepolia

# 2. In .env:
#    ANCHOR_NETWORK=sepolia
#    CHAIN_RPC_URL=https://...        (same RPC URL)
#    ANCHOR_PRIVATE_KEY=0x...         (same key as the deployer)
# 3. Restart TrustTrail
docker compose up -d trusttrail
curl localhost:8000/anchors          # "network": "sepolia"
```
Then check the contract and anchor transactions on a Sepolia block explorer. I rehearsed
this procedure (steps 1–3, with `--network sepolia`, a separate key and `ANCHOR_NETWORK=sepolia`)
against the local chain; a real Sepolia run still needs your RPC URL and funded key.

## Phase 6: evaluation harness

Everything below runs in the `trusttrail` container and writes to `trusttrail/eval/results/`
(Markdown tables ready for the report, plus raw CSVs).

```bash
docker compose exec trusttrail sh eval/run_all.sh     # (a), (b), (c) in one go (about 3 minutes)
```

### (a) Latency: `python -m eval.bench_latency [--runs 200]`

Compares a plain OIDC login (`bench-baseline`: an ordinary Keycloak client that receives
every attribute in its ID token) with a TrustTrail login (LMS token plus `POST /release`, which
includes the ledger entry and signed receipt). It uses 200 runs each, in random interleaved order
after a warm-up, and reports median and p95.

| Variant | Runs | Median (ms) | p95 (ms) | Mean (ms) |
|---|---|---|---|---|
| Plain OIDC login (no privacy layer) | 200 | 17.1 | 19.1 | 17.4 |
| TrustTrail login + release (total) | 200 | 21.2 | 24.7 | 21.6 |
| of which: TrustTrail `/release` | 200 | 4.2 | 5.8 | 4.4 |

Overhead: median **+4.0 ms**, p95 **+5.6 ms** (an earlier run gave +3.4 / +4.5 ms; one laptop, all containers local, password grant;
a browser login adds the same redirects to both). Anchoring runs in the background and is not
on the login path. Each TrustTrail run is a real release, so the benchmark adds ledger entries.

### (b) Tamper and violation tests: `python -m eval.tamper_test`, `python -m eval.violation_test`

Both are repeatable and compare every run with what the design says should happen.

| Attack (5 repetitions, random target) | Hash chain | Student receipts | Blockchain anchor | Any check |
|---|---|---|---|---|
| A. change an entry, leave its hash | 5/5 | 5/5 | 5/5 | 5/5 |
| B. change an entry, recompute its hash | 5/5 | 5/5 | 5/5 | 5/5 |
| C. delete an entry | 5/5 | 5/5 | 5/5 | 5/5 |
| D. change an entry, recompute every later hash | 0/5 | 5/5 | 5/5 | 5/5 |
| E. cut off the tail of the ledger | 0/5 | 5/5 | 5/5 | 5/5 |
| F. change an entry made after the last anchor | 0/5 | 5/5 | 0/5 | 5/5 |

| Bad service (3 repetitions × 5 attempts) | Rule | Detected | Missed | Wrong rule | Tier after each attempt |
|---|---|---|---|---|---|
| Campus Deals | 1 · undeclared attribute | 15/15 | 0 | 0 | semi_trusted → untrusted → blocked (stays) |
| Alumni Tracker | 2 · after retention | 15/15 | 0 | 0 | semi_trusted → untrusted → blocked (stays) |
| Career Portal | 3 · above tier cap | 15/15 | 0 | 0 | untrusted → blocked (stays) |
| Honest services, 90 releases | | **0 false positives** | | | no tier changes |

### (c) Taxonomy scoring sheet: `trusttrail/eval/taxonomy/` and `python -m eval.plot_taxonomy`

- `taxonomy.csv` has nine feature rows and, per system, a score (`0`, `partial`, `full`) and an
  evidence column. `proposals.csv` names the authors' four proposals.
- **The feature list is a draft.** I could not verify the paper's exact nine features or the
  four proposals, so the rows are marked `DRAFT` / `TODO`: replace them with the paper's wording
  and fill in the proposals' scores from the paper.
- TrustTrail has `trusttrail_suggested` (the builder's view, with evidence pointing to tests and
  results) and an empty `trusttrail_score`. **A teammate who did not build a feature should
  score it**, and record who in `trusttrail_scored_by`.
- The chart (`results/taxonomy_chart.png` and `.svg`) draws empty cells as "not scored", never
  as 0, and hatches and stars suggested scores until a real score is entered.

### (d) Usability study: `/study`, `trusttrail/eval/usability/`, `python -m eval.analyze_study`

Each participant plays an invented student and uses both **Keycloak's default consent screen**
(real, unchanged: "Grant Access to … Email address, User profile, User roles. Yes / No") and the
**TrustTrail consent screen** (a prototype: purpose, trust level, delete-by date, per-attribute
choice with nothing pre-ticked). There are two tasks per screen:

- **P:** share department, programme and year, but not email or roll number. This is impossible
  on the all-or-nothing baseline, by design.
- **F:** share everything, which both screens can do.

Screen and task order are counterbalanced by participant code.

The app measures, per task:
- **Did they choose what they intended?** (automatic)
- **"Which of these does the service now have?"** (comprehension; scored against what the
  service really received)
- **Confidence.**

Per screen, it measures the purpose and retention questions, three 1–5 agreement items and an
optional comment. Only the participant code is stored, in `study.db`.

| File | For |
|---|---|
| `eval/usability/consent_form.md` | participants: what happens, what's recorded, voluntary, withdrawal |
| `eval/usability/data_handling.md` | participants and team: storage, access, deletion; **check whether IIIT Dharwad needs ethics approval** |
| `eval/usability/facilitator_guide.md` | team: checklist, pilot, session script, counterbalancing, reporting threats to validity |
| `eval/usability/questionnaire.md` | paper backup, plus the answer key (team only) |
| `/study/preview/P`, `/study/preview/F` | the TrustTrail screen for screenshots and piloting (records nothing) |

```bash
.venv/bin/python scripts/check_study.py                          # 2 scripted participants (P98, P99) end to end
docker compose exec trusttrail python -m eval.analyze_study     # after real sessions -> results/study.md
docker compose exec trusttrail python -m eval.analyze_study --delete-all --yes   # once the report is graded
```

`analyze_study` reports intended-choice rates per screen and task; comprehension (exact and
per-item), with a paired exact sign test; purpose and retention accuracy; Likert medians; and the
limits section. **No real study has been run yet.** Those numbers come from your sessions.

### Tests

- `tests/test_eval.py`: percentile, counterbalancing (4 equal groups; everyone does every
  screen × task), what each screen releases, intended-choice scoring, Q1 scoring, the sign test,
  and the taxonomy sheet's shape.
- `scripts/check_study.py`: plays P98 and P99 through the real Keycloak and TrustTrail screens
  and checks the analysis.

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

## Known limits (Phase 4)

- **The trust score is a heuristic.** The weights are hand-picked and were tested only with
  simulated clients. It ranks services by behaviour TrustTrail can see; it is not a measure of
  how trustworthy a service really is.
- **Only visible misbehaviour counts.** A service that stays inside its declaration but
  misuses the data afterwards, or never deletes it, gets a perfect score. Deletion cannot be proven.
- **Rule 2 only sees re-requests.** It catches a service that comes back after its deletion
  date, not one that quietly keeps what it already has.
- **Rule 3 at login depends on Keycloak's event log.** If events are switched off or expire
  before the next sync (every 3 s here, events kept for 1 day), those attempts are refused but
  not counted.
- **`manage-clients` is a broad Keycloak role.** TrustTrail could change any client, not just
  the scopes it needs to. Keycloak's fine-grained admin permissions could narrow this; not done here.
- **Resets are trusted.** Whoever holds the admin token can forgive a service. The reset is
  recorded in the ledger, but nothing stops it.
- Authlib 1.9 marks its httpx integration as deprecated in favour of `httpx2`. It works today;
  the bad-service scripts hide the notice.

## Known limits (Phase 5)

- **An anchor proves "unchanged since the anchor", not "true when written".** If TrustTrail
  records something false, anchoring faithfully preserves the false record.
- **There is an anchoring window.** Entries newer than the last batch (up to one interval) are
  protected only by the hash chain and students' receipts (tamper attack F).
- **TrustTrail decides what to anchor.** It could leave a release out of the ledger entirely
  before anchoring; anchoring can't reveal a record that was never written. Receipts held by
  students are the counter-evidence.
- **The local chain is a stand-in.** Hardhat runs in memory with public test keys; its anchors
  prove nothing to outsiders. Only a public chain such as Sepolia (or mainnet) gives evidence
  independent of TrustTrail. Sepolia is a test network and could in principle be reset.
- **Key custody:** whoever holds the anchoring key can add batches, but cannot change or remove
  existing ones.
- **Library versions:** Hardhat 3.20.0 is pinned (current is 3.21.x, about two weeks newer),
  with Solidity 0.8.28 and web3.py 7.16.0. web3.py 8.0 exists; we stayed on 7.x, whose API is
  established.

## Known limits (Phase 6)

- **The latency numbers come from one laptop** with everything local. They show the order of
  magnitude of the privacy layer's cost (a few milliseconds), not production performance or
  behaviour under load.
- **The tamper and violation tests use our own scripted attacks and clients.** They show the
  mechanisms work as designed, not how often real attackers or services would be caught.
- **The taxonomy features are a draft and the TrustTrail scores are self-assessed** until a
  teammate re-scores them; the authors' proposals are unscored until filled in from the paper.
- **The usability study is small and indicative.** It uses a convenience sample of classmates,
  a team member as facilitator, an invented persona, and a prototype screen. Students cannot yet
  deselect attributes in the running system. Task P is impossible on the baseline screen by
  design; comprehension is the fairer comparison.
