# phase1 — cheap-signal value critics for MLE candidates (offline study)

**Question.** Under **few + expensive** labels (a candidate's *true* score = an MLE-bench external
grade, which costs a full train+grade), can a **reasoning-first-then-value** critic predict that
score more sample-efficiently / better-calibrated than a bare scalar head, a zero-shot frozen model,
a frozen-representation probe, and two trivial early-signal baselines?

This module is **offline and self-contained**: it turns aira-dojo runs into *cards*, then trains /
evaluates six predictors and reports sample-efficiency, ranking, and calibration. **It does not change
any aira-dojo core behavior — all code lives in `phase1/`.**

---

## 实验记录与当前进度（2026-07-07）

> 完整版见仓库根 `phase1_进度报告_20260707.md`；此处为 README 内的浓缩记录。

**核心思路**：搜索里评估一个候选解很贵（要跑满 train+grade 才知真实 MLE-bench 分）。用**廉价信号**（自报验证分、代码、血缘）预测它的真实 grade，让搜索省评估预算；重点检验**「先自然语言分析、再出分」的 reasoning critic 是否更省样本**。硬约束：不微调底座、只用可验证信号（无 LLM-as-judge）、reasoning 单前向无投票、aira-dojo 核心零改动、单卡 3090 用 7B QLoRA-4bit。

**数据**：把真实搜索树 `journal.jsonl` 的每个候选解节点变成一张 card（schema 见下）。当前 **148 卡 / 3 任务**：spaceship-titanic 90（二分类）、nomad2018 37（回归）、tps_may 21（二分类）。标签用 **per-task min-max graded**（medal 阈值会把「都没拿奖」的任务压成常数标签，已弃用）。

**里程碑**：
- **P1a（mock 骨架）** ✅ 全绿：合成数据端到端跑通、`pytest` 12 passed；
- **P1b（真 Qwen 后端）** ✅ 4 臂逐个跑通（7B 4-bit：load 42s / 6GB / gen 1s）。

**结果（诚实，含负结果）**

同任务（intra，spaceship 90，6:4 split）— H1 初步成立：
| one_epoch | zeroshot | scalar | reasoning | probe |
|---|---|---|---|---|
| +0.136 | **+0.227** | +0.190 | +0.104 | −0.106 |

跨任务（LOTO，首轮 medal 标签）— learned 全输给廉价 baseline：
| 预测器 | spaceship | nomad |
|---|---|---|
| **one_epoch** | **+0.238** | **+0.455** |
| zeroshot / scalar / reasoning | ≈0 / 负 | ≈0 / 负 |

**命题分裂 & confound**：
- 「廉价 critic 能预测 grade」**同任务成立**，跨任务几乎无信号（连冻结大模型 zeroshot 都 ≈0）；
- 「跨任务 learned > baseline」首轮**证伪**，但 baseline=自报分与真值**同源**而极强 + 跨任务最难 + 数据仅 148 卡 + tps_may 曾是无效折 → 不利结果**站不住脚当结论**；
- 「reasoning 更省样本」**尚未显出**（弱且疑退化），有强 confound，暂**不下结论**。

**正在拆 confound**：① 标签 medal→min-max（tps_may 修复）② 加同任务 intra 对照 ③ 两个矩阵跑中（loto + intra，min-max 标签）④ 待做：给 baseline 设障（去掉自报分、只给代码/血缘）、诊断 reasoning 是否退化成常数。

**副产物**：修了 aira 一个执行 bug——agent 代码用 `if __name__=="__main__"` guard 时被误判 buggy（`src/dojo/core/interpreters/python.py:189` exec 前加 `global_scope["__name__"]="__main__"`），采树 grade 产出率 5%→33%。

## The six predictors

| name | uses labels? | what it is | backend (mock → real) |
|------|:---:|---|---|
| `one_epoch` | no | rank by the cheap self-reported `val_at_low` (ArchPilot 1-epoch/10%-data proxy) | numpy (final) |
| `asha` | no | learning-curve extrapolation of `val_curve` (ASHA/curve-fit) | numpy (final) |
| `zeroshot` (a) | no | **frozen** Qwen2.5-Coder-14B, single forward, parse `SCORE:` | fixed heuristic → 14B AWQ/8-bit |
| `scalar` (b) | yes | Qwen2.5-Coder-**7B** QLoRA + scalar head, MSE + pairwise rank | ridge on features → 7B QLoRA |
| `reasoning` (c) | yes | **same 7B**, SFT to emit *analysis → `predicted_final_score`*, single forward | residual ridge → 7B QLoRA SFT |
| `probe` (d) | yes | **frozen** Qwen hidden-state + token-entropy → linear/MLP probe | random-proj + ridge → frozen feats |

(b) and (c) **share the same 7B base** so any gap is attributable to the reasoning-then-value format,
not the backbone. **Hard constraints honored:** open-source Qwen only; closed-world; only verifiable
signals (**no LLM-as-judge anywhere**); reasoning critic = **one forward pass, no multi-sample
voting**; 7B via QLoRA 4-bit, 14B via 8-bit/AWQ.

## Layout

```
phase1/
  cards.py         Card schema + numeric featurizer + journal.jsonl parser + label-hiding
  dataset.py       LOTO folds + label-budget sub-sampling (N∈{25,50,100,200,all}) + seeds
  critics/         base.py (Critic ABC + closed-form Ridge), baselines.py, zeroshot/scalar/reasoning/probe.py
  eval/            metrics.py (spearman/kendall/top-k regret/ECE + bootstrap CI), runner.py, plots.py
  mock/            generate.py — synthetic cards (seeded) so the whole pipeline runs on CPU in seconds
  smoke.py         end-to-end acceptance driver (mock → 6 predictors → CSV + table + plots)
  tests/           pytest gate (smoke + metric known-answers + card round-trip/label-hiding)
  Makefile         `make -C phase1 smoke | quick | test`
```

## Run the acceptance gate (Phase 1a — mock only, no downloads)

From the aira-dojo repo root:

```bash
python -m phase1.smoke           # full mock sweep  → phase1/_smoke_out/{runs.csv, sample_eff_*.png/.csv}
python -m phase1.smoke --quick   # tiny (seconds)
python -m pytest phase1/tests -q # gate
# or: make -C phase1 smoke  /  make -C phase1 test
```

Requires only **numpy** (matplotlib optional — without it the plot *data* CSV is still written, the
PNG is skipped). What the gate asserts: all 6 predictors emit finite scores for every
predictor×budget×seed×LOTO-fold; artifacts are written; and — as a synthetic-signal sanity check —
learned critics clear a near-zero floor at the largest budget while the three label-free predictors
stay flat across N. **It does not assert which critic wins** — that is the empirical question for the
real run.

### Reading the output
- `runs.csv`: **one row per run** — `predictor,budget,seed,task,n_train,n_test,commit` + every metric.
- `sample_eff_<metric>.png` / `.csv`: metric vs label budget N, one line per predictor with a
  bootstrap 95% CI band (the sample-efficiency curve — the headline result shape).
- console: a compact median-Spearman table (predictors × budgets).

## What the mock backends are (and are NOT)

The mock backends are **plumbing with distinct inductive biases**, not evidence. The synthetic label
depends on a latent quality `q` (which the cheap `val_at_low` sees noisily) **and** on op/depth
structure that `val_at_low` misses — so a learned critic *can* beat the baselines and *improve* with
N, letting the harness demonstrate it can measure sample efficiency. `reasoning`'s mock uses
residual-on-the-cheap-signal learning (lower-variance target → tends to lead at small N);
`probe`'s mock uses a frozen random projection. **These stand-ins only exercise the pipeline; the real
comparison uses the Qwen backends below.** No mock arm is claimed to predict the real ranking.

## Real-data path (dry-runnable now; execution = Phase 1b)

1. **Cards from real runs.** `phase1.cards.parse_journal(path_to_checkpoint/journal.jsonl, TaskInfo(...))`
   builds cards offline from an aira-dojo run: `label.graded` = `metric_info["score"]` (external
   MLE-bench grade), thresholds from `metric_info["{gold,silver,bronze}_threshold"]`,
   `obs.val_at_low` = self-reported `validation_score`, lineage/op/depth from the node. Save with
   `save_cards`. Then `run_sweep(cards, backend="qwen")`.
2. **Qwen backends** (each critic's `_fit_qwen`/`_predict_qwen`, currently a documented
   `NotImplementedError`): `zeroshot` = frozen 14B AWQ, value prompt from `Card.view()`, parse
   `SCORE:`; `scalar` = 7B QLoRA + scalar head (MSE + pairwise hinge, grad-accum for a 3090);
   `probe` = cache frozen 7B/14B hidden-state + token-entropy features per card, fit a linear/MLP
   probe; `reasoning` = **hindsight distillation** — a frozen 14B writes an analysis for a card whose
   *true* `y_norm` is known, the number is stripped from its text, and `y_norm` is appended as the
   supervised target, then QLoRA-SFT the 7B to emit `analysis … \n predicted_final_score: x.xx`;
   predict = one forward, parse the number.

### Assumptions / TODO (do not fabricate)
1. **[confirmed] Obs/label semantics = option B**: one aira-dojo node = one run; `obs` = the
   candidate's self-reported validation at the agent's fidelity; `label.graded` = that same run's
   external MLE-bench grade.
2. **aira-dojo records no explicit fidelity / validation curve.** `obs.fidelity` (epochs, data_frac)
   and `obs.val_curve` are therefore left empty by `parse_journal` (marked `TODO` in `cards.py`).
   Populating them requires injecting lightweight logging into the generated solution code — a
   separate, opt-in change **outside** the aira-dojo core (a wrapper), not done this round. The
   featurizer and `asha` baseline degrade gracefully to `val_at_low` when the curve is absent.
3. Label normalization uses medal thresholds (`normalize_graded`); if a run lacks thresholds,
   `y_norm` is `None` and the card is dropped from the labeled set (documented degraded path).

## Reproducibility
Everything is seeded (numpy default_rng). `runs.csv` records seed, budget, predictor (arm), and a
`commit` column (pass the aira-dojo git commit via `run_sweep(..., commit=...)`; mock runs write
`"mock"`). Report **median + bootstrap CI across seeds×folds**, never a single number.

## Dependencies
- **mock smoke / gate:** `numpy` (required), `matplotlib` (optional, for PNGs), `pytest` (dev).
- **real backends (Phase 1b):** `torch`, `transformers`, `peft`, `accelerate`, `bitsandbytes` (7B
  QLoRA), AWQ weights for the 14B. Installed only when running `backend="qwen"`.
