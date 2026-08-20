# Decision semantic exact-config support v2

Formal outcome-blind support gate for the fixed senior `baf6bdd` decision files. Scientific source:
`21a4d4e4e81e780259fbf300112b561ae0fc1116`.

- Status: `V2_EXACT_CONFIG_SUPPORT_ELIGIBLE` (10/10 fixed gates pass).
- Eligible merged: 5,240 train / 931 test; 28 test tasks; 23 with at least 10 pairs.
- Dominant test task: 100/931 = `0.10741138560687433`.
- Removed: 385/6,556 pairs, all Draft hardware mismatches.
- Train/test endpoint and physical-run overlap: 0 / 0.
- Producer ×2 and independent verifier ×2 are byte-identical; focused tests 11/11.
- GPU/API/model/checkpoint/prospective outcome access: 0.

The repository stores aggregate receipts only. Exact filtered JSONL identities are fixed in
`DecisionSemanticMixture_v2支持门裁决与输入绑定.md` and can be regenerated with the committed producer. The complete
remote bundle is `21a4d4e-baf6bdd-v2.tar.gz`, SHA-256
`ff5e2448a1222c4a59480ab8db638908b98d1d644ae9d6bf97f69cdddb11d986`.
