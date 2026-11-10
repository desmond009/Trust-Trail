# Notes on the base paper

J. Werner, C. M. Westphall, C. B. Westphall, "Cloud identity management: A survey on privacy strategies,"
Computer Networks 122 (2017) 29–42, doi:10.1016/j.comnet.2017.04.030. (PDF in repo root.)

## What the survey does
- Surveys privacy in cloud IdM. Systematic mapping (Kitchenham-style, ref [51]): keywords "Identity Management, IDM,
  Privacy, Cloud Computing, Cloud"; 198 papers found, then filtered by title/abstract inclusion criteria.
- Three research questions (Sec. 3.1): which IdM model ensures privacy in cloud; best techniques for lack of privacy
  control in interactions; how federation partners should agree on privacy for authn/authz.
- Sec. 2.3: privacy properties from Birrell & Schneider [42]: undetectability, unlinkability, confidentiality.
- Proposes a taxonomy (Fig. 3) of 9 privacy characteristics, each with two mechanisms:
  - Transparency: advertence, consciousness
  - Controllability: selection, consent
  - Minimization: control, participation
  - Accountability: traceability, policies ("auditing and tracking actions, in accordance with legal requirements...
    identify misuse and privacy breaches... enabling audit actions")
  - Data quality: validation, confidence
  - Use limitation: obligations, policies ("only authorized entities should have access... policies and obligations.
    A policy... can represent the reason or intention for using the data. An obligation is a directive that must be
    carried out before or after access")
  - User-friendly: with add-ons, without add-ons (UI to "check what data was released under what conditions, and to whom")
  - Trust: reputation, risk
  - Obfuscation: anonymity, pseudonym
- Fig. 4 maps features to properties (confidentiality / undetectability / unlinkability).
- Table 1: EU projects (PRIME, PrimeLife, ABC4Trust, GÉANT, PRISMACLOUD, CREDENTIAL) vs characteristics.
  Accountability: only GÉANT/PRISMACLOUD/CREDENTIAL list "traceability". Use limitation: only PrimeLife (policies) and
  ABC4Trust (obligations).
- Table 2: 23 proposals 2009–2016 vs characteristics. Accountability marked only for Suriadi 2009 [67] and
  Sanchez 2012 [9]. Use limitation: Mowbray, Suriadi, Pearson, Sanchez, Faraji (5 of 23).
  Trust: Celesti, Sanchez, Chadwick, Ahmad, Ferdous (5).
- Survey's own conclusion (Sec. 3.4 end): "these related works do not present a complete framework that provides
  privacy mechanisms in IdM systems, meeting the dynamic characteristics of federations in the cloud."
- Notable details:
  - Ferdous & Poet [11]: trust levels in dynamic federations: fully trusted / semi-trusted / untrusted.
    (TrustTrail's tier names follow this.)
  - Sticky policies [8,68]: "does not make clear the means to ensure the effective implementation of sticky policies
    after receiving data" (about [68]).
  - Mowbray [66]: "does not provide details and does not validate the proposal".
  - [65]: "mathematical and logical evidences, without a practical implementation".
  - [29]: "does not make clear how to implement it".
  - [75]: user-defined dissemination policies "can cause problems, since the majority of users do not have sufficient
    knowledge about policy creation and management".

## Challenges / directions (Sec. 4, Fig. 5)
1. 4.1 Reliability assessment: evaluate trust among entities; reputation of providers [8,9]; risk metrics [80].
2. 4.2 Agreement of privacy options: prior agreement of privacy features between IdP and SP; not static.
3. 4.3 Definition of interaction profiles: standard profiles anonymous, pseudonym, partial attributes, total
   attributes (from [6]); users disseminate least information needed.
4. 4.4 Grained control over dissemination: release individual attributes per context.
5. 4.5 Ensure the implementation of policies: "It is essential that the application of different privacy policies
   [28] be guaranteed in an automated way"; sticky policies; compliance assessment is "a key challenge".

## Authors' own works in progress (Sec. 5, Table 3)
- Weingärtner [83]: users encrypt PII before sending to IdP; dissemination page with reputation warning (Fig. 6).
- Werner [6]: four OIDC scopes: Anonymous, Pseudonym, Partial Attributes, Total Attributes (Fig. 7 JSON).
- Lucas/Bodnar [24]: dynamic federation via OIDC dynamic client registration.
- Werner [28]: privacy model; dissemination screen with access scopes + warning on provider trust (Fig. 9).
- Table 3: across all four works, Accountability, Use limitation are EMPTY; Data quality only [83];
  User-friendly only "partial"; Trust only [83],[28]; Obfuscation only [28]; Minimization only [28].

## Gaps TrustTrail targets (our argument)
1. Accountability is the least-covered characteristic (2/23 proposals in Table 2; none of the authors' 4 works).
   TrustTrail: hash-chained ledger + signed receipts + public Merkle anchoring.
2. Use limitation: declared purpose and retention are not bound to releases in the authors' works. TrustTrail:
   signed purpose declarations (purpose, attributes, retention_until) checked on every release.
3. Ensuring policy implementation (4.5) is called key but left open; sticky policies lack enforcement evidence.
   TrustTrail: enforces at the release point and produces non-repudiable evidence; honest limit: cannot enforce
   deletion after data leaves.
4. Trust (4.1) is static reputation in prior works. TrustTrail: trust score computed from observed violations,
   automatically lowering the tier cap (Ferdous-style tiers become dynamic).
5. Profiles (4.3) from [6] exist as OIDC scopes but nothing stops an SP from asking above its level or linking
   users across SPs. TrustTrail: tier caps enforced by Keycloak scope assignment + pairwise sub + sid stripping.
6. Many proposals lack implementation/validation (noted by the survey itself). TrustTrail: working implementation on
   a current IdP (Keycloak 26) plus quantitative evaluation.
