# G-reuse source-package declaration validator

Exact code: `005d0d2`. Formal root:
`/research/d7/spc/yzyang4/g-reuse-source-package-validator/formal-005d0d2-v2`.
Source archive SHA-256: `dd5ddd7dd8c15e6cd5ff7127af586479aee09bed8d3a7685dfb74e90d905cf56`.

The validator checks the seven required package roles, exact bytes/SHA/LFS-OID declarations,
same manifest/producer-receipt commit/release/config declarations, UTC producer time, duplicate
JSON keys, credential shapes, path traversal, symlinks, and listed hardlink aliases. It parses
only the manifest and two fixed-schema small receipts, not Cards, pair, split, provenance, label,
or prediction payloads.

Nine synthetic tests passed locally. On Linux, both raw test runs independently reported nine
passes with empty stderr. Their raw outputs differ only in pytest duration; the first formal
comparison correctly stopped on that difference. A new root preserved both raw streams and
normalized only the explicit duration token. The normalized streams are byte-identical with
SHA-256 `9111e3399a60f0407a09454c983a83ea24085e8b78f61a8d656e9bf1f77ddb4a`.

Success is deliberately classified as `PACKAGE_DECLARATION_HASH_BOUND_NOT_EFFECT_ELIGIBLE`.
It does not attest that the declared producer commit/config ran, that instances are independent,
that the evaluator is pristine, or that the split is experiment-closed. Existing source-v2,
payload overlap/config, outcome-blind power, G0, and explicit GPU-budget gates remain mandatory.
GPU jobs, paid API calls, model fits, and protected-value reads were all zero.

## Link-safety hardening

Code review after the first receipt found that the validator rejected aliases among listed
artifacts but did not reject a hardlink to an unlisted file, and an in-root intermediate symlink
was not explicitly rejected. Commit `9bc90cc` now rejects every symlink path component and requires
link count one for the manifest and every artifact. Linux formal root `formal-9bc90cc-v3` passed
11 tests twice with empty stderr; duration-normalized outputs are byte-identical with SHA-256
`bc8e66bc8b6559e106b228ab58cd0c82f48b32471aa5f218546aa0cc65d1012b`. The hardened source
archive SHA-256 is `b7118f16488417ab707ee2b13004e208f893c64e47b384c84085e7710aabe24a`.
This supersedes the nine-test security surface above without changing the declaration-only status.
