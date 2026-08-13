# Probe-First Contract Safety/Discovery V2：设计草案

日期：2026-08-13
状态：**设计与预算预览；尚未预注册、未调用 API、未提交 GPU**

## 唯一问题

在从未用于 V1/V2 feasibility 或无效 A/B 10637 的全新 task×seed blocks 上，只向 draft prompt 增加冻结的
progressive artifact contract，是否相对 original prompt：

1. 提高 host 120 秒内 candidate-specific、schema-valid、finite-pristine-score artifact 的覆盖；
2. 不降低 full-like validity；
3. 不造成方向性 full-quality 损害。

该实验仍是 safety/discovery，不是 search utility confirmation。SPT identity tap 已关闭；本实验测试的是主动
low-fidelity candidate generation，不宣称 same-code semantics。

## 候选矩阵（待最终 public-data 与 Hydra 预检后冻结）

固定新 seed，8 tasks × original/contract = 16 generation entries；每个 task 的两臂同时启动，arm order 交替。
候选任务均未出现在 V1、V2 feasibility 或 job 10637 的六任务矩阵中：

| task | modality / metric direction | public-data footprint | 角色 |
|---|---|---:|---|
| aerial-cactus-identification | image binary, higher | 19.2 MB | small image |
| denoising-dirty-documents | image restoration, lower | 100.4 MB | non-tabular regression |
| learning-agency-lab-automated-essay-scoring-2 | text ordinal, higher | 36.2 MB | long text |
| mlsp-2013-birds | audio multilabel, higher | 661.1 MB | audio |
| petfinder-pawpularity-score | image/tabular regression, lower | 1.04 GB | mixed modality |
| random-acts-of-pizza | JSON text binary, higher | 12.7 MB | text |
| us-patent-phrase-to-phrase-matching | text similarity, higher | 2.2 MB | text pair |
| whale-categorization-playground | image multiclass, higher | 283.8 MB | large-class image |

最终冻结前必须自动验证 sample submission 的实际文件名与 loader 支持；不能因为某任务失败而 outcome 后替换。
这里选择 8 blocks 是为了 discovery 分母更稳，不用于显著性宣称。

## 公平契约与新增防错门

- 唯一允许变化的是 draft system prompt 中固定 artifact-contract block；底座、seed、analyze/debug/improve、
  step/debug/time budget、容器、GPU、public data、grader、启动时间与 request order 均固定；
- 两臂各获得同样一次 conditional debug，首次 valid candidate 后停止；失败、timeout、invalid 全进分母；
- resolved-config comparison 只允许三类预期差异：draft prompt、`solver.exp_name`、
  `solver.checkpoint_path`。其余字段逐项 fail-closed；尤其 `step_limit/execution_timeout/client` 变动必须触发测试失败；
- candidate 只挂 public data，不见 pristine grader、private label 或分数；grader 只在 snapshot 稳定、candidate
  停止后运行；
- `decision_frozen_v11_b*` 和历史 `decision_clean_b*` 完全不读取；
- full-quality 非劣必须按公开 metric direction 逐 task 配对，不把 missing pair complete-case 成总体；
- generation manifest builder 与 scientific validator 分开保存 rc；任何 infrastructure/provenance 失败仍为
  `INVALID`，但不再把 run identity 误报为 confound。

## 预期门（正式 launch 前还需冻结精确数字）

- compliance：contract 合法 probe 至少 6/8；
- coverage：contract coverage@120 至少 6/8，且 paired net gain 至少 3 blocks；
- full validity：contract 比 original 最多少 1 block；
- quality safety：至少 4 个 paired full scores；方向修正相对差 median ≥ -0.05，`<-0.10` catastrophic harm
  最多 1 task；
- 只有全部通过才进入多 seed/多 candidate fixed-budget utility；否则按预注册分别裁决
  `NO_COVERAGE_GAIN`、`QUALITY_KILL`、`INCONCLUSIVE` 或 `INVALID`。

## 预算预览与 ETA

- generation：16 entries，每个 candidate execution cap 600 s；candidate 上限 2.67 GPU·h；
- replay：16 entries × 600 s，上限 2.67 GPU·h；
- 合计 candidate 上限 5.33 GPU·h；建议 `4×RTX3090`、两波/四波并发，scheduler hard cap 不超过
  12 GPU·h；
- API：每 entry 最多 draft+debug 与对应 analysis，最多 64 logical usage records；正式提交前先由远端 balance
  guard fail-closed，并单列实际 token/cost；
- ETA：队列外约 3—5 小时可出冻结 verdict；若任一 cheap/Hydra/data/secret gate 不通过则不提交。

在用户批准长实验前，只完成代码、fixture、resolved-config 审计和精确矩阵/预算；不启动该 GPU/API 批次。
