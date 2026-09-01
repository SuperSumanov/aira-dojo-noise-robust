# Incremental archive-rejection support audit

Formal status: `INCREMENTAL_ARCHIVE_SUPPORT_ABSENT`.

The single new `ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS` event selected before readout by its
frozen registry hash has no accepted support in the exact 126-transaction prior prefix, the
seven-transaction new window, or the full 133-transaction current registry.  Each window has
`0/0/0/0` accepted archives / physical runs / eligible runs / eligible endpoints for the
anonymized target competition.

This is a one-event benchmark-audit result.  It establishes that the support gate is
non-vacuous and can identify a genuine prospective coverage gap; it does not estimate the
population frequency of such gaps, justify a task whitelist/blacklist, or measure predictor
accuracy, scaling, or search utility.

## Integrity

- Exact public commit: `ce9f50531779174c497da5eae5c66b570de92880`.
- Frozen immutable observations SHA-256: `d2ed361a557bf52dadfe9f0547e49c16ea5dc1eea42a1c78f7b354542a2a704a`.
- Result A/B SHA-256: `c95b8e0ffce0162bc65e26ce69867187f29a52184205c6c34745daa54c742080`.
- Independent verifier A/B SHA-256: `4acc607c86a2560df3036588b1d0f8898533966385551d9d5c0612bc5a64d836`.
- Formal manifest SHA-256: `65f0d2ebbf67ea5c31587b39770a70098f5acff562b4ce6bb96d0c6ff7e476de`.
- Tests: `24` focused and `1,930` full phase1 tests passed (`48` warnings).
- Producer A/B, verifier A/B, and pre/post read-only receipts are byte-identical.
- Network, forbidden-path, credential-content, and identity-schema hits are all zero.
- GPU / paid API / model fit / base update: `0/0/0/0`.

The local evidence bundle omits the large file/network trace files; the immutable remote
formal root retains them, and `SHA256SUMS` plus `MANIFEST_SHA256` bind the complete remote
artifact.  All 21 copied remote files were independently matched to their manifest entries.
