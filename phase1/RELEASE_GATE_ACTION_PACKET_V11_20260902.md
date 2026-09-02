# Decision Corpus v11 release-gate action packet

> Status: `INTERNAL_REVIEW_PACKET_NOT_LEGAL_ADVICE_NOT_RELEASE_CLEARANCE`
>
> Date: 2026-09-02. This packet routes already-frozen evidence to the people who
> can close the remaining gates. It does not rescan payloads, interpret law, or
> upgrade any `PARTIAL`, `BLOCKED`, `SEALED`, or `STRUCTURE_ONLY` state.

## 1. Decision in one page

The historical v11 release scope is 16,012 cards across 25 tasks. The current
machine-audited content rule partitions those cards into 15,174
`CONTENT_REVIEW_ELIGIBLE` cards and 838 `STRUCTURE_ONLY` cards. Neither class is
public-release cleared. `CONTENT_REVIEW_ELIGIBLE` means only that the card may
enter private content/legal review; `STRUCTURE_ONLY` is the maximum payload class
currently permitted by the frozen content rule for those cards, not a legal or
privacy clearance.

The remaining work is not another predictor experiment. It is a five-owner,
fail-closed release decision:

1. an authorized content/security reviewer adjudicates 173 matched patterns
   affecting 419 cards and obtains the two missing prepared sources covering a
   further 419 cards;
2. an institutional/legal reviewer resolves the 25-competition rule matrix and
   the permitted scope of derived code, scores, and tree metadata;
3. the provider account owners recover non-secret service-provider, account-region,
   contracting-entity, and collection-time terms evidence for five batches / 6,111
   rows, including the two Qwen batches / 44 rows;
4. the project governance owner chooses the final dataset license, notices,
   attribution, and withholding policy after those reviews;
5. the release engineer creates an immutable successor if sanitation or withholding
   changes are required, runs dual scans on that exact candidate, fills the five
   real publication fields, and produces the final postflight receipt.

Until all five streams close, the only packageable material is the paper, research
code/tooling, aggregate receipts, schema/reconstruction documentation, and other
explicitly allowed metadata, each still subject to the repository's final security
and attribution checks. Competition data remains zero-byte redistributed. Full v11
payload availability must not be promised in the paper or data card.

## 2. Frozen evidence that must not be reinterpreted

| Gate | Frozen evidence | Current status | What it does **not** prove |
|---|---:|---|---|
| Historical release scope | 16,012 cards; 25 tasks | fixed v11 scope | that any payload is cleared |
| Content-scan coverage | 23/25 tasks; 3,766,518 candidate patterns | `PARTIAL` | that the two unscanned tasks are clean |
| Content matches | 173 patterns; 419 affected cards | private review required | that a match is either benign or a leak |
| Conservative tiers | 15,174 review-eligible; 838 structure-only (419 match + 419 unscanned) | formally tiered | that either tier may be published now |
| Competition rules | 25/25 pages; templates 16 standard / 7 compact legacy / 2 custom | triaged, not legal clearance | that missing language grants permission |
| Generator model ID | 29/29 batches; 16,012/16,012 rows | complete on model-ID axis | provider, contract, or server-side version |
| Exact version-or-model | 15,905 rows; 107 boundary-ambiguous | disclosed limitation | exact server-side model for all rows |
| Provider family | 24/29 batches; 9,901/16,012 rows | five batches / 6,111 rows blocked | that model names identify the service provider |
| Final candidate security scan | no exact final candidate receipt | `PARTIAL / NOT RUN ON FINAL CANDIDATE` | that upstream scans substitute for the final scan |
| License / notices | no final decision | `BLOCKED` | compatibility of Kaggle, provider, upstream, and dataset terms |
| Croissant / RAI | 10 resources / 24,119 rows inventoried | engineering-ready; five publication fields blocked | release clearance |
| Prospective first-960 | frozen outcome-blind cohort | `SEALED` | any prospective result or release decision |
| v4/v5 byte reproducibility | original payloads absent | `PERMANENTLY UNRESOLVED` | recoverability without the original payloads |

The source receipts are enumerated in
`phase1/release_gate_action_manifest_v11_draft.json`. Counts in this packet are
bindings to those receipts, not new scientific evidence.

## 3. Candidate payload classes

### A. Code, aggregate audit, and reconstruction package

This may be prepared before the full dataset payload is cleared: benchmark code,
tests, schema dictionaries, immutable-manifest/rebuild instructions, aggregate
receipts, withdrawal records, and the paper/data card. Before publication it still
needs the exact repository credential/path scan, upstream attribution check, and a
final package manifest. This class does not include competition data, historical
card payloads, or prospective escrow/vault contents.

### B. Historical `STRUCTURE_ONLY` candidate: 838 cards

The frozen rule withholds code and stdout for every matched or unscanned card. This
is a candidate serialization class only. Legal/provider/governance review and an
exact final-candidate scan still apply; therefore its current
`public_release_cleared` value is false.

### C. Historical content-bearing candidate: 15,174 cards

These cards are eligible only for the next private review stage. They are not
declared clean, non-infringing, private-data-free, or licensed. A reviewer decision
may move cards to a sanitized/withheld successor; v11 itself must never be silently
rewritten.

### D. Prospective first-960

This class remains sealed through cohort closure and the one-time result protocol.
No release decision, label, outcome, prediction, candidate identity, or utility may
be read or inferred from this action packet.

## 4. Role-separated closure requests

| Owner role | Exact request | Acceptable closure artifact | Fail-closed outcome |
|---|---|---|---|
| Historical data curator / senior | Supply the two missing prepared sources and non-secret provenance for five unresolved provider batches; for Qwen, include collection-time account region, contracting entity, and accepted terms/version or order receipt | hash-bound source-coverage receipt plus metadata-only provenance receipt with credential scan | missing evidence remains unknown; affected rows stay withheld or blocked |
| Authorized content/security reviewer | Privately adjudicate 173 matched patterns / 419 cards without publishing raw spans or card identities | aggregate disposition receipt bound to the private manifest; no raw values in Git | no adjudication means no content-bearing release |
| Institutional/legal reviewer | Review all 25 competition rules, especially 7 compact legacy + 2 custom templates, provider-output terms, upstream terms, and proposed payload classes | dated scope decision for data/code/score/tree fields and per-batch provider disposition | no opinion is not permission; unresolved slices stay withheld |
| Project governance owner | Select final license, NOTICE, attribution, contributor/creator list, and durable withholding/versioning policy | final `LICENSE`, `NOTICE`, `licenses.json`, creator approval, and governance receipt | no global license is inferred from a subset of rows or a winner-license label |
| Release engineer | Build append-only successor if required, freeze exact resource hashes, run dual candidate scans, build/verify Croissant and RAI metadata, and publish a final postflight | immutable release manifest, two-implementation security receipts, verified JSON-LD, landing URL and content base URL | any hash drift, scan hit, placeholder, or missing decision stops publication |

No contact address is inferred in this packet. The project owner must route each row
to an authorized person.

## 5. Fail-closed execution order

1. **Private review inputs:** recover the two prepared sources and non-secret provider
   evidence; scan every supplied archive for credential-shaped material before use.
2. **Parallel reviews:** complete content/security adjudication and institutional
   competition/provider/legal review. Preserve unknowns explicitly.
3. **Disposition freeze:** choose content-bearing, sanitized, structure-only, or
   withheld status per reviewed unit. Do not overwrite v11.
4. **Immutable candidate:** build an append-only successor and freeze ordered paths,
   rows, bytes, and SHA-256 values.
5. **Exact-candidate scans:** run independent credential, cookie, PII, absolute-path,
   and competition-content checks on the precise public fields. Any hit blocks the
   candidate or creates another successor.
6. **Governance artifacts:** finalize `LICENSE`, `NOTICE`, per-task/per-batch
   `licenses.json`, attribution, creator approval, and version policy.
7. **Publication metadata:** fill real `license`, `url`, `creator`, `datePublished`,
   and `contentBaseUrl`; then run the existing Croissant/RAI builder and independent
   verifier. Nulls, placeholders, local paths, or unverified URLs fail.
8. **Final postflight:** verify every resource digest, zero-byte competition data,
   repository security receipt, legal/governance artifacts, and public landing-page
   download. Only this step may create a release-clearance receipt.

Steps 1--2 may run in parallel. Steps 3--8 are ordered; no later artifact can
retroactively clear a failed earlier gate.

## 6. What the paper can honestly submit before full payload release

The submission can already include the corpus construction method, run-clean audit
protocol, benchmark code, aggregate corpus statistics, Evidence Index, withdrawal
ledger, schema dictionary, reproducibility appendix, and the machine-audited release
plan. The availability statement must say that content-bearing historical payloads
remain under legal/privacy review and that the prospective cohort is sealed. If the
venue requires public data by a fixed date, that date becomes an external critical
path rather than evidence that the current candidate is cleared.

This packet reduces coordination risk; it is not a scientific positive result and
does not increment the Evidence Index.
