# Decodable but Not Usable: What a Frozen Code‑LLM Knows About ML‑Solution Quality, and Why It Does Not Guide Poor‑Compute Search

*Working draft v3 — supersedes `论文初稿_v2_穷算力杠杆.md`. Single‑GPU, model‑agnostic, no LLM‑as‑judge.*

---

## Abstract

Automated ML‑engineering agents search over candidate solutions; a natural way to guide that search cheaply is a **critic** that scores a candidate *before* paying to evaluate it. We ask, under deliberately poor compute — a single consumer GPU, and a base search LLM that is never fine‑tuned and reached only through an API — whether such a critic can be read out of the internal representations of a *frozen* code‑LLM, and whether it actually helps. On 289 externally‑graded solutions from three Kaggle‑style tabular competitions, we find a sharp dissociation.

**The signal is there.** A linear probe on a frozen code‑LLM's mid‑layer representation decodes the eventual (expensive) grade *across tasks*, and that signal is (i) independent of the candidate's own cheap self‑reported validation score, (ii) independent of code length — the make‑or‑break confound — (iii) low‑dimensional (one principal direction recovers ~70 %), and (iv) reproduced across four code‑LLMs from three families.

**But the signal is not usable for control.** It buys **no** budget savings under a fixed evaluation budget (*rank ≠ regret*); a deployment **veto** built on it evaporates on real search trees; and the quality direction cannot be causally **steered** — only surface features such as code length steer the model's behaviour. A frozen representation *knows* solution quality without being able to *use* it.

**The one thing it can do is detect failure.** The same probe flags reward‑hacking / validation‑overfit solutions that the self‑report is blind to (AUROC 0.63; inside the set the self‑report trusts, the self‑report is actively *anti*‑informative), though the effect is modest and length‑comparable. A trained reasoning critic and multi‑fidelity screening add nothing at this data scale. Under poor compute the lever is **clean evaluation, not a cleverer critic** — a single‑GPU, model‑agnostic instantiation of the AIRA_2 diagnosis, delivered as a set of cheap, adversarial, offline falsification tests.

---

## 1. Introduction

LLM agents that do machine‑learning engineering (write, run, and refine ML code against a held‑out metric) spend most of their budget *evaluating* candidate solutions — each evaluation trains a model and scores it. A search controller that could tell a good candidate from a bad one *before* evaluating it would be worth a great deal: it could rank candidates, prune the budget, or steer generation toward better solutions. The obvious such controller is a **learned critic**.

Two facts make this hard in our regime. First, **compute is poor**: one RTX 3090, and a base LLM (DeepSeek) that we deliberately never fine‑tune — the method has to be *model‑agnostic*, so all "learning" must live in a light‑weight readout, not in the base weights. Second, prior work is sobering: aira‑dojo [2507.02554] formalises search *policy* × *operator* and reports that, with the evaluation held fixed, the search policy contributes little; AIRA_2 [2603.26499] diagnoses the degradation not as memorisation but as **evaluation inconsistency / noise**. Our study is a single‑GPU instantiation of that diagnosis, and it asks the narrow, concrete question underneath it: *can a cheap critic, read from a frozen code‑LLM, recover the signal a noisy evaluation loses — and does recovering it help the search?*

Our answer is a clean dissociation between **decodability** and **usability**, which organises the paper:

- **Contribution 1 — the signal is there (§4).** We frame the critic as *linear probing*: how much of the eventual grade is linearly decodable from a frozen code‑LLM's representation of the candidate code? The grade is decodable cross‑task, and the signal is **independent of the candidate's self‑report and of code length**, **low‑dimensional**, and **general across model families**. This is a representation‑probing result about what frozen code‑LLMs encode, not a trained model.
- **Contribution 2 — it is not usable for control (§5).** The same signal **saves no evaluations** (rank ≠ regret), **does not convert as a deployment veto** on real trees, and **cannot be steered** (only surface features steer). Each is a distinct, controlled, mostly‑offline experiment.
- **Contribution 3 — the one deployable use is failure detection (§6).** The probe flags reward‑hacking the self‑report misses — a length‑independent, self‑report‑independent detector — but modestly.
- **Contribution 4 — two more non‑levers and two pitfalls (§7–8).** A trained reasoning critic and multi‑fidelity screening add nothing at this scale; two measurement artifacts we hit are worth flagging because either could have produced a false headline.

Everything is offline, cheap, and **designed to falsify before you build**. We report medians across seeds with dispersion, never single numbers, and we surface the confounds ourselves.

## 2. Related work

**Search‑policy negatives.** aira‑dojo [2507.02554] is our target: with evaluation fixed, search policy barely matters. AIRA_2 [2603.26499] relocates the cause to evaluation noise and proposes a high‑consistency evaluation (HCE) protocol; §5–§6 show that two "obvious fixes" to the critic side (a learned critic, multi‑fidelity screening) do *not* rescue the affordable regime, which is consistent with the lever being evaluation, not policy.

**Hidden‑state reward models.** ELHSR / "Reward Inside the Model" [2505.12225] learns a reward from a *frozen* LLM's hidden states via a linear head — the same family as our probe — but for **binary correctness** on **cheap‑to‑verify** reasoning, used for best‑of‑N reranking. We borrow the mechanism; our setting is the **expensive, scarce, continuous ML grade**, and our contribution is an **ablation‑based independence** argument that reranking work never needs to make.

**Probing code‑LLMs.** OPENIA [2501.12934], AutoProbe [2510.02934], and a contrastive‑direction code ranker [2512.07404] (which uses the *same* Qwen2.5‑Coder‑7B) show a frozen code‑LLM's hidden states linearly encode **binary unit‑correctness** against a solution's own tests. We differ on two axes: a **continuous downstream task grade** rather than pass/fail of one unit, and **verified independence** from the self‑report and from code length.

**Steering & reward hacking.** Steering code‑LLMs [2603.23629] finds the controllable directions are *language/library*, not quality — which our §5.3 confirms causally. Reward‑hacking detection is an active area [2601.20103; 2604.01476] under the Goodhart framing [2210.10760]; our §6 casts the probe as one such detector.

## 3. Setup

**Data.** 289 "cards" harvested from AIRA_MCTS searches (base LLM = DeepSeek, via a LiteLLM/OpenAI‑compatible client) on three tabular Kaggle‑style competitions: `spaceship‑titanic` (221 cards, classification), `nomad2018‑predict‑transparent‑conductors` (37, regression/RMSLE), `tabular‑playground‑series‑may‑2022` (31, classification). Each **card** is a candidate solution carrying: the task, the generated code, the cheap early signals the agent saw (self‑reported validation score `val_at_low`, runtime, lineage), and — separately, as the **label** — an **external, pristine, medal‑normalised grade `y`** computed by held‑out code the agent never touches. Cards with no official grade are dropped.

**Models.** The base search LLM is never fine‑tuned (model‑agnostic is the point). The critic's substrate is a **frozen** code‑LLM used only as a feature extractor: primarily Qwen2.5‑Coder‑7B‑Instruct, plus Qwen2.5‑Coder‑14B, DeepSeek‑Coder‑6.7B‑Instruct, and CodeLlama‑7B‑Instruct for the cross‑family check (§4.4). All loaded in 4‑bit; a ridge readout is the only thing "trained".

**Integrity & fair contract.** Grading is external and pristine (no reading a possibly‑tampered in‑workspace evaluator); the agent sees scores, never labels; there is **no LLM‑as‑judge** anywhere. In every comparison **only the studied knob varies** — operator set, base LLM, per‑task budget, task set, and data split are fixed and logged. We pin seeds, dependency versions, and the commit, and write one CSV row per run.

## 4. The signal is there: representation probing (H1)

We ask one single‑level question: **how much of the eventual (expensive) grade is *linearly decodable* from a frozen code‑LLM's representation of the candidate code** — and is that information already in the candidate's cheap self‑report, or merely a proxy for how much code was written? The frozen model is the *object of study*; a ridge readout is the *measurement instrument* (standard linear probing, cf. hidden‑state reward models [2505.12225]). We report Spearman ρ, per‑task 5‑fold CV within‑task (**intra**) and leave‑one‑task‑out (**LOTO**), 3 seeds, 289 cards.

| probe (Qwen2.5‑Coder‑7B, of 28 layers) / condition | intra ρ | cross‑task LOTO ρ |
|---|---|---|
| last layer 28, normal | 0.35 | 0.07 |
| **mid layer 21, normal** | 0.30 | **0.18** |
| **mid layer 21, self‑report ablated** | 0.28 | **0.24** |
| mid layer 21, ablated **+ code‑length residualised** | 0.20 | **0.30** |
| code‑length only (log len, log #lines) — floor | 0.20 | **−0.07** |

**Mid‑depth carries the signal best (Fig 1).** A mid layer (21 of 28) decodes the grade better cross‑task than the last‑layer default (LOTO 0.18 vs 0.07), matching the interpretability finding that intermediate representations are richest and no fixed final layer is optimal. Naïvely concatenating all layers does not help — early layers dilute; pick one good mid layer.

**It survives ablating the self‑report (Fig 1).** Masking the candidate's own `val_at_low` / curve / parent from the prompt collapses a self‑report‑only baseline to exactly 0, yet the probe barely drops and cross‑task *rises* (LOTO **0.24**). The representation encodes grade information from the *code itself*, not by echoing the cheap score.

**It survives controlling for code length — the make‑or‑break confound.** High linear‑probe decodability can be a pure length artifact [2606.02907]. We residualise every hidden‑state dimension against log(code length) and log(#lines), fit on the training fold only. Code length *alone* decodes at ρ 0.20 within‑task but **−0.07 cross‑task — it does not generalise at all**; the residualised probe *holds*, LOTO rising to **0.30**. The encoded signal is genuine representational quality, not a length proxy. (Intra carries a mild length confound, so we headline the confound‑clean LOTO.)

**The signal is low‑dimensional (Fig 4).** Projecting to the top‑*k* PCA components before the ridge, a **single** component already decodes ρ 0.21 — ~70 % of the full 7,169‑dim ρ 0.31 — and ≤ 16 components match it; a single contrastive *good‑minus‑bad* direction is weaker (0.10), so the quality signal is the representation's **top principal variance, not a mean shift**. This mirrors the "confidence manifold" result that a frozen LLM's *binary* correctness lives in 3–8 dimensions [2602.08159]; our continuous grade behaves the same, which is why a light ridge — not a deep head — suffices.

**It is not Qwen‑specific — it replicates across families (Fig 6).** Running the identical protocol on three further code‑LLMs, the self‑report‑ablated, length‑residualised cross‑task grade signal stays positive in **every** family: LOTO = **0.30** (Qwen‑Coder‑7B) / **0.23** (Qwen‑Coder‑14B) / **0.20** (DeepSeek‑Coder‑6.7B) / **0.20** (CodeLlama‑7B), all far above the −0.07 length floor. Two honest notes: the *best layer* is model‑specific (mid‑to‑late for Qwen, early — ~25 % depth — for DeepSeek/CodeLlama), and *scale does not help* (14B < 7B). What matters is **that** the backbone is a code‑LLM, not its size — the grade signal is a general property of frozen code‑LLM representations.

**Novelty.** The closest priors [2501.12934; 2510.02934; 2512.07404] linearly encode *binary unit‑correctness* from a frozen code‑LLM. We are distinct on two axes no prior makes: a **continuous eventual task grade**, and **ablation‑verified independence** from both the self‑report and code length, general across families. A QLoRA `scalar` critic is weak‑to‑negative at this data scale; H1 rests entirely on the frozen probe — the contribution is *what the representation encodes*, not a trained model.

## 5. …but the signal is not usable for control

The rest of the critic story is a single through‑line: the decodable signal (§4) cannot be turned into a search benefit. Three distinct mechanisms, three negatives.

### 5.1 It buys no budget savings (rank ≠ regret, Fig 2)

Under a fixed budget of *K* expensive evaluations, define `regret(K) = oracle − best‑recovered`. On the one task with real discrimination room (tps‑may, dispersed grades):

| K = 3 | critic (probe) | proxy (self‑report) | random |
|---|---|---|---|
| intra | 0.215 | **0.000** | 0.171 |
| LOTO | 0.292 | **0.000** | 0.227 |

The **free self‑report proxy is optimal** (it picks the budget's best), while the probe ≈ random and cross‑task *worse* than random. On top‑heavy tasks any pick is fine. **No regime makes the probe the right selector** — its +0.4 rank advantage does not translate into savings. This is the NAS *rank ≠ regret* warning, and it explains why a cheap proxy screen (≈ the self‑report) is already a sound choice.

### 5.2 A deployment veto does not convert on real trees

v2 proposed wiring the failure signal (§6) into deployment **as a veto** — override the self‑report's pick when the probe distrusts it. We ran it, offline first. **On random candidate pools it looks like a large win** (Δregret up to +0.181 at K=20 on spaceship; a soft blend `argmax(z(self‑report)+λ·z(probe))` cuts spaceship regret 0.235 → 0.040). **On real search trees it vanishes**: with each pool taken from one real spaceship run (18 runs, leave‑one‑run‑out probe, no within‑run leakage), a hard veto gives Δregret **−0.001** (3 win / 4 lose / 11 tie), and the best soft blend gives +0.007 with a 95 % bootstrap CI of **[−0.003, +0.018]** — **not significant**. The random‑pool win is an artifact of *independent* candidates; real trees converge via improve‑lineage, so the self‑report's own pick is already good. *rank ≠ regret* extends from best‑of‑K selection to the online veto.

### 5.3 The direction cannot be steered (Fig 5)

Decodability fails usability in a third, causal sense. We activation‑steer the frozen model's layer‑21 residual stream along the grade direction (CAA‑style, ±3σ in units of its own projection std) and read the model's own soft score (expected value over the score digit's token distribution — a continuous readout, since the greedy score quantises to 7 buckets and is itself anti‑correlated with the grade, ρ −0.21). The quality‑specific effect is *statistically* detectable at n = 289 but **negligible** (quality − random slope +1×10⁻⁴, ~0.01 % of range), and a norm‑matched **random** direction is itself "significant" (a generic perturbation effect) — the significance bar is meaningless at this power. The one direction that genuinely moves the output is **code length** (≈ 4.5× larger): the only steerable axis is a surface feature, exactly as steering‑code work reports [2603.23629]. So the §4 grade signal is **decodable but not causally usable** — it selects nothing (§5.1), vetoes nothing (§5.2), and steers nothing; only surface features steer.

## 6. The one deployable use: failure detection

Where the probe *does* earn its keep is where the self‑report is **wrong**. On candidate pairs the self‑report ranks incorrectly (0 % correct by construction; random 50 %), the probe is still right (Fig 3): **0.59 on spaceship** (8,382 pairs), 0.55 nomad, 0.28 tps‑may — a self‑report‑failure / reward‑hacking detector, not a selector. Two honest caveats: independence is *partial* (0.59 < probe‑@‑right 0.71) and *not universal* (tps, where the probe is intrinsically weak).

**Made deployable, it beats the self‑report and is not a length artifact — but it is modest.** As a per‑candidate detector: among candidates the self‑report already calls good (self‑report ≥ its task median), flag the ones a **code‑only** probe scores low. Pooled (146 such candidates, 38 secretly‑below‑median), the probe reaches **AUROC 0.63 [95 % bootstrap CI 0.53–0.73]** while the self‑report's own score is **anti‑informative (0.42 < 0.5)** — inside the set it already trusts, higher self‑confidence is if anything a *worse* signal, the sharpest form of "the self‑report cannot police itself". The signal is **not code length**: residualising log‑length out of the features per fold leaves AUROC unchanged (0.62 → 0.63; length's marginal contribution −0.01 [−0.07, +0.04]) — the §4 control, passed again. Limits stated plainly: the AUROC is **modest and statistically tied with a code‑length heuristic** (0.55; the gap CI includes 0, and fusing the two adds nothing), and it is **spaceship‑dominated** (nomad n = 5 is uninformative). We therefore report this as a downstream **use** of the H1 signal — a length‑independent, self‑report‑independent reward‑hacking flag [cf. 2601.20103; 2604.01476; 2210.10760] — not a strong standalone detector.

## 7. Two more non‑levers

**Reasoning‑first does not help — not with a 14B teacher, nor with privileged‑information grounding.** A reasoning‑generation critic (analyse, then score) underperforms a scalar head overall (mean Spearman −0.15 vs −0.07). Teacher quality is a genuine hidden variable — a 7B → 14B teacher flips spaceship from −0.01 to +0.31 — so a weak‑teacher dismissal would be invalid; but the 14B gain does not generalise. We also tested the natural fix: give the teacher the *true grade* so it writes a **coherent** rationale (privileged‑information / hindsight), then distil. The rationales do become coherent, but on 231 labels the student **underfits** — default QLoRA collapses to the base model's zero‑shot behaviour (byte‑identical predictions); only aggressive training moves it off the base, and *then* grounding helps by **+0.047** (directionally validating the idea) yet the reasoning critic stays **~0.48 below the scalar readout**. Under poor compute a **frozen readout beats a trained reasoning critic**, precisely because it needs no expensive, underfitting generation training.

**Multi‑fidelity has no headroom in the affordable regime.** Before building Hyperband/ASHA machinery, we probe its headroom offline: from a candidate pool and a budget of *B* full‑eval‑equivalents, `single` = best of *B* random, `mf(self‑report)` = best of the top‑*B* by the free self‑report screen, `oracle` = pool max. Headroom (`mf − single`) is +0.015 (spaceship B=3), −0.000 (B=10), +0.000 (nomad), +0.044 (tps): essentially nil where evaluation is already affordable. The screen you would build is the free self‑report — which §5.1 already showed is a fine selector.

## 8. Two methodological pitfalls

- **Prompt‑truncation bug.** Code placed *before* the instruction block in a length‑limited prompt: truncation dropped the "analyse‑then‑score" instruction, the model **continued the code**, and the parser grabbed a random number — the reasoning critic *never ran* for a whole phase, invisible from metrics alone (only raw‑generation dumps revealed it).
- **Code‑length confound.** Shortening code to fit a critic's VRAM **collapsed the probe's ablated Spearman from +0.41 to +0.02** — the probe reads the code. A confound in one arm silently inverted another arm's headline. (A sibling of the same trap appears in §5.3: a statistically "significant" but negligible steering effect, tripped by over‑powered statistics on a dead readout — always read the effect size and the random control, not the p‑value.)

## 9. Limitations

Three tabular tasks, spaceship‑dominated (221 / 37 / 31 cards); the per‑task CIs on nomad and tps are wide, and we say so rather than average them away. The signal‑is‑there result is strong and now cross‑family; the not‑usable and detection results are load‑bearing on spaceship. Broadening to more (small) tasks is the natural next step but hits the compute wall that motivates the whole study — generating graded cards is itself expensive, and it must stay inside the fair contract (same generation environment as the existing pool), which rules out the easy fixes. Everything here is a *frozen‑critic* result; it does not speak to fine‑tuning the base, which the model‑agnostic premise excludes by design.

## 10. Conclusion

A frozen code‑LLM's representation **knows** more about an ML solution's eventual quality than the solution's own cheap self‑report — decodably, independently of code length, low‑dimensionally, and across model families. And it **cannot use** that knowledge to guide search under poor compute: it saves no evaluations, its deployment veto does not convert, and its quality direction cannot be steered; a trained reasoning critic and multi‑fidelity screening add nothing. The one thing it buys is a length‑independent flag for the failures the self‑report hides. The practical reading is the one AIRA_2 points to and we make single‑GPU and model‑agnostic: **the lever is clean, consistent evaluation, not a cleverer critic** — and the contribution of this paper is as much the set of cheap, adversarial, offline tests that *separate a real signal from a usable one* as any single number.

---

## Appendix

**Reproducibility.** `cards_real_mm.jsonl` (289 cards); frozen backbones in 4‑bit on one RTX 3090; ridge readout only. Seeds {0,1,2} (probe CV) / split seeds × draws (regret); dependency versions and commit pinned; one CSV row per run with all knobs, seeds, and metrics. External pristine grading only; no LLM‑as‑judge.

**Scripts.** `run_full_matrix.py` (`--ablate`) and `h1_ablation.py` (layer × ablation × length‑residual; `H1_MODEL` / `H1_LAYERS` env for the 4‑backbone sweep, §4); `a1b1_probe.py` (low‑dim subspace, §4); `budget_probe.py` (best‑of‑K, §5.1); `veto_sim.py` / `veto_realtrees.py` (random‑pool vs real‑tree veto + bootstrap, §5.2); `a3_steer.py` / `a3_steer2.py` (steering gate, greedy + sensitive soft readout, §5.3); `probe_rescue.py` / `b1_detector.py` / `b1_resid.py` (wrong‑pair rescue + deployable detector + length‑residualised bootstrap, §6); `mf_headroom.py` (multi‑fidelity headroom, §7); `build_cards.py` + `relabel_minmax.py` (data); `dump_reasoning.py` (§8 pitfall). Figures 1–6 in `figures.html`.

**Figures.** F1 self‑report ablation · F2 rank ≠ regret · F3 wrong‑pair rescue · F4 low‑dimensionality · F5 steering coefficient plot · F6 cross‑family replication.

**Key references.** aira‑dojo 2507.02554 · AIRA_2 2603.26499 · ELHSR 2505.12225 · OPENIA 2501.12934 · AutoProbe 2510.02934 · code ranker 2512.07404 · confidence manifold 2602.08159 · steering code 2603.23629 · reward‑hacking 2601.20103 / 2604.01476 · Goodhart 2210.10760 · length‑artifact caution 2606.02907.
