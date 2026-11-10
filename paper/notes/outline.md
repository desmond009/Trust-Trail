# TrustTrail paper outline (Phase 2, for approval)

Format: IEEEtran journal, one column, IEEE numbered citations. Target 13,500–15,500 words, about 32–38 pages
with figures, tables and listings. Sources: notes/system_facts.md (code), notes/werner2017_notes.md (base paper),
references.bib (verified).

Title: TrustTrail: Accountable, Purpose-Bound Attribute Release for Privacy-Aware Federated Identity Management
Authors: Vijender Yadav (23BCS132), Ansh Hardaha (23BCS016), Sourabh (23BEC055), IIIT Dharwad
Acknowledgement: guide Malay Kumar

| # | Section | Contents | Figures / tables | Words |
|---|---|---|---|---|
| – | Abstract + index terms | problem, approach, results (3.6 ms median overhead; 6/6 tamper attacks detected; 45/45 violations, 0 false positives) | – | 250 |
| 1 | Introduction | campus SSO scenario; why: over-release, cross-service linking, no record or recourse; Werner survey as starting point; research questions; 6 contributions; paper map | Fig. 1 problem scenario | 1,300 |
| 2 | Background | IdM, federation, SSO; OAuth 2.0 / OIDC (tokens, scopes, pairwise sub); JOSE (JWS/JWK/thumbprints); hash chains; Merkle trees (RFC 6962); Ethereum smart contracts; legal principles: purpose limitation, storage limitation, accountability (GDPR, India DPDP Act 2023) | Table: terms | 1,800 |
| 3 | The base paper and its gaps | Werner et al. 2017 in depth: method, 9-characteristic taxonomy, Tables 1–3, five challenges (Sec. 4); our reading of what is missing: accountability, use limitation, guaranteed policy implementation, dynamic trust, enforced profiles, missing implementations | Table: survey coverage counts per characteristic; Table: challenge → gap → TrustTrail answer | 1,700 |
| 4 | Related work | privacy-preserving SSO (SPRESSO, POIDC, UPPRESSO); anonymous credentials (Chaum, Idemix, U-Prove), SSI/VCs; sticky policies and policy-based authz; consent receipts; tamper-evident logging (Schneier–Kelsey, Crosby–Wallach, CT); blockchain for privacy/accountability (Zyskind, MedRec, GDPR blockchain); trust/reputation; usable consent; positioning table | Table: TrustTrail vs related approaches | 1,600 |
| 5 | Problem, threat model, design goals | actors (student, IdP, TrustTrail, services, operator, public verifier); adversaries (curious/greedy service, colluding services, insider editing the ledger, operator truncating history); assumptions (honest Keycloak, TLS); goals G1–G7 mapped to Werner characteristics; explicit non-goals (post-release deletion, IdP tracking, timing correlation) | Table: goals vs characteristics | 1,100 |
| 6 | System architecture | components & trust boundaries; data stores (identity_map.db vs trusttrail.db); end-to-end sequence from key registration to anchoring; design decisions (why Keycloak decides *which* profile, TrustTrail decides *what*) | Fig. 2 component diagram; Fig. 3 end-to-end sequence | 1,300 |
| 7 | Detailed design | 7.1 profiles, tier caps, pairwise pseudonyms, strip-sid mapper; 7.2 signed purpose declarations and receipts; 7.3 hash-chained ledger and dashboard; 7.4 violation rules, trust score, tier demotion; 7.5 Merkle anchoring, contract, proofs, verification | Fig. 4 release decision flow; Fig. 5 ledger chain + Merkle batch; Listings: declaration JWS, ledger entry, contract; Table: refusal codes; algorithm boxes | 3,200 |
| 8 | Implementation | stack and versions; containers; modules; API; configuration; Keycloak realm seeding; test suite (94 unit + 55 integration + 6 contract); bad services; reproducibility | Table: stack; Table: API; Table: LoC & tests | 1,100 |
| 9 | Evaluation | setup; RQ-aligned experiments: (a) latency; (b) tamper detection, 6 attacks × 5; (c) violation detection & false positives; (d) anchoring cost (gas, delay); (e) taxonomy comparison vs Werner Table 3, labelled as authors' self-assessment; threats to validity | Tables from eval/results; Fig. 6 latency; Fig. 7 taxonomy chart | 2,000 |
| 10 | Discussion & limitations | what the results mean; evidence vs enforcement; IdP can still see everything; timing correlation; single operator; key management; chain choice and cost; known limits per phase | – | 900 |
| 11 | Future work | usability study (designed, not yet run: method and hypotheses); Sepolia/public chain; selective disclosure credentials; multi-IdP federation; independent taxonomy scoring | – | 450 |
| 12 | Conclusion | – | – | 350 |
| – | Back matter | Acknowledgment (guide); AI use statement; data & code availability (all demo data invented); author contributions; conflict of interest; funding (none) | – | 300 |
| – | Appendices | A. full API reference; B. configuration files (profiles, trust, anchoring); C. reproduction commands | – | (extra pages) |

Total body ≈ 15,300 words.

## Decisions taken
- Latency: re-run `eval/run_all.sh` right before final and report that run with its date (current working tree:
  2026-11-10 run, +3.6 ms median; committed run 2026-10-30, +4.0 ms).
- Taxonomy: TrustTrail column = authors' self-assessment, clearly labelled. Comparison columns use Werner's
  own published Table 3 marks for their four works, which is verifiable data, not our scoring.
- Usability study: future work only, no results claimed.
- Gas figures: 91,659 (first anchor) and 77,268 (later anchor of 100,000 entries), confirmed by `npx hardhat test`
  run on 2026-11-10.
