# Peer Reviewer 2 (Domain: identity protocols, OIDC/Keycloak, privacy-preserving SSO, anonymous credentials)

Material read: main.tex, sections 00-13 (focus 02, 03, 04, 05, 06, 07, 09 Table 5, 10), references.bib notes, system_facts.md, tokens.py, StripSessionIdMapper.java. Protocol facts I could not confirm from public sources are marked "unverified" and are not asserted as errors.

## 1. Summary

TrustTrail is a Keycloak 26 deployment plus a FastAPI "release service". Keycloak issues tokens with pairwise `sub` and no personal claims. Per-tier optional scopes act as profile caps. A custom mapper strips `sid`. TrustTrail then releases attribute values only under a service-signed purpose declaration, writes each release to a hash-chained ledger, issues signed receipts, demotes misbehaving services, and anchors Merkle roots on Ethereum.

From an identity-protocol viewpoint the engineering is careful and honestly scoped. The `sid` linkage finding is real and useful. Non-goals and residual linkability are mostly stated.

The weak points are these.
- The unlinkability claim (G2) is scoped to token identifiers. The system deliberately releases quasi-identifiers (department, programme, year, affiliation, name, email, roll_no) through TrustTrail, and that undercuts G2.
- The "anonymous" profile is mislabelled.
- Several OAuth/Keycloak design choices are fragile: no `aud` check, a `client_id` claim used as a discriminator, a shared client secret as the root of "non-repudiation", and the sector/salt semantics.
- Related work omits the standards and federation practice that are closest to this problem, and overstates what credential systems lack.
- The comparison table is partly unfair to credentials and consent receipts.

## 2. Genuine strengths

- **S1 (07-design, "Removing the shared session identifier"; 01-intro).** The paper shows that Keycloak's pairwise `sub` is defeated by the shared `sid`. It supplies a 72-line mapper and a curl-based browser-level check that fails when the mapper is removed. This is a concrete, reproducible practitioner contribution that the SSO-privacy literature rarely tests on a real IdP. The side effects are honestly listed: userinfo, refresh and `id_token_hint` logout break (07; 10 "Dependence on Keycloak internals").
- **S2 (07, "Pairwise pseudonyms").** The pairwise algorithm is described correctly (below), ported, and tested against live Keycloak output.
- **S3 (05-threat; 10 "Linkability that remains").** Timing and IP correlation, IdP tracking, the operator-held identity map, and the anonymous profile's pairwise `sub` are all declared. This is more candour than most system papers show.
- **S4 (04, first and second paragraphs).** The IdP-trusted campus setting is a legitimate reason to treat SPRESSO/UPPRESSO-style IdP blindness as complementary.
- **S5 (07, "Declaration format and checks").** `typ` separation, an algorithm allow-list, nonce replay protection, and a 30 s skew limit follow current JWT best practice (RFC 8725 style).
- **S6 (07-design, "Violations").** Not counting within-agreement requests as violations avoids demotion snowballing. This is a thoughtful protocol-level detail.

## 3. Weaknesses

### D-1 (CRITICAL) G2 "services cannot link a student" is undermined by the attributes TrustTrail itself releases
- **Location:** 05-threat Table 3 (G2); 07 Table 1 (profiles); 09-evaluation functional results; 10 "Linkability that remains".
- **Problem:** The paper removes identifiers from tokens, then releases `affiliation` (anonymous), plus `department, program, year` (partial), plus `name, email, roll_no` (total).
  - Two colluding services can join on (affiliation, department, program, year), or on `email`/`roll_no`/`name`. A total-tier service is a deanonymiser for every partial-tier service.
  - The threat model's A3 limits linkage to "identifiers, session values or authentication timestamps in the tokens". The discussion then lists only timing, IPs and the anonymous `sub`. Attribute-based linkage by quasi-identifiers is never discussed, and "quasi-identifier"/"k-anonymity" do not appear anywhere in the manuscript.
  - The evaluation uses five students (09). Any cohort-size analysis would show many (department, programme, year) cells with one student.
- **Evidence:** grep for quasi/k-anonym/re-identif returns nothing in sections/. Table 1 shows nested profiles.
- **Fix:**
  - Restate G2 as "no linkage through protocol-level identifiers", and say that linkage resistance holds only among pseudonym-profile services.
  - Add an attribute-linkage threat (A3b). Report, for a realistic cohort model, the size of the equivalence classes induced by each profile (cite Sweeney k-anonymity).
  - Optionally generalise the released values (for example year bands or department groups).
  - Add a collusion test: partial service plus total service join.

### D-2 (MAJOR) The "anonymous" profile is not anonymous, and the profile names borrow guarantees they do not give
- **Location:** 07 Table 1; 02 Table 2; 09 Table "taxonomy" (Obfuscation = p); 10.
- **Problem:** Keycloak always issues the pairwise `sub` in the ID and access token. The service can therefore recognise a returning student under the "anonymous" profile. By Pfitzmann-Hansen terminology (cited in 02) this is pseudonymity, with a stable pseudonym, not anonymity. The caveat appears only in the discussion and a table cell. The "anonymous" profile also has no unlinkability across sessions: the pseudonym is persistent.
- **Fix:**
  - Rename it (for example "affiliation-only" or "no-attributes") or add a session-scoped identifier for it.
  - Alternatively, issue the anonymous profile without the pairwise mapper, using a per-session random `sub`, if that is feasible in Keycloak.
  - Move the caveat into 07 Table 1 and the abstract/introduction wherever "anonymous" is used.

### D-3 (MAJOR) No audience restriction on access tokens accepted by /release
- **Location:** 07 Algorithm 1 line 1 ("verify with JWKS ... issuer, type Bearer"); 06; tokens.py `options={"verify_aud": False}`; system_facts "no `aud` check".
- **Problem:** Any realm-issued access token with `typ=Bearer`, `azp`, `sub` is accepted. TrustTrail is not an intended audience of the tokens. This is a confused-deputy and token-replay pattern. RFC 8725 §3.9 and RFC 9068 require `aud` validation. It also means:
  - tokens issued for any other resource or client in the realm are acceptable;
  - revocation and logout are ignored (acknowledged in a code comment only);
  - a service can replay a student's token to /release for its whole lifetime without the student being present.
  The stated justification ("Keycloak does not put services in `aud` by default") is an artefact of removing every default scope, including `roles`, which carries the audience-resolve mapper. It is not a Keycloak limitation.
- **Fix:** Add an Audience mapper (`included.custom.audience=trusttrail`) on the service clients, or use RFC 8707 resource indicators if the Keycloak version supports them. Validate `aud` in verify_access_token. Document the replay window (Keycloak default access-token lifetime) in the threat model, and consider sender-constraining (DPoP, RFC 9449).

### D-4 (MAJOR) Service-key registration and "non-repudiation" rest on a shared client secret and an operator-controlled registry
- **Location:** 07 "Service keys", "Receipts" ("the service cannot later deny it"); 10 "Key custody"; G4.
- **Problem:** Key registration is authenticated by the Keycloak client secret. The IdP operator/admin can reset or read that secret and register a key in any service's name. The key registry is in TrustTrail's own database and is not covered by the anchored ledger.
  - Consequently G4 ("the service cannot deny its declaration") does not hold against a service that claims the operator forged it, or against an insider (A5), and the Evaluation's six tamper cases do not include key-registry tampering.
  - The paper concedes the root-of-trust point in 10 but still states non-repudiation without qualification in 07 and in the Table 3 goals.
  - Services could instead publish a JWKS in their Keycloak client (`jwks_url`) and authenticate with `private_key_jwt`, which removes the shared secret.
- **Fix:**
  - Weaken the claim to "attributable to the key registered under the client's credentials".
  - Anchor key registrations in the ledger (or in an on-chain registry), or authenticate registration with `private_key_jwt`.
  - Add the key-registry substitution attack to the tamper evaluation.

### D-5 (MAJOR) The `client_id`-only-in-client-credentials discriminator is fragile and version-specific
- **Location:** 07 "Service keys"; 02 (client credentials); tokens.py `verify_service_token`.
- **Problem:** The check "client_id == azp, because Keycloak adds this claim only to client-credentials tokens" depends on an undocumented behaviour of Keycloak 26.8.1. I could not confirm it from public sources (unverified). RFC 9068 makes `client_id` a REQUIRED claim of all JWT access tokens. If Keycloak adopts that profile, a student's login token would pass this check and be accepted for key registration. The paper's own Keycloak-dependence discussion (10) should cover this.
- **Fix:** Discriminate by something Keycloak guarantees for service accounts (for example a service-account `sub`/`preferred_username` claim, a dedicated audience, or `private_key_jwt`). Add an integration test that fails if a user-flow token ever carries `client_id`. Cite the Keycloak documentation or source for the stated behaviour.

### D-6 (MAJOR) Fairness of Table 4 (related work comparison): credentials and consent receipts
- **Location:** 04, subsection on anonymous credentials ("nothing ties the verifier's use of the data to a declared purpose", "leaves no record that the user can later show"); table row "Anonymous credentials, SSI"; row "Consent receipts" ("not tamper-evident").
- **Problem:**
  - These are overstated. Verifier requests in the OpenID4VP/DIF Presentation Exchange ecosystem can be signed and carry a `purpose` string. A wallet can keep a log of presentations, and the verifier's signed request object is attributable evidence of the stated purpose. W3C VC presentations can be signed by the holder, which gives the verifier a non-repudiable record, and in the other direction gives the holder one of the request.
  - Kantara receipts have a signed (JWT) form, and ISO/IEC TS 27560:2023 specifies consent-record structures and lifecycle. The row should say "tamper evidence is not specified or not linked to each release", not that receipts are not tamper-evident.
  - Also "Privacy-preserving SSO... no purpose binding" is fair, but UPPRESSO targets exactly G2 (unlinkability across RPs) without trusting the IdP. The text should say plainly that on G2 these systems are strictly stronger, and TrustTrail's different adversary model is the reason for choosing otherwise.
- **Fix:** Rewrite those cells to "possible but not specified for this goal"; add an explicit G2-column comparison; cite OID4VP and ISO/IEC TS 27560.

### D-7 (MAJOR) Missing closest related work from federated identity practice and OAuth standards
- **Location:** 04 (whole); 02.
- **Problem:** The campus-federation setting has a long, directly relevant practice that is not cited.
  - SAML pairwise identifiers: `pairwise-id` and `subject-id` (OASIS Subject Identifier Attributes Profile), replacing `eduPersonTargetedID`/persistent NameID.
  - REFEDS entity categories and the GÉANT Data Protection Code of Conduct, which are the production solution to "which SP gets which attributes".
  - Shibboleth's consent/intercept modules.
  - On the OAuth side: Rich Authorization Requests (RFC 9396) and Resource Indicators (RFC 8707, which would fix D-3).
  - Transparency logging, which is much closer to the receipts and ledger than the generic tamper-evident-log cites: Pulls, Peeters and Wouters, "Distributed privacy-preserving transparency logging" (WPES 2013).
  - Pairwise identifiers in SAML mean the claimed novelty of "pairwise IDs per service in a campus federation" must be positioned, not implied.
- **Fix:** Add a "Federation practice" paragraph and a table row for SAML pairwise-id/REFEDS entity categories. See the suggested references in section 5.

### D-8 (MAJOR) Sector and salt semantics are misdescribed, and the production deployment constraint is not stated
- **Location:** 02 "Pairwise subject identifiers"; 07 "Pairwise pseudonyms".
- **Problem:**
  - The paper says each "sector of clients" receives a different `sub`. In the deployed configuration every client gets its own random salt, so the sector is irrelevant: even clients in one sector receive different values, which is not the OIDC sector semantics (OIDC Core §8.1 sector identifier shared by related clients).
  - The sector derivation requires redirect URIs to share a host unless a `sector_identifier_uri` is set. If two services are placed under one host (path-based or port-based hosting), a different salt still separates them, but the identifier would then be shared if an administrator copies the salt. This should be a stated deployment rule.
  - The identity map is computable by anyone who reads the salt (Admin API). The paper is correct that the operator holds it, but it should say that the salts are themselves the linkability key.
- **Fix:** State that sector is a Keycloak input but uniqueness comes from the salt. Document the salt-confidentiality requirement and the `*.localhost` host-naming artifact of the demo.

### D-9 (MINOR) Stripping `sid` does not remove all session-linked values
- **Location:** 07 "Removing the shared session identifier"; 10.
- **Problem:**
  - Back-channel/front-channel logout and OIDC session management generate their own `sid`/`session_state` (logout tokens carry `sid`; the session-management iframe uses `session_state` and the shared `KEYCLOAK_SESSION` cookie). The mapper only touches ID and access tokens. If a service ever configures logout URLs, `sid` returns through the logout token.
  - `iat`, `exp`, `jti` ordering, and `acr` (if the scope is added) also correlate, and `nonce`/`at_hash` do not. The paper lists timing but not logout channels.
  - The reliance on a deprecated client setting for `session_state` is acknowledged. The authorisation response `session_state` is a separate parameter from a token claim, and the text mixes them slightly.
- **Fix:** Extend the check script to a logout flow and a back-channel logout configuration; list logout channels as a linkability vector or as explicitly disabled.

### D-10 (MINOR) OAuth/OIDC background imprecisions
- **Location:** 02 "OAuth 2.0 and OpenID Connect"; "Session identifiers".
- **Problem:**
  - The authorization-code flow is described without PKCE or `state`, and TrustTrail's confidential clients' use is not stated.
  - "Keycloak adds a session identifier claim, `sid`, to the tokens it issues" is fine, but `sid` is an OIDC Front-Channel/Back-Channel Logout claim (ID token), not a Keycloak invention. Cite the logout specs.
  - Passing a student's access token to a non-resource-server (TrustTrail) is not the OAuth resource-server pattern the introduction implies. Say that explicitly.
  - Client scopes "default" vs "optional" are described correctly. Note that the `profile-*` scopes carrying no claims is the stated design (a scope used purely as a capability marker, which is sound).
- **Fix:** Light edits; add OIDC Back-Channel/Front-Channel Logout and PKCE (RFC 7636) citations.

### D-11 (MINOR) Blockchain and cost, a possible blind spot
- **Location:** 07 anchoring; 09 anchoring cost.
- **Problem:** I am not a blockchain expert. The cost figure (77,268 gas per anchor, independent of batch size) is local-chain only, and the public-chain confirmation latency and fee volatility are not measured. The paper itself notes the local chain meets neither the trust assumption nor latency. This is stated openly; I only flag that the "operator cannot rewrite the chain" assumption is not demonstrated on a public testnet.
- **Fix:** One Sepolia run with measured latency and cost.

### D-12 (MINOR) Dashboard client has no pairwise mapper, so TrustTrail sees real IDs
- **Location:** 07 "Student dashboard".
- **Problem:** This is a necessary, disclosed design choice, but it means TrustTrail is a second deanonymisation point alongside the IdP. Table 4's "operator controls the pseudonym map" row captures this, but the privacy conclusion "IdP sees all logins" omits that TrustTrail also links all services per student by construction.
- **Fix:** Name TrustTrail explicitly as a linking party in the threat model and in Table 4.

## 4. Technical-accuracy checklist

| Statement | Correct? | Note |
|---|---|---|
| OIDC has public and pairwise subject types (Sec. 8) | Yes | |
| Spec suggests hash of sector id, local account id and salt | Yes | OIDC Core §8.1 |
| Keycloak SHA-256 pairwise = UUIDv3 of 32-byte SHA-256 digest (`UUID.nameUUIDFromBytes`) | Yes (consistent with the code and integration test; I did not re-run) | MD5-based UUID of the hash; fine |
| Sector = host of redirect URIs unless sector_identifier_uri | Yes | Requires all redirect hosts equal |
| "Each sector receives a different `sub`" | Partly | In this deployment a per-client random salt separates clients regardless of sector (D-8) |
| Empty salt makes Keycloak generate a random salt per client | Plausible/consistent with the code | |
| Keycloak adds `sid` and has no setting to disable it | Plausible; not independently verified | `sid` is the session ID, as in the logout specs |
| All clients in one SSO session get the same `sid` | Yes (one session) | |
| `session_state` in authorisation response; `exclude.session.state.from.auth.response` | Yes (setting exists; deprecation in 26.8 unverified) | Distinct from token claims |
| `auth_time` comes from the `basic` scope mapper | Plausible for Keycloak 26 | |
| Optional vs default scopes; unassigned scope gives invalid_scope | Yes | |
| Scopes with no mappers only appear in `scope` | Yes | |
| Client-credentials tokens carry `client_id`, user tokens do not | Unverified, version-specific | RFC 9068 requires `client_id` in all JWT access tokens (D-5) |
| `azp` identifies the client the token was issued to | Yes | |
| No `aud` check is acceptable because Keycloak omits services in `aud` | No | Consequence of removing default scopes; violates JWT BCP (D-3) |
| Userinfo, refresh and `id_token_hint` logout fail when `sid` is null | Plausible | Session lookup is by `sid`; consistent with the paper's tests |
| RS256 for Keycloak tokens, ES256 for declarations | Yes | |
| JWK thumbprint (RFC 7638) as `kid` | Yes | |
| RFC 6962 leaf/node prefixes 0x00/0x01; odd node promoted | Yes | RFC 6962 also promotes unpaired nodes |
| Pairwise identifiers are recommended by NIST 800-63C | Yes | |
| Anonymous profile's token still has pairwise `sub` | Yes | Admitted; term is misleading (D-2) |
| Pfitzmann-Hansen and Birrell-Schneider terminology use | Yes | |
| "UPPRESSO, so far a preprint" | Yes per bibliography notes | |

## 5. Suggested references (verified to exist by search)

```yaml suggested-references
- title: "SAML V2.0 Subject Identifier Attributes Profile Version 1.0"
  authors: "OASIS Security Services (SAML) TC (J. Kemp, ed.; S. Cantor, ed.)"
  venue: "OASIS Committee Specification 01"
  year: 2019
  url: "https://docs.oasis-open.org/security/saml-subject-id-attr/v1.0/saml-subject-id-attr-v1.0.html"
- title: "k-Anonymity: A Model for Protecting Privacy"
  authors: "Latanya Sweeney"
  venue: "International Journal on Uncertainty, Fuzziness and Knowledge-Based Systems 10(5), 557-570"
  year: 2002
  url: "https://dataprivacylab.org/projects/kanonymity/index.html"
- title: "Distributed Privacy-Preserving Transparency Logging"
  authors: "Tobias Pulls, Roel Peeters, Karel Wouters"
  venue: "ACM WPES 2013, pp. 83-94"
  year: 2013
  doi: "10.1145/2517840.2517847"
- title: "JSON Web Token (JWT) Profile for OAuth 2.0 Access Tokens"
  authors: "V. Bertocci"
  venue: "RFC 9068"
  year: 2021
  url: "https://www.rfc-editor.org/rfc/rfc9068"
- title: "Resource Indicators for OAuth 2.0"
  authors: "B. Campbell, J. Bradley, H. Tschofenig"
  venue: "RFC 8707"
  year: 2020
  url: "https://www.rfc-editor.org/rfc/rfc8707"
- title: "OAuth 2.0 Rich Authorization Requests"
  authors: "T. Lodderstedt, J. Richer, B. Campbell"
  venue: "RFC 9396"
  year: 2023
  url: "https://www.rfc-editor.org/rfc/rfc9396"
- title: "OAuth 2.0 Demonstrating Proof of Possession (DPoP)"
  authors: "D. Fett, B. Campbell, J. Bradley, T. Lodderstedt, M. Jones, D. Waite"
  venue: "RFC 9449"
  year: 2023
  url: "https://www.rfc-editor.org/rfc/rfc9449"
- title: "Privacy technologies - Consent record information structure (ISO/IEC TS 27560:2023)"
  authors: "ISO/IEC"
  venue: "ISO/IEC Technical Specification"
  year: 2023
  url: "https://standict.eu/standards-repository/privacy-technologies-consent-record-information-structure-isoiec-ts-275602023"
```
Not verified in this session (check before adding): REFEDS entity categories, GÉANT Data Protection Code of Conduct, OpenID4VP, OIDC Back-Channel Logout, RFC 8725 (JWT BCP).

## 6. Criterion judgements

- **Technical correctness:** PARTLY_MEETS. The pairwise/`sid` core is right and tested. The `aud` omission, the `client_id` discriminator, the sector/salt wording, and the non-repudiation and unlinkability claims need correcting (D-1, D-3, D-4, D-5, D-8).
- **Literature coverage:** PARTLY_MEETS. The tamper-log, SSO-privacy and credential citations are good. Federation practice (SAML pairwise-id, entity categories, DP CoC), OAuth extension RFCs, transparency logging and consent-record standards are missing (D-7).
- **Fairness of comparison:** PARTLY_MEETS. The credential and consent-receipt cells overstate what those systems lack, and the G2 comparison with UPPRESSO hides that those systems are stronger on G2 (D-6).
- **Contribution to the domain:** PARTLY_MEETS. The `sid` finding and the declaration-plus-receipt design are practical. The privacy-novel claim is weakened by quasi-identifier linkage (D-1) and by the "anonymous" mislabel (D-2). The strongest contribution is the accountability layer.

## 7. Recommendation

**Major revision.**

The engineering and honesty about limits are real, and the `sid` observation is worth publishing. But the headline unlinkability/anonymity framing (G2, the "anonymous" profile, "pairwise sub and no `sid`" as obfuscation) is not supported once the attributes the system itself releases are considered. The OAuth integration also has avoidable weaknesses (no `aud`, a fragile `client_id` discriminator, a shared-secret trust root for non-repudiation). The related work leaves out the closest federation and standards work and is somewhat unfair to credentials and consent records.

Required for acceptance:
1. Re-scope G2 and add attribute-linkage analysis.
2. Fix or rename the anonymous profile.
3. Add `aud` validation, or justify the omission with a threat analysis.
4. Qualify non-repudiation, or anchor key registration.
5. Correct the Table 4 cells and add the missing related work.
