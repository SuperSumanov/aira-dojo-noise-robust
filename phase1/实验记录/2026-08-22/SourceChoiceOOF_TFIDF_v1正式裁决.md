# SourceChoice OOF TF-IDF v1：正式裁决

日期：2026-08-22。正式状态：`NO_NARROW_POSITIVE`。本裁决关闭固定 char-TFIDF
source-choice predictor 这一条窄方法线；不外推为“所有模型都不可预测”，也不改变 score-channel 前瞻主线与
D&B/integrity benchmark 主张。

## 锁定链与输入

- 正式 producer 控制 commit：`11b7f23d2d91bc412c3a2e0c8cd7d6a23fbb5baf`；只读目录：
  `/research/d7/spc/yzyang4/source-choice-oof-tfidf/11b7f23-v1`；完成时间：
  `2026-08-21T19:28:13Z`。
- 独立 verifier commit：`9bed9c85dafc3707a58684097e30a42064eae3bf`；只读目录：
  `/research/d7/spc/yzyang4/source-choice-oof-verification/9bed9c8-on-11b7f23-v1`；完成时间：
  `2026-08-21T19:36:12Z`。
- exact-sign audit commit：`dd106275acb7a56c081bcddd49caff7bc4c20244`；只读目录：
  `/research/d7/spc/yzyang4/source-choice-oof-exact-sign-audit/dd10627-on-11b7f23-v1`；完成时间：
  `2026-08-21T19:40:43Z`。
- 正式 summary SHA-256：
  `4e5da9a357f7675f34928713604d82abf73d41bdcd348297a802ac68c3bf8fcf`；prediction SHA-256：
  `ffee4bafdc7b3301f1f8c64052d45e731b7ed13fdadb40589a22c24f17a52383`。
- 输入严格限于 S2 v2 train 和公开 cluster manifest；frozen/extension model 与 label vault 均未读。
  样本为 2,109 choice groups、5,739 unique candidates、23 tasks、275 physical runs；mixed-task runs、
  cross-task code hashes、cross-run code hashes 均为 0。共拟合 28 个冻结配置的 CPU 模型，GPU/API/base-LLM
  update 均为 0。

## 冻结 headline 结果

| split / 指标 | TF-IDF | exact uniform | delta | 95% clustered CI | task sign |
|---|---:|---:|---:|---:|---:|
| task-LOTO micro accuracy | `0.4016121384542437` | `0.4001780146516989` | `0.0014341238025448724` | run-cluster `[-0.026928473294010907, 0.03209627998879697]` | — |
| task-LOTO task-macro accuracy | `0.4587577147706667` | `0.4099340298087316` | `0.04882368496193506` | task-cluster `[-0.002818580653200905, 0.10637780689695644]` | `12+/11-/0`, one-sided `p=0.5` |
| run-grouped 5-fold micro accuracy | `0.4144144144144144` | `0.4001780146516989` | `0.014236399762715573` | run-cluster `[-0.010765587398163913, 0.042475689286202156]` | — |
| run-grouped 5-fold task-macro accuracy | `0.46183422441070165` | `0.4099340298087316` | `0.051900194601970095` | task-cluster `[0.010357110375943576, 0.09639269016400835]` | `15+/8-/0`, one-sided `p=0.10501980781555176` |

task-LOTO 的 primary gate 因 task-cluster CI 下界不大于 0 且 sign `p` 不小于 0.05 而失败。run-only gate
虽有正的 task-macro CI，却因 run-clustered micro CI 下界不大于 0 而失败。机器输出中的
`cross_task_pass=false`、`run_only_pass=false` 与 `NO_NARROW_POSITIVE` 因而一致。

结果前新增的有理数 exact-sign audit 没有改变裁决：task-LOTO 精确计数为 `12+/11-/0`，
`p=4194304/8388608=0.5`；run-grouped 5-fold 为 `15+/8-/0`，
`p=880970/8388608=0.10501980781555176`。它还确认没有数学上恰为零却被 binary float 错分的 task。

## Controls 与一个独立机制线索

winner oracle 在两个 split 的 top-1 accuracy 均为 `1.0`，证明评估链可检出强正信号。min-SHA 与
max-code-length controls 没有稳定正信号。预注册的 deterministic `max_step_then_min_sha` control 则得到：

- task-macro delta=`0.03755268823459413`，task-cluster CI=
  `[0.003178139904469143, 0.07802102179810541]`；
- task sign=`17+/5-/1`，one-sided `p=0.00845026969909668`；
- micro delta=`0.016133033238296412`，run-cluster CI=
  `[-0.005012731663295798, 0.03761184711470949]`。

这不改变 TF-IDF 的预注册 gate，也不能作为事后 model rescue。它是 D&B/integrity 线的独立描述性线索：source
selection outcome 与 candidate 的 logged search step 存在跨任务关联，但 micro/run-cluster 不稳定，而且完整
parent 的所有 child 是否在对应决策时刻同时可用尚未由当前材料证明。后续只能在不读取 frozen label 的前提下先做
temporal-availability 审计，再由严格未来 cohort 验证；在此之前不得称为可部署 selector 或 search speedup。

## 复现、失败记录与完整性

- producer A/B 的结果逐字节一致，`result_reproducibility.diff`=0；两个 producer stderr=0；正式完整测试为
  `707 passed, 32 warnings in 54.03s`。两次 producer wall time 分别为 `1:31:47` 与 `1:33:21`。
- independent verifier 不 import producer、不 refit 模型，从 21,090 prediction rows、28 个 fit receipts 独立重建
  split、controls、metrics 与 gate；双跑逐字节一致，`verification_reproducibility.diff`=0，两个 stderr=0，
  verifier 状态为 `INDEPENDENT_SOURCE_CHOICE_OOF_TFIDF_VERIFIED`。
- exact-sign audit 双跑逐字节一致，`audit_reproducibility.diff`=0，两个 stderr=0；reported/exact verdict 均为
  `NO_NARROW_POSITIVE`。
- 三层正式目录权限为 `0500`，结果文件为 `0400`；forbidden scientific/vault path hits、credential
  filename/content hits、worktree drift 均为 0。
- exact-sign runner 首次封装因工作目录错误在任何科学输出前 fail-closed；旧 staging 原样保留。唯一修复只是先
  `cd` 到锁定 worktree，详见 `SourceChoiceOOF_ExactSign首轮封装失败与修复.md`。

## 科学裁决与后续

固定 char-TFIDF 不能在冻结的 task-LOTO/run-OOF 门下证明稳定 source-choice signal；该窄方法线至此关闭，禁止换
模型、换阈值、删任务或挑 source-size 追救。按已冻结 activation contract，recovery-provenance sensitivity 与
frozen/extension prediction escrow 均不激活，且实际没有运行。

这不是数据资产的失败。正式结果反而把三件事拆开：（1）source winner 可物化与可审计；（2）logged step 等协议
变量可能携带选择机制信号；（3）只读候选代码的简单 OOF ranker 尚无稳定证据。结合 RPM/FOREAGENT 已覆盖的广义
candidate preference，本项目下一步只保留：严格前瞻 score-channel 复现，以及以真实 logged topology、failure/
unknown preservation、dependency-aware inference、temporal frozen、成本和撤回链为核心的 D&B/integrity benchmark。
