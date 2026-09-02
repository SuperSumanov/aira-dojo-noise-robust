# Decision Corpus reviewer artifact (anonymous preview v0)

This package is an anonymous, aggregate-only preview of the Decision Corpus
evaluation artifact. It contains no Git history, author or institution metadata,
competition data, historical card payloads, per-pair predictions, prospective
identities, labels, outcomes, prediction values, or private selection profiles.

## What this preview verifies

- the paper's provenance and sealed-evaluation schematic can be regenerated from
  code alone;
- the run-to-pair weighting figure can be regenerated from its frozen,
  outcome-blind aggregate trajectory;
- the historical Table 4A and deployment-cost values can be checked against a
  hash-bound aggregate paper extract;
- the v11 descriptor, schema dictionary, data card, graph-basis method note, and
  claim-withdrawal ledger can be inspected without opening content-bearing data;
- every packaged byte is listed in a SHA-256 manifest and checked for credential,
  host-path, and identity-shaped material.

## What this preview does not verify

This package does not recompute predictor accuracy from the 931 historical pair
rows and does not rebuild the 16,012-card v11 corpus. Those operations require
content-bearing artifacts whose public release remains under review. It also does
not expose or evaluate the sealed prospective cohort and does not demonstrate
end-to-end search utility. The distinction between exact paper regeneration and
scientific recomputation is part of the artifact contract, not a temporary caveat.

## Quick check

Use Python 3.11 or newer in a fresh virtual environment:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python tools/run_reviewer_checks.py
```

The check verifies the package manifest, regenerates both figures in a temporary
directory, compares their hashes with the frozen receipts, and validates the
aggregate Table 4A and corpus-descriptor invariants. It performs no network access,
model fitting, GPU work, or paid API call.

## License boundary

`LICENSE.code-only` and `THIRD_PARTY_LICENSES.md` describe the inherited code terms.
They are not a license or release clearance for historical card payloads, competition
data, provider outputs, or the sealed prospective cohort. No such payload is present
in this preview.
