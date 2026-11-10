# Editorial decision: round 1

Manuscript: *TrustTrail: Accountable, Purpose-Bound Attribute Release for Privacy-Aware Federated Identity Management* (paper/main.tex, 36 pages)
Panel: Journal-Fit Reviewer, R1 Methodology, R2 Identity protocols, R3 Data-protection law, Devil's Advocate. Reports in this folder.
Provenance: all five seats ran as separate subagents of the same model family in one session, each without access to the other reports. They are role-separated, not independent reviewers.

## Decision: Major revision

All five seats recommend major revision (DA gives no recommendation by design). No seat found a number in the paper that contradicts the data. The panel agrees that the system is real, well tested and honestly limited in places, and that the base-survey counts are correct. The revision is mostly about claims that are stronger than the evidence, missing comparisons, and missing legal and governance analysis. Most items need rewriting, not new experiments.

## Devil's Advocate CRITICAL issues (adjudicated)

| ID | Issue | Adjudication |
|---|---|---|
| DA-1 | "Tamper-evident even against the operator" overreaches: the operator writes the ledger and holds the anchoring and receipt keys | **Validated** (corroborated by JF-1, JF-6, D-4, P-4). The claim holds only for changes after an anchor, on a chain the operator cannot rewrite. Blocks acceptance until the abstract, RQ3 answer, Sec. 5 goal G5 and conclusion are scoped. |
| DA-2 | Ethereum anchoring never compared with cheaper alternatives (published signed head, RFC 3161 timestamping, CT-style witnesses) | **Validated in part.** The paper does need the comparison (corroborated by JF-2, JF-11). The design choice can stand if the trade-offs are argued (no trusted third party, public permissionless verification, cost). Blocks acceptance until a comparison paragraph is added. |

## Other CRITICAL findings

| ID | Issue | Synthesis |
|---|---|---|
| JF-1 | Operator-resistance evaluated only on a local chain the operator controls | Merged with DA-1. Fix by scoping claims; a Sepolia run would strengthen but is optional (needs an RPC URL and a funded test key). |
| JF-2 | Contribution is an integration of standard parts; paper never says what is new | Add an explicit "what is new / what is not" paragraph in Sec. 1 and position against usage-control and verifiable-log work. |
| D-1 | Released attributes (department, programme, year, name, roll no.) let colluding services link students without any identifier | Validated. G2 must be restated as "no linking identifiers in tokens", and attribute-based linkage (small anonymity sets) added as a limitation. |
| P-1 | The ledger and receipts are personal data (pseudonymous access records) with no retention, erasure or correction regime | Validated. Add a retention and erasure design discussion (e.g., unlinking by deleting identity-map rows, ledger retention period, why anchored roots alone reveal nothing) and state it as a limitation of the implementation. |

## Consensus issues (raised by 3 or more seats)

1. **Evaluation is conformance testing, not a detection rate** (M-1, M-2, DA-3, DA-4, JF-4). Reframe Tables XIV and XV as "behaves as designed" checks. State that the receipts column assumes every affected student kept a receipt. Say that "15/15" is 3 independent starts per service.
2. **Latency headline** (M-3, M-4, JF-5, DA-8). The 22% figure is relative to a 16 ms loopback login; present the absolute +3.6 ms, add the bootstrap 95% CI for the median difference (computed by the editor from the raw CSV: 3.4 to 3.7 ms), state the nearest-rank p95 method, and replace the "two earlier runs" sentence with what is actually in the repository.
3. **Non-repudiation is weaker than stated** (JF-6, D-4, DA-7). Key registration rests on the client secret; the registry is operator-controlled and not anchored. Scope "cannot later deny" accordingly.
4. **Gap analysis and taxonomy are selective** (JF-3, JF-7, DA-5, DA-10). Data quality and user-friendliness also score 2/23; explain why the paper targets accountability and use limitation (the problem statement, not the counts alone). Compare TrustTrail also with the two Table 2 proposals that do address accountability (Suriadi, Sánchez), and keep the self-assessment caveat.
5. **Operator governance** (P-4, DA-1, D-12). Add a short governance subsection: who runs TrustTrail, separation of duties, audit of administrator actions (resets are already in the ledger), publishing the contract address.

## Other major issues (one or two seats)

- D-2: the "anonymous" profile is pseudonymous (persistent pairwise `sub` in the ID token). Rename in text or qualify every use.
- D-3: `/release` performs no audience check on access tokens; D-5: the `client_id`-only-in-client-credentials guard depends on Keycloak behaviour. Either fix in code (audience mapper plus `aud` check; a sturdier service-token check) or document as limitations.
- D-6, D-7, JF-11: related-work table is unfair to credentials and consent receipts; missing federation practice (SAML pairwise-id, REFEDS, GÉANT Code of Conduct), OAuth standards (RFC 8707, 9068, 9396, 9449), verifiable logs, and usage control (UCON). Only add references that are verified.
- D-8: sector vs. salt semantics are misdescribed; uniqueness in the deployment comes from the per-client random salt; salts are the linkability key and must stay confidential.
- P-2, P-3, P-7: anchoring and "roots are not personal data" asserted, not argued; DPDP Act treated as GDPR-lite (roles of data fiduciary and data principal, notice, grievance redressal, minors); practicality for an Indian institute.
- P-5: the student has evidence but no remedy path; connect to grievance redressal.
- P-6: usability-study ethics plan is thin and recruits dependent classmates.
- M-5: public-chain delay and cost are model estimates; label them so.
- JF-8: length and overlap (Secs. 2, 5, 6, 7); abstract is about 330 words (limit 250).

## Reviewer claims the editor checked and does not accept

- **M-3, p95 values.** The reviewer recomputed p95 as about 20.6 / 25.7 ms. The harness uses the nearest-rank definition (`eval/common.py`), which gives 20.17 / 25.63 ms from the raw CSV, matching the table. The table is correct; the definition should be stated.
- **M-8, "results files are uncommitted".** They were committed in `c74abd3` before the review. The reviewer relied on an older note.
- **Suggested references from R2 and R3.** Several are marked unverified by the reviewers themselves. None will be added until each is verified.

## Revision roadmap

| # | Item | Source findings | Work | Needs new experiment? |
|---|---|---|---|---|
| 1 | Scope operator-resistance and non-repudiation claims (abstract, RQ3, G4/G5, conclusion) | DA-1, JF-1, JF-6, D-4, DA-7 | Writing | No (Sepolia run optional) |
| 2 | "What is new" paragraph; anchoring alternatives comparison | JF-2, DA-2, JF-11 | Writing + verified refs | No |
| 3 | Reframe tamper and violation results as conformance tests; receipts assumption; repetitions | M-1, M-2, DA-3, DA-4, JF-4 | Writing | Optional: receipt-coverage sweep |
| 4 | Latency: absolute overhead, CI, p95 method, earlier-runs sentence, loopback caveat | M-3, M-4, JF-5, DA-8 | Writing (CI already computed) | No |
| 5 | Linkage through released attributes; "anonymous" profile wording; salts | D-1, D-2, D-8, P-9 | Writing | No |
| 6 | Ledger as personal data: retention, erasure, correction; roots and erasure | P-1, P-2, P-8 | Writing | No |
| 7 | DPDP specifics, grievance path, Indian deployment | P-3, P-5, P-7 | Writing + verified legal refs | No |
| 8 | Operator governance subsection | P-4, DA-1, D-12 | Writing | No |
| 9 | Gap-analysis justification; taxonomy vs. Suriadi and Sánchez | JF-3, JF-7, DA-5, DA-10 | Writing | No |
| 10 | Token audience and service-token checks | D-3, D-5 | Code change or documented limitation | If code changes: re-run tests and latency |
| 11 | Related-work additions and fairer Table 4 | D-6, D-7 | Writing + verified refs | No |
| 12 | Ethics and usability plan | P-6 | Writing | No |
| 13 | Length, overlap, abstract to 250 words; minor accuracy items | JF-8, JF-9, JF-12, D-9, D-10, M-6 to M-10 | Editing | No |
