# Anonymous reviewer artifact v0 — aggregate executable preview

Date: 2026-09-02. This note records a submission-engineering result, not a new
predictor or search result.

## Decision

The reviewer artifact is now **locally executable and independently verifiable** as
an anonymous, aggregate-only preview. It is not a dataset release and is not yet a
public anonymous mirror. The package exposes exactly 24 hash-bound source resources
and two generated manifests (26 files total); it contains no Git history, source
commit, author or institution metadata, historical card payloads, row-level
predictions, or prospective identities/labels/outcomes/predictions/utility.

The package contract makes four materially different evidence levels explicit:

1. Figure 1 is exactly regenerable from code and has no scientific values.
2. Figure 2 is exactly regenerable from a frozen outcome-blind aggregate trajectory;
   upstream row-level recomputation is not claimed.
3. Table 4A and the cost panel can be checked for exact paper transcription, support,
   and scope, but cannot be scientifically recomputed without the unreleased 931-row
   payload.
4. The v11 descriptor and corpus hash can be inspected, but the 16,012-card payload
   is not included and cannot be rebuilt from this preview.

The prospective confirmation remains excluded and sealed.

## Reproduction result

Two independent output directories were built from the fixed allowlist. Text inputs
are canonicalized to UTF-8/LF while PNG bytes remain exact, so checkout line-ending
settings cannot change the package. Their trees and ZIP archives were byte-identical.
Each final r4 archive is 656,781 bytes with SHA-256
`79f326899dd1dd766493c50433d1820bb5abc09ac45bfcee189b73c994659352`.
The independent verifier passed on both copies, including exact source hashes,
package file set, manifest coverage, ZIP order/timestamps/modes/payloads, and
credential/identity scans.

The package's own offline check first enforces the pinned dependency versions. It then
regenerates Figure 1 and Figure 2 with byte-exact SVGs and pixel-exact decoded PNGs;
the latter permits only OS-specific PNG compression bytes, not a single changed RGBA
value or dimension. It also checks the Table 4A population/panel/scope, cost-panel
boundary, and v11 descriptor invariants. It makes no network, GPU, paid API,
model-fit, or base-update call. The focused regressions include tamper and
source-hash-drift fail-closed controls.

The first remote post-push check of commit `370d2c2` is retained as a failure:
14 focused tests passed and one failed because the shared environment used unpinned
Matplotlib/NumPy. Repeating under the exact pins showed that both SVG files were
byte-identical and both decoded PNG arrays had identical shapes and zero changed RGBA
values, while only PNG compression bytes differed between Linux and Windows. The r4
contract therefore checks SVG bytes and decoded PNG pixels separately and rejects a
dependency-version mismatch before rendering.

## What this closes and what remains

This closes the local executable-preview part of the anonymous-artifact blocker. It
does not close reviewer hosting, content-bearing dataset access, provider/content/
privacy/license clearance, Croissant core, or fresh anonymous reproduction. The
correct submission claim is therefore “executable aggregate audit preview ready,”
not “dataset released” or “headline results fully recomputable.”

The build contract is `phase1/anonymous_reviewer_artifact_v0.json`; the deterministic
builder and non-importing verifier are
`phase1/build_anonymous_reviewer_artifact_v0.py` and
`phase1/verify_anonymous_reviewer_artifact_v0.py`. The local ZIP is intentionally kept
outside Git until the anonymous-hosting and release decision is made.
