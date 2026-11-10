# Devil's Advocate report, Round 1: TrustTrail paper

Scope read: paper/main.tex, all of paper/sections/*.tex, notes/system_facts.md (header and sections 1-3), the Werner et al. 2017 PDF (Table 2 and Table 3 checked via pdftotext), and selected code (app/anchoring.py, chain/contracts, eval/ file list, eval/tamper_test.py EXPECTED). Nothing was executed. Where I could not verify a point I say so.

## 1. Strongest counter-argument

TrustTrail's headline is "accountability that even the operator cannot undo." Look at who holds every trust root. The operator runs Keycloak (which the threat model assumes honest), runs TrustTrail (which "runs its code faithfully at the time of a release"), holds the identity map, holds the receipt-signing key, holds the anchoring key (the contract's `owner` is TrustTrail's own account), can reset any service's trust, and decides what is written to the ledger at all. The paper concedes this in Section 5.2 and the non-goals ("A dishonest release service ... anchoring cannot reveal an entry that was never written"). The adversary left for the blockchain to defeat is therefore narrow: an operator who is honest at write time and malicious later, against a record that is already hash-chained, and whose every entry the student can already check against a receipt.

For that narrow adversary, the paper's own Table 9 (tamper) shows the Ethereum contract adds exactly what any externally published commitment adds: a signed (head_hash, count) posted every few minutes to a git repo, a mailing list, or an RFC 3161 timestamp authority gives the same detection of attacks D and E, at zero gas and without a chain. The paper never compares against this baseline. Its related-work section even cites OpenTimestamps and Certificate Transparency, and says these designs "assume an outside party that receives and keeps commitments", then picks the most expensive such party without arguing why.

What remains is a competent integration of existing parts: Keycloak's built-in pairwise-sub mapper and scope assignment, JWS signatures, a hash-chained SQLite table, a Merkle root, and a rule-based score. The evaluation then tests it with attacks and misbehaving services written by the same team, with outcomes fixed in advance, against a single-laptop loopback. The result "all six attacks detected, 45/45 violations detected" is closer to a unit-test pass than to evidence that accountability is achieved. The thesis that the gap in the survey is filled is supported only for the narrow, self-defined meaning of "accountable".

## 2. Issue list

### DA-1 | CRITICAL | argument
Location: 00-abstract.tex, "so that edits, deletions and truncation by the operator can be detected"; 09-evaluation.tex RQ3 "yes, for all six attacks tried, including a full rewrite and truncation by the operator".
Challenge: The paper claims protection against the operator, but the operator is the sole writer of the ledger, the sole holder of the anchoring key, the holder of the receipt-signing key, and (by the assumptions in 05-threat-model.tex) trusted not to lie "while writing an entry". The claim holds only against a post-hoc editor of a database file who is not allowed to fabricate or omit at write time.
Evidence: 05-threat-model.tex non-goal "A dishonest release service"; 10-discussion.tex "the operator still controls what enters the ledger ... The receipt is the only counter-evidence"; chain/contracts/TrustTrailAnchor.sol `address public immutable owner` and `NotOwner` check, which means only TrustTrail's own key can anchor. Receipts are signed by TrustTrail's own key (07-design.tex line 72), so an operator who can rewrite the DB can also mint receipts for the rewritten entries; only receipts the student previously downloaded are independent (the paper concedes this at the end of the tamper interpretation).
Needed: Restate the claim in the abstract and RQ3 as "post-write tampering by an actor with DB access, assuming a write-time-honest operator." Add a short threat-model matrix of operator capabilities (omit, fabricate, delay anchoring, withhold receipts, reset trust, re-key) against which mechanism detects what. Drop "by the operator" from the headline or qualify it each time.

### DA-2 | CRITICAL | argument
Location: 06-architecture.tex / 07-design.tex anchoring sections; 04-related-work.tex "These systems assume an outside party..."; 09-evaluation.tex gas table.
Challenge: The blockchain is the paper's most visible differentiator but is never justified against the obvious cheaper alternative: periodically publish a signed head hash (and count) to an append-only public location, or use an RFC 3161 TSA, or a CT-style witness set. The paper supplies no argument that a smart contract with an enforced contiguity rule detects anything that a published signed head does not.
Evidence: Related work cites OpenTimestamps, Chainpoint, Crosby-Wallach, CT, and then says in effect TrustTrail "has two such parties ... a public blockchain". Grep for "RFC 3161", "signed tree head", "witness" in the paper finds only a passing "gossip protocol" mention. Contiguity is enforced by the contract, but the same check is a one-line rule in any verifier that reads a published head log. The experiments were all run on a local Hardhat chain that the paper itself says "proves nothing to outsiders" (10-discussion.tex); Sepolia was never used (09-evaluation.tex "we did not run on Sepolia").
Needed: A design-alternatives subsection comparing (a) signed head on a public repo/mailing list, (b) RFC 3161 TSA, (c) CT-style witnesses, (d) Ethereum anchoring on dimensions that matter (who must be trusted, cost, delay, liveness, GDPR exposure, verifier effort). Either show a concrete adversary only (d) handles, or reframe the chain as one option. A run on a public testnet would at least turn the cost estimates into measurements.

### DA-3 | MAJOR | evidence
Location: 09-evaluation.tex Table (tamper), "every attack was detected by at least one check in all five repetitions"; "Receipts caught all six".
Challenge: The tamper experiment is close to tautological. The attacks were written by the team, deterministically applied, and the expected outcome table was fixed beforehand (eval/tamper_test.py `EXPECTED = {attack: (chain, receipts, anchor)}`; "every cell matched the outcome the design predicts"). Five repetitions of a deterministic attack with a random target add no statistical content; 5/5 is the only possible outcome of a correct implementation. The receipts column is true by construction: the harness records the hash of every entry in every stored receipt, then any change to any entry mismatches.
Evidence: The paper's own validity paragraph: "the expected outcomes were fixed in advance by the same team." Receipts are harvested from the harness's own database ("records the entry hashes contained in all stored receipts, which stand for the receipts that students have downloaded").
Needed: Report the attack set as a case analysis (what each check can and cannot see), not as "5/5". Add attacks that the design should fail on and show them: omission at write time, backdating, anchor withheld by operator, re-anchoring after a full-chain rewrite before the first anchor, receipts table rewritten along with ledger. Have someone outside the team propose attacks. Model receipt coverage as a fraction of students (e.g. 0%, 10%, 100%) rather than assuming all hold receipts.

### DA-4 | MAJOR | evidence
Location: 09-evaluation.tex violation table; "all 45 scripted violations were detected with the correct rule and no false positives over 90 honest releases".
Challenge: The three bad services are written to commit exactly the violations the three rules detect; 100% detection is guaranteed by construction. "Zero false positives over 90 honest releases" tests only that the team's honest scripts follow the team's rules. Moreover two of the three rules fire on requests that TrustTrail has already refused or that Keycloak already refuses (Rule 3: a login for a profile above the cap is rejected by Keycloak before any data moves). The evaluation measures that a rejected request gets logged, not that harm is prevented.
Evidence: 09-evaluation.tex states the point partly: "The 100% detection rate is a property of scripted clients that misbehave in exactly the ways the rules describe." Yet the abstract and conclusion still headline "all 45 scripted violations were detected". Rules enumerated in 05-threat-model.tex A1, A2: both are services that "ask again" or "ask for more", so the penalised behaviour is the one the system already blocks. The real harm scenario (misuse after release) is acknowledged as undetectable.
Needed: Move the caveat into the abstract or drop the 45/45 figure from it. Explain what a tier demotion buys when the refused request already released nothing. Add one experiment with a service that misbehaves in a way not anticipated by the rules (e.g. leaks data to another declared service; stays within declaration but with a false purpose) and report that TrustTrail does not detect it, as an honest negative result.

### DA-5 | MAJOR | logic
Location: 03-base-paper.tex "Reading the tables" and "Weaknesses"; 01-introduction.tex "the two characteristics that matter most for the third problem are also the least covered".
Challenge: Gap selection looks post-hoc. In Werner's Table 2 accountability is 2 of 23, but data quality and user-friendliness are also 2 of 23 (the paper's own Table 1 coverage row), and are dismissed as "less central to the problems described in Section 1", problems the authors themselves chose. Use limitation at 5/23 is no scarcer than trust (5/23). "Least covered" is also a weak proxy for "most needed": low counts can mean the survey's scope (cloud IdM privacy, 2009-2016) did not include audit research, not that the field has a gap. The survey is nine years old at the time of writing; the paper's recount did not extend to 2017-2026 work on accountability (e.g. verifiable credentials, transparency logs for identity) other than a few cites.
Evidence: Coverage table in 03-base-paper.tex (Data quality 2, User-friendly 2, Accountability 2 against 23). I checked Survey Table 2 via pdftotext; the accountability count of 2 (Suriadi, Sanchez) holds, the use-limitation count of 5 is plausible but column alignment in the extracted text is ambiguous, so I did not independently confirm it. Also: the team's own selection of "challenge 4.5, ensuring the implementation of policies" is mapped to hash-chains, but the survey's challenge is about enforcing the policy, which Section 5 admits TrustTrail does not do after release.
Needed: State the criterion for "gap" before counting. Acknowledge the three-way tie. Add a paragraph on post-2017 literature coverage and what a rescoring would show. Re-word the 4.5 mapping as "evidence about policy application at disclosure", not "ensuring implementation".

### DA-6 | MAJOR | argument
Location: 01-introduction.tex RQ1; 09-evaluation.tex "RQ1 ... yes, with standard OIDC on the service side".
Challenge: RQ1 is close to trivial. Pairwise subject identifiers are a feature of OIDC Core (section 8.1) and Keycloak ships a pairwise mapper; scope assignment as an upper bound is a standard Keycloak feature; the four profiles come from Werner's own prior work. The only new element is a seven-line Java mapper that nulls `sid`, which is a workaround for a Keycloak 26 behaviour, not a design contribution. The "RQ1 yes" is shown by a functional check on 5 students and 3 services.
Evidence: 02-background and 07-design describe the pairwise mapper as Keycloak's `oidc-sha256-pairwise-sub-mapper`; system_facts section 2.6 shows `StripSessionIdMapper.java` is 72 lines, whose body is `token.setSessionId(null)`. 10-discussion.tex concedes it depends on an SPI "that Keycloak marks as internal".
Needed: Present RQ1 as an engineering finding (the sid leak and how it was found) rather than as a research result. Quantify the linkage claim with something other than "the three identifiers differed", e.g. a linking attack by two colluding services over timestamps, which is a stated non-goal but the very attack a skeptic will run.

### DA-7 | MAJOR | logic
Location: 05-threat-model.tex A4 and G4; 07-design.tex line 74 "The declaration ... the service cannot later deny".
Challenge: A4 names two repudiation cases: denying a promise and denying having received data. Only the first is covered. TrustTrail's receipt is signed by TrustTrail, not by the service, so a service can still deny receipt; there is no service-signed acknowledgement. G4 ("TrustTrail cannot deny a release it receipted") is a statement about a party who is trusted by assumption anyway. Further, the declaration is signed by a key whose registration needs only the service's Keycloak client secret (10-discussion.tex "the client secret is the root of trust for key registration"), so a leaked client secret lets anyone register a key and sign "the service's" promise, undermining non-repudiation in the sense the abstract claims ("cannot later deny").
Evidence: 10-discussion.tex "Key custody"; 07-design.tex receipt description; table of goals G4.
Needed: Either add a service-signed acknowledgement of receipt (or drop "denies having received data" from A4), and replace "cannot later deny" with "cannot deny unless its key or secret was compromised, which registration does not detect."

### DA-8 | MAJOR | evidence
Location: 09-evaluation.tex latency section; abstract "3.6 ms (22%)".
Challenge: The 22% overhead figure is a ratio against a 16 ms loopback password-grant baseline and is therefore close to meaningless for a real login; reported relative overhead depends entirely on how fast the baseline is. The paper acknowledges that deployment adds network latency, but still puts "22%" in the abstract. The two variants differ in more than the privacy layer (different clients, mapper chain, claim mappers). No concurrency test, and a global lock plus single SQLite connection means the measured per-request cost is the best case.
Evidence: 09-evaluation.tex Threats to validity; 10-discussion.tex "Scale and deployment" ("we did not measure throughput under concurrent load"). Also the evaluation file notes two earlier runs gave 4.0 and 3.4 ms and that the README quotes 4.0 ms; the sheet (system_facts) flags that the README matches an older run. The paper cites 10 Nov 2026 numbers; fine, but the repo README says something else, so a reader cross-checking will see a conflict unless README is updated.
Needed: Drop the percentage from the abstract; give absolute added time plus the extra network round trip. Add a modest concurrency run (e.g. 10-50 parallel logins) to show where the single lock saturates. Reconcile README and paper.

### DA-9 | MAJOR | scope
Location: 07-design.tex (trust model), 10-discussion.tex "The trust model".
Challenge: The operator-controlled trust tier is described as a feedback loop that "lowers trust", but the weights are hand-picked (15, 10, 25, 25 per tier), were never tuned or validated, and the only effect, tier demotion, can be reversed by the operator with a `trust_reset`. The loop's novelty claim ("static trust ... a provider that breaks its promises does not automatically get less data") is made against the 2017 survey only; adaptive trust and reputation in federations is a large field the paper summarises in one paragraph (Jøsang survey).
Evidence: 10-discussion.tex "The trust score is a heuristic. Its weights ... were chosen by hand and tested only with scripted clients."; 04-related-work.tex trust subsection is a single paragraph.
Needed: A sensitivity check on the weights (does the ordering of services change?) and a clearer statement of what the demotion prevents in a case where the offending request was already refused. Position against adaptive-trust literature.

### DA-10 | MAJOR | framing
Location: 09-evaluation.tex Table (taxonomy) and "TrustTrail's marks are our own assessment".
Challenge: The taxonomy comparison is a self-scored table in which the only column the authors control is the one that wins. The paper admits this but still uses it as the closing evidence. It also marks TrustTrail as covering "Transparency" and "Minimization" with a tick while the usability study that would test transparency/user-friendliness was never run (11-future-work.tex "has not yet been run"; 13-backmatter "no human participants"). The comparison is against the authors' four works-in-progress, not against the stronger systems in the survey's own Table 2, so "none of the four" being zero on accountability is a weak benchmark.
Evidence: 09-evaluation.tex taxonomy table caption: "TrustTrail's marks are our self-assessment."
Needed: Replace ticks with an evidence-level scale (implemented and tested / implemented, untested / designed only); compare against Suriadi and Sanchez, the two accountability-marked proposals; and downgrade Transparency to partial until the study is run.

### DA-11 | MINOR | framing
Location: 12-conclusion.tex "a record that neither the services nor the operator can change without detection once it is anchored".
Challenge: "Once it is anchored" does heavy lifting: anchoring runs on a 300 s default and is operator-triggered; the operator controls when anchoring occurs and whether it does at all (no liveness guarantee, and nobody is watching the contract per the paper's own caveat "publish the anchor contract address so outsiders can watch it"). No monitor exists in the system.
Needed: Add the missing actor (a monitor/auditor process) to the architecture or list it as required for the claim to hold.

### DA-12 | MINOR | evidence
Location: 09-evaluation.tex anchoring section, "at 1 gwei, one anchor costs about 0.000077 ETH ... a day ... 0.022 ETH".
Challenge: The cost projection is derived by multiplication from local gas with an assumed gas price and no ETH-price or L2 discussion, while the headline cost claim ("regardless of its size") is a property of the contract design (constant storage), not an empirical finding; it follows directly from storing a 32-byte root. Also gas prices on mainnet routinely exceed 1 gwei.
Needed: Present it as a design property with a short sensitivity table on gas price, or measure on a testnet.

### DA-13 | MINOR | logic
Location: 01-introduction.tex contribution 6 vs 03-base-paper.tex gaps table "155 tests", 08-implementation.tex "94 unit tests (70 test functions)".
Challenge: Test counts are quoted three different ways ("149 Python tests and 6 contract tests", "155 tests", "94 unit tests (70 test functions)"). I did not run pytest; the sheet notes counts come from `--collect-only` and static reading, so the integration counts are unexecuted. Mixed units (tests vs functions vs parametrised cases) invite doubt.
Needed: One definition, one number, and state whether the suite was run green on the cited commit.

### DA-14 | MINOR | scope
Location: 01-introduction.tex "a typical campus SSO configuration"; Figure 1 caption.
Challenge: The motivating "problem" (every service receives the same sub and all claims) is asserted as typical but evidenced only by "the project started from a simple question". No survey of real campus deployments (e.g. eduGAIN/Shibboleth, which already supports attribute release policies and transient/persistent per-SP identifiers) is cited. SAML federations in R&E communities have used per-SP persistent NameIDs and attribute filtering for over a decade, which weakens the novelty framing of "over-release" and "linkability".
Needed: Cite evidence of how real campus IdPs are configured, or soften "typical" to "an easy default", and discuss Shibboleth/eduGAIN's attribute release as prior art in the introduction, not only deep in related work.

## 3. Ignored alternative explanations or designs

1. Signed head hash published to a public location, or an RFC 3161 timestamp authority, or CT-style witnesses, instead of a smart contract (see DA-2).
2. Service-signed receipts (the service countersigns each release), which would give two-party non-repudiation without a trusted TrustTrail key.
3. Splitting the operator role: a separate auditor holds the anchoring key or a second ledger copy, so that the party that writes the ledger is not the party that anchors it. The paper only says "would place administration with an independent office".
4. Existing attribute-release machinery in Shibboleth/SAML (per-SP attribute filters, transient identifiers), and OIDC-native alternatives (pairwise subject, claims parameter, UMA, GNAP) as baselines for RQ1.
5. Verifiable credentials / SD-JWT and selective disclosure, which would let the student rather than a central release service decide disclosure and remove the need for a trusted TrustTrail holding the identity map.
6. Student-held evidence (a wallet or an append-only personal log) as the primary mechanism rather than an optional download.
7. A reading of Table 2's low accountability count as an artifact of the survey's search scope (cloud-IdM privacy, 2009-2016), rather than a field gap.
8. For the latency result: the overhead is simply the cost of one extra service-to-service HTTP call plus an ECDSA signature; any release-gateway design would show this. It does not discriminate TrustTrail's design.

## 4. Missing stakeholder perspectives

- Services (relying parties): why would a third-party service sign declarations and accept demotion? There is no adoption incentive or cost analysis; all six services are invented and all controlled by the team.
- The university's DPO / legal office / IT administration: who runs TrustTrail and who audits the operator? The paper invokes GDPR and DPDP but never states whether signed receipts would be accepted as evidence or whether a ledger of pseudonymous release records is itself personal data under those laws.
- Students: no student has used it. The usability study is designed but not run; the paper's transparency and user-friendliness marks rest on the authors' view.
- The IdP administrator: Keycloak upgrade burden for an internal SPI, and the broad `manage-clients` role given to TrustTrail's service account.
- A regulator or auditor: how a third party would verify without the operator's cooperation (is the receipt public key discoverable? where?). I did not find this stated; it may be in 07-design.tex, but I did not locate it.

## 5. Observations that are NOT defects (hold up under challenge)

- The paper is candid about the core limit: it cannot see use after release, and says so in the abstract, introduction, non-goals, and discussion. That is a strength, not a defect.
- The survey counts for accountability (2 of 23) and the authors' four works (zero) match Werner's Tables 2 and 3 as I extracted them; the headline gap numbers are not invented.
- The layered tamper argument (chain misses full rewrites, anchors miss the post-anchor window, receipts only help holders) is correct, honestly presented, and the attack F row shows a result the design does not win.
- The evaluation reports a negative cell (attack F, anchor 0/5) and lists internal, external and construct validity threats including that the authors wrote the attacks.
- The separation of which profile (Keycloak) from what it contains (TrustTrail) is a defensible design decision with a concrete enforcement mechanism, and the design discloses the Keycloak `sid` finding with a reproducible check script.
- The anonymous profile's remaining pairwise `sub` and the timing-linkability limit are disclosed rather than hidden.
- Dates, versions, and numbers in the latency and gas tables are traceable to results files (per the fact sheet); the working-tree vs committed discrepancy is flagged in the fact sheet, so it can be fixed.
