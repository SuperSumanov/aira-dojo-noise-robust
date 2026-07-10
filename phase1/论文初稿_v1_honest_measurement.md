# Cheap Critics for Expensive Search: What a Frozen-Probe Value Model Can and Cannot Do in Poor-Compute LLM ML-Engineering

*(Draft v1 — 2026-07-10. Honest-measurement empirical paper. All numbers from `aira-dojo/phase1/`; data/scripts in Appendix.)*

---

## Abstract

LLM agents that write code to solve ML-engineering tasks (e.g. MLE-bench) search over candidate solutions, but scoring each candidate requires an **expensive full training run + official grading**. Under poor compute (a single GPU, few expensive labels), can a **cheap learned critic** — a *frozen* LLM's hidden features fed to a linear probe — predict that expensive grade and make the search cheaper? Through controlled ablations on graded LLM-generated solutions across three tabular tasks, we report a deliberately honest set of positive and negative findings:

1. **(H1, positive)** The frozen-probe critic predicts *same-task* grade and, crucially, **retains its signal when the candidate's self-reported validation score is ablated** (Spearman +0.36 intra / +0.18 cross-task on 289 graded solutions, robust across seeds), while self-report-only baselines collapse to zero. It carries grade information *independent of* the cheap self-report.

2. **(negative)** This rank skill does **not** translate into evaluation-budget savings. In a fixed-budget best-of-K simulation, the free self-report proxy **matches or beats** the probe — a concrete instance of the *rank ≠ regret* gap known from NAS.

3. **(positive, limited)** The probe's usable value surfaces exactly **where the self-report fails**: on candidate pairs the self-report ranks *wrong*, the probe is still ~59% correct at large sample (vs 0% by construction), suggesting a **self-report-failure / reward-hacking detection** use-case rather than a selection one.

4. **(negative)** Forcing the critic to *reason before scoring* (reasoning-first) does **not** help — even with a stronger 14B teacher, it underperforms a plain regression head.

We situate these against hidden-state reward models (ELHSR), agent process-reward models (AgentRM), and proxy-guided MLE agents (ArchPilot), and distill two methodological lessons: a **rank-vs-regret** warning for critic-guided search, and a **prompt-truncation pitfall** that silently disabled our reasoning critic for an entire study phase.

---

## 1. Introduction

Autonomous LLM "ML-engineering agents" — MLE-bench [OpenAI], AIDE, aira-dojo [Meta/FAIR], SELA, and related tree/greedy/evolutionary systems — solve Kaggle-style tasks by generating candidate code, running it, and searching over the results. The dominant cost is **evaluation**: every candidate is fully trained and officially graded. Under *poor compute* (a single commodity GPU, and labels that are expensive and scarce because one label = one full training run + scoring), the natural question is whether a **cheap surrogate critic** can predict a candidate's final grade and let the search spend fewer expensive evaluations.

A frozen LLM already reads the candidate's code; a light linear probe on its hidden states is essentially free. Does such a probe (a) predict the expensive grade, (b) carry information beyond the candidate's own cheap self-reported validation number, and (c) actually make search cheaper? We answer all three with controlled experiments, and the honest answer is **yes / yes / no-but** — a mix of positive and negative results that, taken together, map the *ability boundary* of cheap critics in this setting.

**Contributions.**
- **H1**: A frozen-probe critic predicts same-task grade and, under a **self-report ablation**, is shown to carry grade signal *independent of* the cheap self-report (§4.1) — robust across seeds.
- A **negative** result with a positive lesson: the probe's rank skill does **not** yield budget savings in a fixed-budget selection simulation; the free self-report proxy wins (§4.2). This is a clean *rank ≠ regret* instance in the LLM-agent setting.
- A **limited-positive** re-framing: the probe *does* add value **where the self-report is wrong** (§4.3), pointing to a self-report-failure / reward-hacking detection use-case.
- A **negative** result on **reasoning-first** critics: even a 14B teacher does not make "reason-then-score" beat a scalar head (§4.4).
- Two **methodological** lessons (§4.5): a prompt-truncation pitfall, and a code-length confound that inverts H1's apparent verdict if uncontrolled.

We explicitly do **not** claim a state-of-the-art system; the value is an honest characterization of what a cheap critic can and cannot do, with the confounds controlled.

---

## 2. Related Work

**Hidden-state reward models.** ELHSR / "Reward Inside the Model" [arXiv:2505.12225] learns a reward from a *frozen* LLM's hidden states via a single linear head — architecturally the **same family** as our probe. But it predicts **binary correctness** (BCE) on **cheap-to-verify** math/reasoning and is used for **best-of-N reranking**, not for saving a budget of *expensive* evaluations, and not for continuous ML-engineering grades. We borrow the mechanism; our contribution is the **problem setting** (expensive/scarce ML grade) and the **ablation-based independence argument** it never makes.

**Agent reward models.** AgentRM [arXiv:2502.18407] trains a **fully finetuned** LM + value head to predict step rewards on nine **cheap-to-simulate** agent tasks (WebShop, ALFWorld, …), used for accuracy/generalization via best-of-N + beam search — not framed as an evaluation-budget-saving surrogate, not a frozen probe, not ML-engineering.

**Proxy-guided MLE agents.** ArchPilot [arXiv:2511.03985] is the closest in *goal*: an MLE-bench agent that reduces expensive full trainings. But its proxy is **low-fidelity execution** — it actually runs a cheaper version (one epoch, 10% data, plus noisy/dropout variants) and re-weights these executed signals with ridge; **no learned predictor, no hidden-state features**. Our method **never executes** the candidate. I-MCTS [arXiv:2502.14693] adds an *LLM value model* to SELA to skip rollouts — a learned predictor, but prompted-LLM value on AutoML configs, not a frozen-feature probe on generated code. The specific triple {frozen-probe critic + expensive ML-grade prediction + budget-saving search in an LLM code-agent} is unoccupied.

**AutoML / NAS surrogates.** "Predictor-guided search saves evaluations" is mature: NAS performance predictors [White et al., NeurIPS 2021], pipeline surrogates (ML4ML, AVATAR), and multi-fidelity optimization (Successive Halving, Hyperband, BOHB, ASHA; MFES-HB reports 3.3–8.9× speedups). We borrow directly from this literature — and inherit its central warning that **rank correlation does not reliably predict search speedup** (rank ≠ regret), which §4.2 confirms in our setting.

---

## 3. Setup

**Cards.** Each candidate solution node from a real aira-dojo search journal becomes a *card*: what the critic may see — task description, candidate **code**, cheap observations (self-reported validation `val_at_low`, runtime, error), lineage (parent score, operator, depth) — and, held out, the **label**: the official MLE-bench graded score. A `view()`/`hidden()` split guarantees the label never leaks into critic input. Grading is by external pristine code; **no LLM-as-judge** anywhere.

**Data.** 289 graded cards over three tabular tasks (spaceship-titanic 221, nomad 37, tps-may 31), labels rescaled per-task min-max to [0,1]. All experiments below use this single unified 289-card set.

**Predictors.** Two label-free baselines — `one_epoch` (trust the self-report) and `asha` (curve extrapolation); and four critics — `zeroshot` (frozen LLM, single forward), **`probe`** (frozen Qwen2.5-Coder-7B hidden features + ridge), `scalar` (7B QLoRA + regression head), `reasoning` (7B QLoRA SFT, analyze-then-score). Probe/scalar/reasoning share one backbone for a fair comparison. On a single RTX 3090; 4-bit loading.

**Self-report ablation.** To test *independence* from the cheap signal, we mask `val_at_low`/`val_curve`/`parent_val` in a separate condition. Baselines then collapse; a critic that survives is provably reading grade signal from the **code itself**.

**Metrics.** Spearman rank correlation (with 3 seeds); a fixed-budget best-of-K selection simulation (§4.2); and a pairwise self-report-failure rescue rate (§4.3).

---

## 4. Results

### 4.1 H1 — the probe predicts grade *independent of* self-report

Spearman, mean over 3 seeds × 3 tasks (289 cards), full code context:

| condition | one_epoch (self-report) | probe | scalar |
|---|---|---|---|
| intra, normal | **+0.619** | +0.381 | +0.060 |
| **intra, self-report ablated** | +0.000 | **+0.356** | −0.023 |
| loto, normal | +0.502 | +0.103 | −0.007 |
| **loto, self-report ablated** | +0.000 | **+0.179** | −0.015 |

With the self-report present, the self-report baseline is strongest (it is same-source with the grade). **Under ablation the baseline collapses to exactly 0, but the probe barely drops** (intra +0.381→+0.356; cross-task +0.103→**+0.179**, *rising* — the self-report is a misleading cross-task signal that ablation removes). The probe therefore extracts grade information **from the code itself, independent of the self-report** — H1 holds and is robust (per-seed sd 0.12–0.17 on 289 cards). The learned `scalar` (QLoRA) is weak-to-negative in this small-data regime; H1's positive result rests entirely on the **cheap frozen probe**.

### 4.2 The rank skill does *not* buy evaluation-budget savings (rank ≠ regret)

We simulate a search under a budget of K expensive evaluations: pick the K candidates a strategy ranks highest, keep the best true grade. `regret(K) = oracle − best-recovered` (lower better).

| K=3 | critic (probe) | proxy (self-report) | random |
|---|---|---|---|
| intra tps-may (dispersed grades) | 0.215 | **0.000** | 0.171 |
| loto tps-may | 0.292 | **0.000** | 0.227 |

On the one task with real discrimination room (tps-may, dispersed grades), the **free self-report proxy is optimal (regret 0)** while the probe ≈ random (intra 0.215 vs 0.171) and cross-task is *worse* than random (loto 0.292 vs 0.227). On top-heavy tasks (spaceship, nomad — 89% of solutions near the max) everyone's regret ≈ 0 (any pick is fine). **No regime makes the probe the right selector** — its +0.41 rank does not translate into budget savings. This is exactly the NAS *rank ≠ regret* warning, and it explains why ArchPilot's low-fidelity proxy (≈ our self-report) is a sound design choice.

### 4.3 The probe's value is in *self-report-failure detection*, not selection

Selection failed because the self-report is already good *where it is right*. The probe's value should appear *where the self-report is wrong*. On candidate **pairs the self-report ranks wrong** (opposite the true grade — 0% correct by construction; random 50%):

| task | n | wrong-pairs | probe@wrong | probe@right |
|---|---|---|---|---|
| **spaceship** | 221 | 8382 | **0.59** | 0.71 |
| nomad | 37 | 204 | 0.55 | 0.68 |
| tps-may | 31 | 90 | 0.28 | 0.60 |

On the large-sample task (spaceship, 8382 wrong-pairs) the probe is **0.59 — above chance where the self-report is 0%** — a real, large-sample-credible independent signal. This is the operational form of H1's independence: **when the cheap signal misleads the search, the probe still carries grade information**, a self-report-failure / reward-hacking detector rather than a selector. Two honest caveats: independence is **partial** (probe@wrong 0.59 < probe@right 0.71; the probe is better where the self-report is also right — it is not *purely* independent), and it is **not universal** (tps-may 0.28 < random — but there the probe is intrinsically weak, §4.1, on only 90 pairs).

### 4.4 Reasoning-first does not help — even with a 14B teacher

Making the critic emit a natural-language analysis *before* scoring (hindsight-distilled) does not beat a scalar head (intra Spearman, per task, 289 cards, matched code[:1200]):

| task | scalar | reasoning (14B teacher) |
|---|---|---|
| spaceship | +0.058 | **+0.310** |
| nomad | +0.143 | −0.444 |
| tps-may | −0.396 | −0.304 |
| **mean** | **−0.065** | −0.146 |

Reasoning-first underperforms the scalar head overall (mean −0.146 vs −0.065; loto −0.083 vs −0.029). Yet **teacher quality is a genuine hidden variable**: on a 148-card pilot the same critic went from −0.01 (7B self-distillation teacher) to **+0.31 (14B teacher)**, and on 289 cards the 14B teacher still puts reasoning **+0.310 above scalar's +0.058 on spaceship** — so a "reasoning-first fails" claim from a weak teacher would be invalid. But the gain **does not generalize** (nomad/tps-may stay negative), and the scalar baseline itself degrades on the larger, noisier sample (a QLoRA-overfitting symptom consistent with §4.1). Reasoning-first is not worth its cost at this data scale.

### 4.5 Two methodological pitfalls (that would silently corrupt the study)

- **Prompt-truncation bug.** With code placed *before* the instruction block in a length-limited prompt, truncation dropped the "analyze-then-score" instruction, so the model simply **continued the code** and the parser grabbed a random number — the reasoning critic *never actually ran* for an entire phase, and its "degeneracy" was undetectable from metrics alone; only dumping raw generations revealed it.
- **Code-length confound.** Shortening the code to fit the reasoning critic's VRAM also **collapsed the probe's ablated score from +0.41 to +0.02** — because the probe reads the code. Restoring full-length code restored +0.41. A confound in one arm silently inverted another arm's headline verdict.

---

## 5. Discussion & Limitations

**The through-line: rank ≠ regret.** A cheap critic with genuine, ablation-verified rank skill (H1) still failed to help *selection* (§4.2) and only paid off in the narrower *failure-detection* framing (§4.3). Rank correlation is necessary but not sufficient for search utility — an operational restatement of the NAS lesson in the LLM-agent setting.

**Limitations (stated up front).**
- **Three tabular tasks**; generalization to vision/NLP/larger tasks untested. Grade distributions are often top-heavy, compressing selection headroom.
- H1's positive rests on the **frozen probe**, not the QLoRA critics (weak at this data scale).
- The rescue signal is **task-strength-dependent** (strong on spaceship, absent on tps-may where the probe itself is weak) and **partially, not fully, independent** of the self-report.
- Everything is **offline**; whether the failure-detection signal helps a *live* search is untested (though offline results here are the necessary precondition, and cheap to obtain).

**Positioning.** Not a system paper; an honest boundary map. The reusable artifacts are the **self-report ablation** as an independence test, the **best-of-K rank→regret** protocol, and the **wrong-pair rescue** metric.

---

## 6. Conclusion

Under poor compute, a nearly-free frozen-probe critic **can** predict same-task ML-engineering grade independent of the candidate's self-report (H1), **cannot** be used to pick candidates under a fixed evaluation budget (the free self-report proxy wins — rank ≠ regret), but **can** flag where the self-report is wrong (a limited but real reward-hacking-detection use-case), while reasoning-first critics do not help even with a stronger teacher. The honest map — what a cheap critic can and cannot do, with confounds controlled — is the contribution.

---

## Appendix — Reproducibility
- Data: `aira-dojo/phase1/cards_real_mm.jsonl` (289 cards; initial 148 backed up as `_148bak`), per-task min-max labels; external pristine grading, no LLM-judge.
- Scripts: `run_full_matrix.py` (`--ablate` self-report), `budget_probe.py` (best-of-K), `probe_rescue.py` (wrong-pair rescue), `build_cards.py` + `relabel_minmax.py`, `dump_reasoning.py` (pitfall diagnosis).
- Backbone: Qwen2.5-Coder-7B/14B, 4-bit, single RTX 3090; 3 seeds; all runs log seed/commit/budget.
- Results CSVs: `_h1k*` (H1), `_rfx*`/`_rfx14*` (H2), `bprobe_*.out` (§4.2–4.3).

## References

1. J. Guo, Z. Wu, H. Yang, P. S. Yu. **Mining Intrinsic Rewards from LLM Hidden States for Efficient Best-of-N Sampling** (ELHSR/SWIFT). arXiv:2505.12225, May 2025. *KDD 2026 (Research Track).*
2. Y. Xia, J. Fan, W. Chen, S. Yan, X. Cong, Z. Zhang, Y. Lu, Y. Lin, Z. Liu, M. Sun. **AgentRM: Enhancing Agent Generalization with Reward Modeling.** arXiv:2502.18407, Feb 2025. *ACL 2025.*
3. Z. Yuan, T. Liu, Y. Yang, Y. Wang, F. Qi, K. Rangadurai, B. Li, S. Yang. **ArchPilot: A Proxy-Guided Multi-Agent Approach for Machine Learning Engineering.** arXiv:2511.03985, Nov 2025.
4. Z. Liang, F. Wei, W. Xu, L. Chen, Y. Qian, X. Wu. **I-MCTS: Enhancing Agentic AutoML via Introspective Monte Carlo Tree Search.** arXiv:2502.14693, Feb 2025. *EACL 2026 Findings.*
5. E. Toledo, K. Hambardzumyan, M. Josifoski, R. Hazra, N. Baldwin, et al. **AI Research Agents for Machine Learning: Search, Exploration, and Generalization in MLE-bench** (aira-dojo). arXiv:2507.02554, Jul 2025.
6. Y. Chi, Y. Lin, S. Hong, D. Pan, Y. Fei, et al. **SELA: Tree-Search Enhanced LLM Agents for Automated Machine Learning.** arXiv:2410.17238, Oct 2024.
7. C. White, A. Zela, B. Ru, Y. Liu, F. Hutter. **How Powerful are Performance Predictors in Neural Architecture Search?** arXiv:2104.01177. *NeurIPS 2021.*
8. Y. Li, Y. Shen, J. Jiang, J. Gao, C. Zhang, B. Cui. **MFES-HB: Efficient Hyperband with Multi-Fidelity Quality Measurements.** arXiv:2012.03011. *AAAI 2021.*
9. T.-D. Nguyen, T. Maszczyk, K. Musial, M.-A. Zöller, B. Gabrys. **AVATAR — Machine Learning Pipeline Evaluation Using Surrogate Model.** arXiv:2001.11158. *IDA 2020.*
