# TraceML external structure eligibility audit (2026-08-21)

This is the aggregate-only, outcome-free result bundle for the pre-registered
TraceML external replication eligibility audit.

## Fixed inputs

- TraceML revision: `61faec615b179f186dbe9c82ee59d17e14817e96`
- producer/verifier source commit: `517c95c87edceb9d5841696982a34638db9d2fe2`
- `state.parquet` SHA-256:
  `b7fb37b040258bbb958c5ba1bc78952729fb69daabc75797974ef2cf19b74e02`
- `action.parquet` SHA-256:
  `d23a471ab1dcfbda16836827a763f829c9de12071b32bfcc88f69d4411a8d2e4`
- raw parquet files are deliberately not included in Git.

## Verified decision

- 189/189 branch keys map to exactly 13 declared MLEvolve physical-run prefixes.
- 1,026 state rows and 837 action rows join without missing identities.
- Deduplicating repeated branch paths leaves 583 provisional path-adjacency edges.
- Only 537 joined edge rows advance depth by exactly one; 300 rows skip one or more
  levels (`+2`: 178, `+3`: 99, `+4`: 22, `+5`: 1).
- The pre-registered direct-edge mapping therefore fails closed. Canonical direct
  sibling pairs are reported as `null`, not as 167.
- The 167 figure is retained only as an invalid relaxed-path diagnostic. It spans
  three tasks and is dominated by one task at 117/167 =
  `0.7005988023952096`, so it would independently fail the fixed task-support and
  balance gates.
- `raw_code_path` coverage is 0/643 reconstructed original nodes. The score and
  overlap stages were not run, and frozen scorer execution was not authorized.

Producer runs 1/2 and verifier runs 1/2 are byte-identical. The verifier uses an
independent key parser and graph traversal and does not import the producer. The
focused suite reports `12 passed`; all four formal processes exited 0. No score
column, code content, local prospective outcome, GPU, or API was used.

Primary evidence is in `producer_1.json` and `verifier_1.json`; the duplicated files
are retained as deterministic reproduction evidence. `full_artifacts.tar.gz` is the
byte-identical archive copied from the remote postflight and has SHA-256
`4cc0ecc7caabe6bc6377fc7f2b7fff9953a38e0e844eae7b3c62b48b382d98b0`.

This result supports only the narrow artifact distinction: the fixed public TraceML
paired tables cannot instantiate our direct same-parent sibling replication protocol.
It does not establish that the authors' gated raw v1 trees lack recoverable siblings,
and it does not restore any broad “first trajectory/tree dataset” claim.
