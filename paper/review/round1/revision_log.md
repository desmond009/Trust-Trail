# Revision log: round 1 (10 November 2026)

| # | Roadmap item | What changed | Where |
|---|---|---|---|
| 1 | Scope operator-resistance and non-repudiation | Claims now cover anchored history on a public chain; anchoring and receipt keys held by TrustTrail stated as an assumption; non-repudiation rests on the client secret; Sepolia deployment added | abstract; Sec. 1 (loop paragraph, contributions); Sec. 5 (assumptions, G4, G5); Sec. 9 RQ3; Sec. 12 |
| 2 | What is new; anchoring alternatives | "What is new and what is not" paragraph; related-work paragraph on signed heads, RFC 3161 and witnesses; Discussion subsection "Is a blockchain needed?" with comparison table | Sec. 1; Sec. 4; Sec. 10 |
| 3 | Conformance framing | Tamper and violation results called conformance tests; receipts assumption footnoted and discussed; 3 independent starts per service explained | Sec. 9 intro, 9.D, 9.E, threats to validity |
| 4 | Latency | Re-run after the audience fix: +3.2 ms median, bootstrap 95% CI 3.0–3.4 ms, nearest-rank stated, sd given, relative figure explained as loopback artefact; unsupported "earlier runs" sentence removed | Sec. 9.C; abstract |
| 5 | Linkage, anonymous profile, salts | Attribute-value linkage as non-goal and discussion paragraph; anonymous profile qualified; salt semantics and confidentiality | Sec. 2; Sec. 5; Sec. 7.A; Sec. 10 |
| 6 | Ledger as personal data | New subsection: Recital 26, retention with tombstones, erasure by unlinking, correction by appending, roots and erasure, EDPB draft guidelines | Sec. 2; Sec. 6; Sec. 10 |
| 7 | DPDP specifics | Roles, Sections 2, 5, 6, 7, 8(7), 8(10), 9, 11, 12, 13 (checked against the Gazette text); deployment subsection with grievance path and minors | Sec. 2; Sec. 10 |
| 8 | Governance | "Operator power and governance" subsection | Sec. 10 |
| 9 | Gap analysis; taxonomy | Cautions on coarse counts and on data quality/user-friendly being equally rare; taxonomy table now includes Suriadi and Sánchez from survey Table 2 | Sec. 3; Sec. 9.G |
| 10 | Token audience (code) | `aud` check in TrustTrail, audience mapper in seed and migration script, two integration tests; RFC 8707/9068; client_id discriminator caveat | code; Sec. 7.B; Sec. 8 |
| 11 | Related work | Usage control (UCON); fairer rows for credentials and consent receipts | Sec. 4 |
| 12 | Ethics | Ethics committee step, non-coercive recruitment, data handling | Sec. 11; back matter |
| 13 | Length, abstract, minor | Abstract cut to 241 words; Sepolia anchoring delay and gas tables | abstract; Sec. 9.F |

New references (verified): rfc3161, rfc8707, rfc9068, park2004ucon, edpb2025blockchain.
Not done: receipt-coverage experiment (authors' decision); main-network deployment; consistency proofs; implementation of retention/erasure (described as design only).
Paper: 40 pages, compiles without errors or undefined references.
