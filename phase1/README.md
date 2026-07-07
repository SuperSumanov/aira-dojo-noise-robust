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

跨任务 / 同任务（min-max 标签，各 3 折 × N × seed）— **自报分 baseline 两设置都碾压**：
| 预测器 | LOTO 跨任务 | INTRA 同任务 |
|---|---|---|
| **one_epoch（自报分）** | **+0.479** | **+0.450** |
| probe | +0.12~0.16 | **+0.40~0.50** |
| zeroshot / scalar | ≈0 | ≈0 / 负 |
| reasoning | −0.074（恒定） | 0.000（恒定） |

**baseline 设障（mask 掉自报分 `val_at_low`/`val_curve`/`parent_val`，只给代码+血缘）— 翻转裁决**：
| 预测器 | LOTO 跨任务 | INTRA 同任务 |
|---|---|---|
| one_epoch（baseline） | **0.000**（如期废） | **0.000** |
| **probe** | **+0.14**（tps_may 0.52） | **+0.357**（tps_may 0.57） |
| scalar | 个别折 +0.23~0.27 | +0.08~0.26 |
| zeroshot | +0.163 | +0.124 |

→ **去掉同源自报分后 baseline 归零，而 probe/scalar 保留可观信号** = **critic 有独立于自报分的价值**（从代码的 hidden 表示学到 grade 信号），同任务强、跨任务弱但为正。

**命题裁决（拆完 confound）**：
- 「廉价 critic 能预测 grade」**成立**：设障后 probe 同任务 +0.357 / 跨任务 +0.14 > 废掉的 baseline（0）——**Phase-1 的「learned 输 baseline」是 confound**（baseline=`val_at_low` 自报分与真值同源而虚高），并非 critic 无用；
- probe（冻结特征+ridge）**最稳**；scalar 去自报分后跨任务反而更好；**reasoning 仍退化**（7B 自蒸馏+截断+少样本，实现问题非方法问题）；
- 信号整体**偏弱**（真 grade 难 + 数据仅 148 卡，呼应 T0 R²≈0.14）。

**拆 confound 进度**：① 标签 medal→min-max ✅（tps_may 修复）② 同任务 intra 对照 ✅ ③ **baseline 设障 ✅**（去自报分→baseline 归零、probe/scalar 保留信号→critic 有独立价值，见上）④ 待做：修 reasoning（下 14B teacher 真蒸馏、不截断 code）。

**新方向（pivot → 仓库根 `0707_proposal_noise_aware.md`）**：从被动 grade critic 转向 **C1 噪声感知离线偏好蒸馏**——用树里同 parent 的 sibling 做偏好对，**只在分差 > 噪声地板 τ 时配对**（因 grade 噪声大，分差落噪声带内的偏好是假的），ORPO/SimPO 离线训 actor、零新采样。**M0/M1-dry 已在烧 GPU 前证伪现有数据够**：148 卡的树仅 **28 个 graded sibling 对**，无重复 grade（τ 由 T0 R²≈0.14 反推），τ 门控后剩 **5 对(1σ)/1 对(2σ)** → **扩数据是硬前置**（目标每任务几百对）。这也从数据侧印证 proposal 立论（sibling 分差多半落在噪声带内）。

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
