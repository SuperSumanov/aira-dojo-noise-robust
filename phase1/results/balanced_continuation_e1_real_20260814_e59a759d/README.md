# Balanced-continuation real E1 archive

Final scientific status:
`INVALID_FOR_METHOD_CLAIM_ENGINEERING_FAILURE_REPAIRED_NOT_RERUN`.

The frozen run at commit `e59a759d99dd490b6f8a0011c66dd7c772307b28` completed eight rollout
jobs, sixteen candidate attempts, fourteen candidate processes, and eight one-shot operator
calls with no retries, no analyze calls, and no D_test access. Candidate wall time was
`2047.6709687478572` seconds (`0.5687974913188492` GPU-hours). The independent compact-archive
verifier recomputed eight rollout, four sibling, and two task records without importing the
producer. All 537 top-manifest entries were separately rehashed with zero mismatch.

The published zero utilities and ties are not a negative method result. The v1 scorer required a
candidate's IDs to equal one private 10% subset even though the public submission template correctly
covers the union of D_search and D_val. Zero-execution replay at clean commit
`f352b013c67fb1b98b17391ba32711faaa780367` recovered six valid warm artifacts but no valid
continuation, leaving zero paired rollouts. All eight original operator calls hit the 8192-token
output cap; continuation failures were two invalid formats, two Python syntax errors, and four
Python name errors.

The separately preregistered Qwen two-call operator-only probe passed on both tasks with zero GPU
and zero candidate execution. It is an alternative operator, not the frozen E1 production model.
A second, production-matched DeepSeek probe passed spaceship but failed tabular: the latter again
hit 8192 completion tokens with `finish_reason=length` and no complete code block. Thus the original
production path remains closed. Qwen can only be introduced through a new operator contract and a
fresh experiment; neither probe estimates a method effect, unlocks E2/E3, or authorizes a GPU rerun.

Key hashes:

- compact collection summary:
  `576c897a17220b02f9ff1ed5ded38685bcd1da6b009e90ba0eeca73648af3adf`;
- independent collection verification:
  `9bd229544b334d3910173cd69be1e431d27efb59177c859ee5df43337c525b48`;
- zero-execution adapter replay:
  `4f99b146ad9bcc1e42c4cf466806c23944de4c6e2572c466e8b7cfa9ce9b26a5`;
- operator-only probe summary:
  `a30aa463a75ead9fa48fcd53a37921749425ac4a8ee696b18c2d0be33413ed1d`;
- production-matched DeepSeek probe summary:
  `1409719b01fc788797d299b341bf55244313090be496bc4c751a95614e12623f`.

Raw API responses, private labels, candidate workspaces, and credentials are intentionally absent.
The remote raw probe files remain mode 0600 and are represented here only by hashes in the compact
summaries.

Clean-checkout verification also repaired two pre-existing missing LFS result objects. The second
receipt, `lfs_frozen_embed_repair_receipt.json`, records the 17,145,534-byte frozen-embedding tar's
path/link/credential scan and byte-identical remote refetch. These repairs do not change the corpus
release contract: corpus releases still publish immutable batches once and rebuild merged versions
from a release descriptor.
