# Round 1 review: Journal-Fit Reviewer

Manuscript: "TrustTrail: Accountable, Purpose-Bound Attribute Release for Privacy-Aware Federated Identity Management" (36 pp., one-column IEEEtran, about 20k words).
Read: main.tex, all of sections/00-13 and appendix, base-survey Tables 2-3 (spot-checked against the PDF).

## 1. Summary of the paper

TrustTrail is a disclosure layer placed beside an unmodified Keycloak OIDC provider. It combines per-service pairwise subject IDs (plus a custom mapper that strips `sid`), four disclosure profiles capped through Keycloak scope assignment, service-signed JWS purpose declarations, signed release receipts, a SHA-256 hash-chained ledger with Merkle roots anchored in a small Ethereum contract, and a three-rule trust score that demotes misbehaving services. The motivation is a reading of Werner et al. (2017), where accountability (2/23) and use limitation (5/23) are the least-marked characteristics. The evaluation is a single-laptop, scripted, five-student/six-service run: 3.6 ms median overhead, 6/6 tamper attacks detected, 45/45 scripted violations detected with 0 false positives, 77,268 gas per anchor. The paper is candid about several limits (no control after release, operator can omit entries, usability study not run).

## 2. Genuine strengths

- S1. Unusually honest limitations. `10-discussion.tex` ("What the operator can still do", "Linkability that remains", "Key custody") and the "Threats to validity" paragraph in `09-evaluation.tex` state real limits, e.g. "A dishonest TrustTrail could release data without writing an entry" and that the anonymous profile still carries a pairwise `sub`.
- S2. The `sid`/`session_state`/`auth_time` leak finding (`07-design`, `10-discussion` "Dependence on Keycloak internals") is a concrete, practically useful engineering observation, and the paper adds a regression check for it.
- S3. The tamper experiment (`09-evaluation` Table tamper) is well structured. It shows that the chain, receipts and anchors cover each other's gaps, and it reports the attack (F) where anchoring fails instead of hiding it.
- S4. The split between "which profile" (Keycloak scope cap) and "what it contains" (release service) is a clean, defensible design decision.
- S5. The base-survey counts I spot-checked are accurate. Accountability = 2 of 23 (Suriadi, Sanchez) matches the survey's Table 2, and Table 3's Transparency/Accountability/Use-limitation rows match. The paper states "we did not re-score the surveyed works", which is appropriate.
- S6. Writing is plain and mostly free of padding; the research questions map to evaluation subsections and are answered one by one.

## 3. Weaknesses

### JF-1 (CRITICAL): The tamper-evidence claim against the operator is evaluated only on a chain the operator controls
- Location: `00-abstract` ("edits, deletions and truncation by the operator can be detected"); `09-evaluation` RQ3 answer; `12-conclusion` last paragraph; `10-discussion` "Scale and deployment".
- Problem: All anchoring evidence comes from a local Hardhat chain with public test keys. The discussion concedes "its anchors prove nothing to outsiders", and the evaluation says "we did not run on Sepolia". Yet the abstract, RQ3 answer and conclusion state the operator-resistance as achieved ("a record that neither the services nor the operator can change without detection once it is anchored"; RQ3: "yes ... including a full rewrite and truncation by the operator"). On a local chain the operator can reset the chain, so anchors detect nothing against that adversary. Separately, the paper admits that the operator controls what enters the ledger.
- Evidence: "so its anchors prove nothing to outsiders" (10-discussion) versus "yes, for all six attacks tried, including a full rewrite and truncation by the operator" (09-evaluation).
- Fix: Qualify the abstract, RQ3 answer and conclusion ("detected, provided anchors are on a chain the operator cannot reset; demonstrated here only on a local chain"). Better, run the anchor script once on Sepolia (cheap, about 0.0001 ETH) and report real confirmation latency and the contract address. That would also make the gas/delay estimates measured rather than extrapolated.

### JF-2 (CRITICAL): Novelty is framed as a gap-filling system, but the contribution is an integration of standard parts, and the paper does not say which part is new
- Location: `01-introduction` Contributions 2-5; `04-related-work`; `03-base-paper`.
- Problem: Each building block is existing and, in the paper's own words, standard: OIDC pairwise subject type (an OIDC Core feature; Keycloak ships a pairwise mapper), Keycloak scope assignment, JWS (RFC 7515), hash-chained logs (Schneier-Kelsey), RFC 6962 Merkle hashing, and root anchoring (OpenTimestamps/Chainpoint, which the paper itself cites). The introduction lists these as five "contributions" without saying which are new beyond the combination. The one candidate genuinely new idea is the service-signed declaration plus the demotion loop, and the related work never positions it against usage-control and obligation frameworks (UCON, XACML obligations, UMA/GNAP, Shibboleth attribute-release plus eduGAIN/GÉANT Code of Conduct, Kantara receipts being the only one covered) in enough depth. The "Contributions" section also never claims novelty explicitly, but the abstract and conclusion ("addresses these gaps") imply it.
- Evidence: "Chainpoint ... anchor Merkle roots of arbitrary documents in public blockchains" and "TrustTrail ... closer to the anchoring services" (04-related-work); the system's own listed contributions are all "A design that...", "Signed purpose declarations ... based on JSON Web Signatures".
- Fix: Add one explicit paragraph "What is and is not new". State that pairwise IDs, JWS, hash chain and Merkle anchoring are reused. Name the claimed novelty precisely (e.g. binding signed purpose/retention to each release, an enforcement-feedback loop to IdP-side scope assignment, and the finding that shared `sid` defeats pairwise IDs), and say plainly that no prior system was found that does the same, with the search method. Add the missing usage-control and attribute-release-governance literature (UCON/XACML obligations, UMA, GNAP, Trillian/KSI/QLDB-style anchored ledgers, eduGAIN CoC, GDPR-oriented consent management platforms).

### JF-3 (MAJOR): The gap analysis rests on coarse binary checkmarks and an unverified reading, and then claims more than counts can support
- Location: `03-base-paper` "Reading the tables", "Weaknesses of the surveyed approaches", Table coverage; `00-abstract`.
- Problem: (a) A low checkmark count in the survey's own Table 2 shows that the surveyed authors marked few works, not that the problem is "the least covered" or that it "matters most"; no weighting or relevance argument is made. (b) Weakness 1 asserts of the two accountability papers that they "audit the system or trace data inside a trusted environment; none gives the user ... evidence ... the operator cannot later alter" -- this is a claim about what Suriadi et al. and Sánchez et al. do, but the paper only used the survey's table and text, not those papers. (c) The survey is a 2017 mapping of cloud IdM; the 23 proposals end at 2016, so "state of the art" is nine years stale; the paper bridges this with a separate Related Work, but the gap framing in the abstract ("none of the authors' four follow-up works do") treats this as the problem definition. (d) The survey's "challenges" are loosely worded, and the mapping in Table gaps is the authors' own interpretation (e.g. "Granular control ... largely solved" is asserted with one citation). (e) The Section 3 table also gives the survey's authors' own works a special status ("the four works in progress") that does not strengthen the argument for a reader outside that research group.
- Evidence: "Even where it is marked, the works audit the system or trace data inside a trusted environment" (03-base-paper); "we did not re-score the surveyed works" (same section).
- Fix: Reword the abstract to "marked for 2 of 23 proposals in the survey's own classification" and drop "least covered" as a causal justification; add a sentence on why counts are a proxy. Read the two accountability papers (and the five use-limitation ones) and state in one sentence each what they do, or soften weakness 1 to "according to the survey's description". Mark the challenge-to-requirement table explicitly as the authors' interpretation.

### JF-4 (MAJOR): Evaluation claims are partly tautological and scoped to a self-designed test bed
- Location: `00-abstract`, `09-evaluation` violation and tamper sections, RQ answers, `12-conclusion`.
- Problem: "All 45 scripted violations were detected with the correct rule" uses three bad services written by the same team to break exactly the rules the code checks; the paper concedes "a property of scripted clients ... does not estimate how often real services misbehave", but the number appears in the abstract and conclusion as a headline result. Likewise "77,268 gas regardless of batch size" is true by construction (one 32-byte root), and "100% detection" of attacks A-F is because receipts hold the entry hash by design; the expected cells were "fixed in advance by the same team". With 5 repetitions, 6 attacks and 5 students, the numbers establish functional correctness, not detection performance.
- Evidence: "the expected outcomes were fixed in advance by the same team" (09-evaluation, Threats to validity); abstract: "All six tamper attacks we tried were detected ... all 45 scripted violations were detected".
- Fix: Reword the abstract/conclusion to "functional tests: all six ... " and drop the percent-style framing. Add at least one adversarial case not designed around the rule set (e.g. a service that requests a permitted attribute under a false purpose, replays an old declaration, or two colluding services) and report what is not detected. Consider reporting the 22% overhead only with its absolute value and no-network caveat (see JF-5).

### JF-5 (MAJOR): Headline latency figure is misleading in the abstract
- Location: `00-abstract` ("a median of 3.6 ms (22%)"); `09-evaluation` latency.
- Problem: The 22% depends on a 16 ms baseline that has no browser, no network and uses the password grant, so the denominator is artificially small and the percentage is not transferable. The baseline also differs from the TrustTrail variant in token configuration (acknowledged under threats). No per-step breakdown ("we did not time these steps separately") and no concurrent-load test; the paper itself says throughput is "an open question".
- Fix: Drop the percentage from the abstract (keep "about 3.6 ms in a local deployment"), add a sentence on concurrency being untested, and, if time allows, give a per-step timing and a 10-50 client concurrent run.

### JF-6 (MAJOR): Non-repudiation and "cannot later deny" claims are weaker than stated
- Location: `01-introduction` RQ2; `09-evaluation` RQ2 answer; `10-discussion` "Key custody".
- Problem: RQ2 asks whether a service "cannot later deny what it promised", and the answer is "yes". The discussion says key registration "requires only the service's Keycloak client secret", which the Keycloak operator (who is also TrustTrail's operator) also holds, so the operator can register a key and sign a declaration on a service's behalf. Non-repudiation against the operator, and therefore against a disputing service, is not established.
- Fix: Change the RQ2 answer to "yes, against third parties, provided the service key is registered out of band; not against the operator", or add key registration bound to something the operator does not hold.

### JF-7 (MAJOR): Self-assessed taxonomy comparison is selective and mismarks partial features as coverage
- Location: `09-evaluation` Table taxonomy and its paragraph; `00-abstract`; `12-conclusion`.
- Problem: TrustTrail is compared only with the four works in progress, which by the paper's own Section 3 table have no accountability and no use-limitation marks, so the comparison is guaranteed to flatter. The 23 proposals, including the 2 accountability and 5 use-limitation works, are not in the comparison. TrustTrail marks "Accountability = checkmark" while the discussion states that the operator can omit entries and that the chain is local; "Use limitation = p" but the abstract headlines it as a gap that is addressed; "User-friendly = p" has no evaluation (the study was not run). The authors acknowledge self-assessment but do not mitigate it.
- Fix: Include the 2 and 5 relevant proposals as columns, and show the same feature-level rubric (what exactly counts as a checkmark) applied to all. Use "p" for accountability until JF-1 is resolved.

### JF-8 (MAJOR): Length and structure are out of proportion to the contribution
- Location: whole paper (36 pp., about 20k words); `02-background` (1.7k words), `05-threat-model`, `06-architecture`, `07-design` (4k words), appendix.
- Problem: A reader must wade through a textbook primer on hash chains/Merkle/JWS/OIDC (Section 2), a separate threat model (5), an architecture section (6) and a design section (7) with overlapping content (the Section 3 gap table, Section 6 and Section 7 each restate the mechanisms), before any result appears on roughly page 24. The abstract is about 375 words with seven numeric results; the contribution list contains six items, one of which is "an open implementation". For a 20-mark paper-writing criterion this hurts readability more than it helps; for a journal, this would be cut by a third.
- Fix: Merge Sections 5 and 6, cut Section 2 to a half page with pointers, move the code listings and per-endpoint detail to the appendix, shorten the abstract to about 200 words (three results), and collapse the contributions to three.

### JF-9 (MINOR): "Follow-up" framing and RQ phrasing
- Location: `03-base-paper` first line ("TrustTrail is a follow-up to the survey"); `00-abstract` ("their own tables show ... none of the authors' four follow-up works do").
- Problem: A survey from a different group (the authors are students, not Werner et al.) cannot have a "follow-up" in the usual sense; "the authors' four follow-up works" are works in progress cited inside the same survey, not subsequent publications. This invites a reader to believe subsequent peer-reviewed work was examined.
- Fix: Say "works in progress reported in the survey's Section 5" and "builds on" instead of "follow-up".

### JF-10 (MINOR): Unevaluated claims count as transparency/user-friendliness
- Location: `11-future-work` usability study; Table taxonomy marks.
- Problem: Transparency is ticked as a full checkmark on the strength of a dashboard whose usefulness to students is untested; the usability study is described at length (about 500 words including design details) but not run. Future-work text of this size reads as filler for the unrun study.
- Fix: Mark Transparency "p" until tested, and shrink the study description to a paragraph.

### JF-11 (MINOR): Related-work table "our reading" and thin coverage of competing anchored/transparent ledgers
- Location: `04-related-work` Table related.
- Problem: The right-hand column ("What it leaves open for our goals") is defined by TrustTrail's own goals, so every row ends with a gap by construction. The paper does not cite verifiable-log infrastructures that already do batch anchoring with consistency proofs (Trillian/CT-style, Guardtime KSI, QLDB) and defers consistency proofs to future work, leaving the anchoring contribution below the state of practice.
- Fix: Add one or two rows for verifiable-log systems and anchored audit logs, and justify why Merkle-root-only anchoring without consistency proofs is adequate.

### JF-12 (MINOR): Small internal wording inconsistencies
- Location: `00-abstract` and `01-introduction` ("no shared session identifier" / "pairwise IDs prevent linking") versus `10-discussion` (pairwise `sub` still present under the anonymous profile; timing linkage remains).
- Fix: Add "identifier-based" before linkability claims in the abstract and introduction.

## 4. Criterion judgements

- Originality: PARTLY_MEETS. The combination and the enforcement loop are a reasonable student-level synthesis; the paper does not isolate what is new, and every individual primitive is standard (JF-2).
- Significance: PARTLY_MEETS. The campus-IdM problem is real, and the `sid` leak and the demote-via-scope-cap idea are practically useful, but evidence is limited to a single-machine demo.
- Claim-evidence alignment: DOES_NOT_MEET as written, because the operator-resistance, non-repudiation and "gap" claims outrun the local-chain, scripted, self-assessed evidence (JF-1, JF-3, JF-4, JF-6, JF-7). It would become PARTLY_MEETS after the abstract/conclusion are qualified and one Sepolia run is added.
- Structure and clarity: PARTLY_MEETS. Clear prose and a coherent RQ-to-answer mapping, but too long and repetitive (JF-8).
- Fit to the grading criteria (paper writing + implementation/evaluation): PARTLY_MEETS to MEETS. For the paper-writing criterion, the structure and the limitations section are strong, while the overclaiming and length lose marks. For the implementation criterion, there is a working, tested system (155 tests) and five experiments with stated methods, but experiments are mostly self-validating and small-scale.

## 5. Recommendation: Major revision

The system is competently built and the paper is unusually forthright about some limitations, but the headline claims (operator-proof tamper evidence, non-repudiation, "100%" detection, the least-covered gap framing) are not supported by a local-chain, scripted, self-scored evaluation, and the novelty is stated as a combination without isolating what is new. Qualifying the claims, adding one public-testnet run and one adversarial case outside the rule set, positioning the work against usage-control and verifiable-log literature, and cutting the length by about a third would bring it to an acceptable long-form report.
