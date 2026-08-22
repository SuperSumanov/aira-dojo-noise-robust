# Score-channel confirmatory replay 完成审计（2026-08-19）

> **2026-08-23 解释纠正（不改历史机器裁决）：** 后续直接 truth-support audit 发现，158 个 selected parents
> 中 148 个 sibling `y_norm` 全并列；原 headline 的 6 common cards / 3 parents 中 3/3 的 truth 也全并列，
> non-tied common parent=0。故下文 formal `SCORE_CHANNEL_MECHANISM_KILL` 仍是预注册代码的原始输出，但
> `external=stdout=1.0` 是 vacuous tie credit，不能解释为两通道相等、external 失败或两者都能正确排序。
> 科学状态应读作 `DISCRIMINATIVE_COMMON_SUPPORT_ZERO`。完整纠正见
> `phase1/实验记录/2026-08-23/ScoreChannel_GroundingAvailability_正式结果与真值支持纠正.md`。

最终状态：`SCORE_CHANNEL_MECHANISM_KILL`；冻结 analyzer 与不导入 producer 的独立 verifier 均 rc=0，
postprocess 状态为 `COMPLETE_RESULTS_ANALYSIS_AND_INDEPENDENT_VERIFY_PASS`。正式 jobs 为
11127/11128/11129/11130，对应 frozen
shards 0/1/2/3 与 100/85/78/57 candidates；均在 gpu27、RTX3090 上于
`2026-08-18T13:39:18Z` 启动。worker source、approval、coverage 和 replay SHA 均沿用执行前冻结；没有重选
parent、改 cap、改 candidate code、调用 LLM API 或更新底座模型。

## 预注册 headline 裁决

320/320 planned replays 完整结束。320 个候选中 finite external score 为 15，keyed stdout self-report 为 92，
两通道同时存在为 7；严格同 parent common support 最终只有 6 cards / 3 parents / 3 physical runs / 3 tasks。
在这三个 parent 上，external 与 stdout 的 tie-aware top-1 credit 均为 1.0，差值为 0.0；run/task clustered
95% CI 均为 `[0.0, 0.0]`，run sign informative=0、双侧 p=1.0。预注册的正方向、run-CI 与 sign-test 三道门
均失败，因此不得提出“external score 通道优于 stdout self-report”的正方法主张。

这不是 replay 或 verifier 失败：完整性链全部通过。诚实的描述性发现是 120 秒下 external score 覆盖极低，
导致通道优劣估计几乎没有共同支持；它可作为 execution-cliff/selection-observability 的基准诊断，但不能
事后替换预注册 headline 或声称确认了外部分数优势。

直接证据保存在远端：

- `/research/d7/spc/yzyang4/score-channel-replay-20260818-approved-v2/postprocess/analysis/summary.json`；
- `/research/d7/spc/yzyang4/score-channel-replay-20260818-approved-v2/postprocess/independent_verification.json`；
- primary summary SHA=`3dc99bc8266cbe6abe33c89597b4c118c2ce211f3225c33df8c0d70f308178a5`；
- independent status=`VERIFIED_SCORE_CHANNEL_PROSPECTIVE_ANALYSIS`。

## Slurm 秒级取整修正

执行前计划给 shard 3 请求 `01:53:40`，但首次 `squeue` 在结果行仍为 0 时显示 Slurm 将其向上取整为
`01:54:00`。若不处理，四片理论分配加历史 20 秒会超过原 38,400 秒硬上限 20 秒。故在 job 11130 运行约
38 秒、尚无结果行时，用 `scontrol` 原地把 TimeLimit **降低**到 `01:53:00`；作业没有取消、重启或改变候选。

修正后四片 TimeLimit 秒数为 12,000/10,200/9,360/6,780，合计 38,340；加历史 fail-closed 20 秒为
38,360，较批准硬上限留 40 秒余量。远端 amendment receipt SHA=
`ba02fd171469b8b185754dcddfd17bd8fcfd4bc2bcfad69af68d6b4f7ee92147`。这项修正覆盖 preflight 中“Slurm 会保留
秒级 TimeLimit”的错误假设，但不覆盖其他冻结协议。

## 启动前最终门

- 完整数据 coverage SHA=`dd986c78a2f7f411ce16a1f1b757b7b8a77140aff99a36c9a311f7b81eeb8181`；
- approval SHA=`b107075810e5af0da084be087cfa70740cd846d198a155116a061599e3057e09`；
- worker commit=`ca3bb7315078f2c4bed99fa4c33d93c2f353d670`；
- preflight 报告 commit=`b1797dea6003d4790319d873133c97357297b36b` 在远端完整依赖环境为
  `384 passed in 33.84s`、rc=0；
- 第二次显式 submit 前 dry-count/test-only/secret/active-job 门全部重跑通过。

结果盲监控只在四片均终止、结果 SHA 固定、320/320 completeness 与执行后 17/17 数据覆盖双重验证通过后，
才一次性运行 frozen analyzer。四个 top-level jobs 全部 `COMPLETED 0:0`，实际 elapsed 分别为
`03:17:08`、`02:47:01`、`01:55:17`、`01:45:11`，均未触及各自 TimeLimit。
