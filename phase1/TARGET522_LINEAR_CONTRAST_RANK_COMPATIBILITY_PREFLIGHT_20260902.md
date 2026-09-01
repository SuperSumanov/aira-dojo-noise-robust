# Target-522 linear contrast-rank compatibility preflight (2026-09-02)

## Decision

Run the already frozen Target-522 linear contrast-rank audit exactly once through an
execution-only Stage-A v2 compatibility projection.  The scientific protocol, rank
thresholds, acquisition/evaluation partition, decision rule, analyzer, independent
rank verifier, and original scientific test remain byte-identical.  This is not a
second chance to select a cohort or rescue an unfavorable support result.

The Stage-A v2 formal output completed before this execution file was written, but
the compatibility transformation itself was frozen while Stage-A v2 was incomplete
and before its public profile or classification was opened.  The only prior
observations used to define the bridge were source diffs and container metadata:
the immutable selection package had six extra manifest-bound recovery receipts.

## Exact compatibility transformation

The actual Stage-A v2 public JSON is immutable.  A mode-0600 compatibility view is
constructed for the byte-frozen rank analyzer by:

1. removing exactly `selection_container` and
   `selection_container_compatibility_sha256`;
2. replacing exactly `analysis_source_commit` from the compatibility execution
   commit to the original frozen scientific implementation commit; and
3. rejecting any other top-level removal, addition, or changed value.

An independently implemented verifier reconstructs this transformation from the
actual Stage-A public file and requires byte equality with both the projection and
its receipt.  The original Stage-A file is never modified.  The formal runner then
feeds only this compatibility view to the unchanged rank analyzer and unchanged
rank verifier.

## Machine-verified bindings

- Frozen rank scientific protocol:
  `3c8b8f87b43cae74a57c28d78e3428d824f54969051fadf5086810da467ad323`
- Stage-A compatibility protocol:
  `ea2bc26029f6575037f3bf33df580cbd737f49948d5e9fe4f116d73c95c61476`
- Rank execution v2:
  `cc3a53019dc72243450c23c072eb603498705db56fc834378f258e626b010693`
- Projector:
  `3eaef4517f7c8a291f670845527279a99c55859fa26ca3581527a263506c175d`
- Independent projection verifier:
  `f0c8a18d76d104ee44b7a7f83e3470f419809911e7db84b8151c4a377aa56daf`
- Byte-frozen rank analyzer:
  `120e55269fde767cdbe3f036bc28a6293788e72c83972529fbef9c48e0274c41`
- Byte-frozen rank verifier:
  `92ab4533d72d8bd73b75e7ef266798ecf7d25ca4d454ada0571488028695ff93`
- Byte-frozen scientific test:
  `a4e82a14b4f8d3e05174bc2639bafe22e46fec1d3ef5c3c05b7c0b8019818205`
- Compatibility test:
  `569b4cf111b04ad0673d21b84b64ec94897696ba7df3c640f69d802c2ad70ef6`
- Runner:
  `8d736178859c9692fac5681162997b3d4e3f3cf2f62a92db153304a67e44279c`
- Monitor:
  `9c42d04d6f0396eaa0d28238a9b3ec8bfaf603be83d294d7d0bfd1bfb37ab27d`

The actual Stage-A v2 postflight passed at source commit
`05458c439499b145cfeea3a69c109e9e55895ece`; its immutable formal manifest is
`579305941490e8df8d20fb4484c7702a6fd531f0f05371f0d588c4cda4175cd2`
and public A/B SHA is
`a696c6d0f86acc651ffe0fcda956a76e927c2052a184b04d47753b1a081575e8`.
The postflight script SHA is
`bda1774c5b7355048e6427c63e0f4626672adbddbc8ead5b4e3ab1b8a0de9743`.

An actual-file smoke test produced an exact independently verified projection while
emitting no profile, identity, or classification.  The focused old-science plus
compatibility suite reports `27 passed`.

## Formal gates

The formal runner must pass all of the following before writing `COMPLETE`:

- fresh detached exact-commit worktree and clean Git state;
- exact hashes for execution, compatibility, projector, both independent
  verifiers, unchanged scientific sources, both tests, runner, and monitor;
- immutable Stage-A `COMPLETE`, no `FAILED_RC`, exact manifest, and byte-identical
  public A/B;
- focused tests and the full `phase1/tests` suite;
- projector A/B, projection-verifier A/B, analyzer A/B, and rank-verifier A/B all
  byte-identical;
- mode 0600 for intermediate/result JSON before the final read-only seal;
- zero forbidden-path and network trace hits for all four roles;
- zero credential filename/content hits; and
- unchanged Stage-A manifest and public hash after execution.

The runner stdout and monitor `READY` receipt expose only status and hashes.  The
rank classification and graph profile remain sealed until an independent postflight.

## Interpretation boundary

If Stage-A support is incomplete, the original frozen rule returns limited support;
that outcome must not be rewritten as either positive or negative evidence.  If
support is complete, the original two-partition threshold is applied exactly once.
No result from this audit is predictor efficacy, search utility, effective sample
size, or a clean scaling confirmation.  GPU, paid API, model fit, and base-model
update counts are `0/0/0/0`.
