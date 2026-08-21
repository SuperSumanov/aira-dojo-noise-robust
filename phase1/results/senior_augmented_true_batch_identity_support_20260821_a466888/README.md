# Senior augmented true-batch identity/support S0 — formal decision

Status: `IDENTITY_UNAVAILABLE`. Source commit:
`a466888246ec606816486c164fbf24b7e4da7114`.

The frozen tar-header-only audit found 636 unique, 32 ambiguous, and 8 missing source-batch joins among 676 anonymous
physical runs. Two of 146 source archives failed the frozen archive contract. Consequently 1,058 of 13,520 structural
pairs have incomplete endpoint identity. The complete subset has zero cross-true-batch pairs and zero task mismatches, but
the preregistration requires complete identity and does not permit post-result filtering. No pair orientation, numeric grade,
raw code, frozen-test effect, GPU, API, or model fitting was used; S1 is prohibited.

All descriptive support gates would otherwise pass: the fixed experiment-closed allocation yields 6,885 train pairs in 80
experiments and 1,429 dev pairs in 17 experiments across 15 tasks, with dev dominant-task share 0.1357592722183345, 12 dev
tasks having at least 20 pairs, and zero train/dev experiment overlap. This supports a narrow positive conclusion about corpus
scale, not predictor performance. A source-side provenance manifest and corrected archives are required to unlock a new S0.

Formal integrity: producer x2 and independent verifier x2 were byte-identical; focused tests were 13 passed and the full
phase suite was 604 passed with 25 warnings. The full remote directory is read-only with zero writable files and zero
filename/credential-shape hits. Compact evidence SHA-256:

- `summary.json`: `427ff5d9edd6ff00b60943952d7d95d3e4565df58528a96316ce8cc93a2ff2be`;
- `independent_verification.json`: `f6972b477f4ee56b83e2755018d77fc9ecb5ba2637cdbde3cf2894b0d82d276b`;
- producer result manifest: `e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92`;
- source inventory: `f33bef1606b4fd2b7c45872145872b85a4e7eb78d0301e2aad20d41b4b23035e`.

Full immutable artifacts:
`/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3`.
