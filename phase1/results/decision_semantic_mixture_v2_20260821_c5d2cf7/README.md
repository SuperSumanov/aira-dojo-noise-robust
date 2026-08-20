# Decision semantic mixture v2 exact-config discovery

Formal retrospective discovery at source `c5d2cf72a9e0e7aae2aa394532aca16279ad9047` on the exact-config
eligible senior `baf6bddefe62b769b2fab699ff5805dd627dc69f` decision pairs.

- Scientific status: `DISCOVERY_NO_UNLOCK` (4/6 fixed effect gates pass).
- Merged pooled → semantic-mix micro accuracy: `0.5832438238453276` → `0.6004296455424275`
  (delta `0.017185821697099923`).
- Merged task-macro accuracy: `0.5743054636618959` → `0.5845981187534576`
  (delta `0.010292655091561631`).
- Task-clustered 95% CI: `[-0.020432976223223577, 0.04351597259972664]`; parent-clustered micro-delta
  CI: `[-0.003174687247780468, 0.037353489626701986]`.
- Draft micro delta: `0.019108280254777066`; Improve micro delta: `0.01620745542949753`.
- Among 23 tasks with at least 10 test pairs: 10 positive / 9 zero / 4 negative, positive fraction
  `0.43478260869565216`.

The point estimates are favorable but fail the pre-registered task-CI and task-consistency gates. No future
confirmation is unlocked, no weight/task/subset is changed, and the result-blind conditional parent-weighting audit is
not triggered.

Producer ×2 and independent full-refit verifier ×2 are byte-identical. All input/split/exact-config checks pass;
focused tests are 10/10; filename/content credential scans are zero. Total sequential wall time was 1,184.46 seconds,
maximum RSS 3,567,940 kB; GPU/API/checkpoint/base-LLM update/prospective-vault access were all zero.

The complete remote bundle is:

- `/research/d7/spc/yzyang4/decision-semantic-mixture/c5d2cf7-baf6bdd-v2-exact.tar.gz`
- bytes: `10535`
- SHA-256: `d96e747fcbd12c8e200b06eda644401cec0e18a1033e8ad0f2afee56aa591ed3`

One documentation correction is explicit in `postflight_atomicity_correction.txt`: preflight line 06 described the new
output directories as atomic, while the implementation wrote directly into fresh directories. This does not change the
completed, hashed, double-reproduced result, but the atomicity claim is withdrawn.
