# Decision-Corpus evidence index v6

Version 6 adds `prediction_escrow_common_support` to the nine-entry v5
evidence stack. It binds the outcome-blind f109 aggregate coverage matrix and
its independent verification without releasing or aggregating pair-level
predictions.

- Source v5 normalized SHA-256: `4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627`
- Control commit: `3182b75d8b5fb2835007d575849c99977bbbaca6`
- `index.json` SHA-256: `0ee7d885dcaccab59b8294d42f1a165d3b7f1354d433303f978ae7e8c18df9d1`
- `independent_verification.json` SHA-256: `c7c23aa74e2fc92502d48b24eb2bbf6593b7ef653aa70b8066423d595e7d42b8`
- Formal root: `/research/d7/spc/yzyang4/decision-corpus-evidence-index-v6/3182b75-v2-threadcap`
- Formal `SHA256SUMS` file SHA-256: `784271eb69673e5487ab47aa571bd77a8fb967762c66d114d77aae6298940680`

The checked-in index and verification receipt are byte-identical to the formal
fresh-worktree outputs. The formal run reported 10 entries, 28 JSON artifacts,
3 bound files, 362 JSON assertions, and `991 passed, 1 skipped, 47 warnings`.
It made zero GPU/API calls and read no prospective outcome or prediction-value
aggregate.

The published commit `2735d1bfe597408a6685d93867410f450674173a` was then
checked in a second fresh worktree: focused tests were `8 passed`, the full
suite was `992 passed, 47 warnings in 71.87s`, and both checked-in JSON files
were byte-identical to independent reconstruction. The post-push `SHA256SUMS`
file SHA-256 is `f29728efbaca6370b84ba4b2690239c9a820b411591d3f72e9aeb4ffb9de5663`.

The positive claim is deliberately structural: all seven escrow arms share the
same 2,589 canonical pair identities. It is not an accuracy, effect, method
superiority, search-utility, runtime, or closure result, and the WL and
transition activation strata remain distinct.
