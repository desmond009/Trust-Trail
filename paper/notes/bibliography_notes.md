# Bibliography notes (verified Nov. 10, 2026)

Verification methods: **Crossref** = metadata (title, authors, venue, vol/issue/pages, date) pulled from the Crossref API for the DOI; **RFC Editor** = rfc-editor.org JSON metadata; **page** = fetched the publisher/standards page or PDF and read the title page; **search** = confirmed only through web search result text (page not directly readable).
Relevance notes are based on titles/abstracts/title pages actually seen, kept deliberately short.

| key | relevance to TrustTrail | section | verified how |
|---|---|---|---|
| werner2017survey | Base survey: taxonomy of privacy strategies in cloud IdM | Background / Related / Evaluation (taxonomy) | Crossref |
| werner2015approach | IdM-with-privacy approach in cloud (attribute minimisation) | Related | Crossref |
| werner2016model | Model for IdM with privacy in cloud | Related | Crossref |
| ferdous2015dynamic | Dynamic identity federation with SAML | Related / Background | Crossref |
| pearson2011sticky | Sticky policies bind usage policy to data (compare to purpose declarations) | Related / Design | Crossref |
| chadwick2012privacy | Privacy-preserving authorisation for cloud with obligations | Related | Crossref |
| orawiwattanakul2010user | User-controlled attribute-filter release in Shibboleth | Related | Crossref |
| pfitzmann2010terminology | Terminology: pseudonymity, unlinkability, anonymity | Background | page (PDF title page read) |
| birrell2013federated | Privacy-based characterization of federated IdM | Background / Related | Crossref |
| suriadi2009usercentric | User-centric federated SSO | Related | Crossref |
| sanchez2012enhancing | Privacy and dynamic federation in consumer-cloud IdM | Related | Crossref |
| oidccore | Pairwise subject identifiers (Sec. 8), ID token claims incl. sid context | Background / Design | page (openid.net, errata set 2) |
| rfc6749 | OAuth 2.0 framework | Background | RFC Editor |
| rfc7519 | JWT claims format | Background / Design | RFC Editor |
| rfc7515 | JWS compact serialization for signed purpose declarations / receipts | Design | RFC Editor |
| rfc7517 | JWK key format for service keys | Design | RFC Editor |
| rfc7518 | JWA: ES256 / RS256 algorithms | Design | RFC Editor |
| rfc7638 | JWK thumbprint used as kid | Design | RFC Editor |
| rfc6962 | Merkle tree hashing conventions for ledger batches (CT v1) | Design / Background | RFC Editor |
| rfc9162 | CT v2.0, updated Merkle log/proof definitions | Background | RFC Editor |
| rfc8785 | JSON Canonicalization Scheme; related to (not identical with) the canonical JSON used for hashing | Design / Discussion | RFC Editor |
| nist80063c | Federation assertions guidance (pairwise identifiers, attribute minimisation); cites 63C-4 (2025) | Background / Related | page (CSRC citation metadata) |
| kantarareceipt | Consent receipt spec; analogous to TrustTrail signed receipts | Background / Design | search (Kantara wiki page returned 202 to curl; editors/date from search; page not opened) |
| w3cvc2 | Verifiable credentials data model v2.0 (W3C Rec., 15 May 2025); related credential model | Related / Discussion | page (w3.org) |
| saml2core | SAML 2.0 assertions and protocols (2005) | Background | page (PDF title page read) |
| gdpr2016 | Purpose limitation, storage limitation, accountability (Art. 5) | Background / Design / Discussion | search/known OJ citation (EUR-Lex blocked automated fetch, 202) |
| dpdp2023 | Indian DPDP Act 2023 (consent, purpose, erasure after purpose) | Background / Discussion | page (Gazette PDF text read) |
| cavoukian2011pbd | Seven foundational PbD principles | Background / Discussion | page (PDF read; Waterloo mirror because official IPC URL not reachable) |
| chaum1985security | Pseudonyms per organisation, foundational unlinkability | Related / Background | Crossref |
| camenisch2001efficient | CL anonymous credentials | Related | Crossref |
| camenisch2002idemix | Idemix design and implementation | Related | Crossref |
| paquin2013uprove | U-Prove cryptographic specification | Related | search (Microsoft Research listing; page returned 403 to curl) |
| fett2015spresso | Privacy-respecting web SSO (IdP cannot learn RP) | Related | Crossref |
| fett2016oauth | Formal analysis of OAuth 2.0 | Related / Discussion (threat model) | Crossref |
| guo2021uppresso | Untraceable/unlinkable SSO built on OIDC (MITREid Connect) | Related | arXiv abs page (authors, title); peer-reviewed venue NOT found, cited as preprint |
| hammann2020privacy | Privacy-preserving OIDC | Related | Crossref |
| kroschewski2023implicit | Privacy-preserving RP authentication in OIDC | Related | Crossref |
| mainka2017sok | Security evaluation of OIDC | Related / Discussion | Crossref |
| wang2012signing | Traffic-guided security study of deployed SSO | Related / Discussion | Crossref |
| haber1991timestamp | Hash-chained timestamping | Related / Design | Crossref |
| merkle1987signature | Merkle trees (CRYPTO '87, published 1988) | Background / Design | Crossref |
| schneier1999secure | Hash-chained secure audit logs | Related / Design | Crossref |
| crosby2009efficient | Tamper-evident log structures with auditor proofs | Related / Design | page (USENIX PDF title page read); pages omitted (not checked) |
| laurie2014certificate | CT overview, append-only Merkle logs | Related / Background | Crossref |
| ma2007forward | Forward-secure sequential aggregate authentication for logs | Related / Discussion | Crossref |
| nakamoto2008bitcoin | Blockchain timestamped hash chain | Background | page (PDF read) |
| wood2014ethereum | Ethereum yellow paper (Shanghai version, 2025 revision date on PDF) | Background / Design | page (PDF read) |
| todd2016opentimestamps | Bitcoin anchoring of Merkle-aggregated hashes | Related | page reachable (petertodd.org 200) + search for title/date |
| chainpoint | Anchoring standard (Merkle proofs to blockchains) | Related | page (title read). No individual author/date; cite as organisation web source |
| zyskind2015decentralizing | Blockchain for personal-data access control | Related | Crossref |
| azaria2016medrec | Blockchain permission management with off-chain data | Related | Crossref |
| neisse2017blockchain | Blockchain data accountability / provenance (GDPR context) | Related | Crossref |
| truong2020gdpr | Blockchain GDPR-compliant personal data management | Related | Crossref |
| muhle2018survey | SSI components survey | Related / Discussion | Crossref (real title is "A survey on essential components of a self-sovereign identity") |
| allen2016path | Ten SSI principles | Related / Discussion | page reachable (200) + search |
| josang2007survey | Trust and reputation systems survey (basis for dynamic trust score) | Related / Design | Crossref |
| utz2019uninformed | GDPR consent notice field study | Related / Discussion | Crossref |
| felt2011permissions | Apps request more permissions than needed (over-asking) | Related | Crossref |
| felt2012attention | User comprehension of permission prompts | Related / Discussion | Crossref |
| chen2014oauth | OAuth misuse in mobile apps | Related | Crossref |
| keycloakdocs | Keycloak IdP, protocol mappers | Design / Implementation | page (title read) |
| hardhatdocs | Hardhat Ethereum dev environment | Implementation | page (title read) |
| soliditydocs | Solidity language | Implementation | page (title read) |
| fastapidocs | FastAPI framework | Implementation | page (title read) |

## Dropped / unverified
- Official Ontario IPC PDF for Cavoukian "7 Foundational Principles": the known URL returns 404; a university mirror is used instead (flag if you prefer a different copy).
- UPPRESSO peer-reviewed venue: none found, so only the arXiv preprint (v3, 2025) is cited. Do not cite as IEEE TDSC or similar.
- Hammann "OIDC tracking study": no separate tracking study found; only Hammann et al. ASIA CCS 2020 is included.
- A dedicated peer-reviewed study of OAuth/SSO consent over-asking: not found; Felt et al. and Chen et al. are the closest verified proxies and are about Android permissions and OAuth in mobile apps, not SSO consent screens.
- Official Crosby and Wallach page numbers: not verified, omitted.
- DOI not found for Crosby and Wallach, Pfitzmann and Hansen, Nakamoto, Wood (none exist or none checked), so these use URLs.

## Entries to treat with caution
- kantarareceipt: confirmed only via search (editors Lizar and Turner, 20 Feb 2018); open the Kantara page once manually to confirm URL.
- paquin2013uprove: confirmed via search of the Microsoft Research listing; newer Revision 5 (2023) exists.
- gdpr2016: citation (OJ L 119, 4.5.2016, pp. 1-88) is standard but EUR-Lex could not be fetched automatically.
- w3cvc2: author given as W3C (individual editors not verified).
- wood2014ethereum: year set to 2025 because the PDF I read is the Shanghai version dated 2025-02-04; original paper is 2014.
- nist80063c: cites revision 4 (2025); the 2017 revision 3 differs.
- chainpoint, allen2016path, todd2016opentimestamps: web sources, titles confirmed but no stable archival DOI.
