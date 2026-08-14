# Disagreement-triggered selective execution：回顾性发现裁决

日期：2026-08-14。冻结协议：`selective_execution_v11_retrospective_discovery_v1`；科学 commit：
`7a1562a4506f17d713467956c797fb0d3226a8c5`。

## 裁决

正式状态为 **`SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK`**，margin 子裁决为
**`MARGIN_ENRICHMENT_NOT_SUPPORTED`**。三个异构 critic 的 disagreement abstention 没有把 v11 的弱
全覆盖信号变成 task/run 稳健的安全删执行策略；不得把 q=0.05 的事后可见描述点改成新 headline。

| 指标 | 正式结果 | 冻结门 | 状态 |
|---|---:|---:|---|
| selected support | 293 parents / 129 runs / 22 tasks | ≥228 / ≥100 / ≥20 | PASS |
| dominant selected task | 0.22866894197952217 | ≤0.25 | PASS |
| 候选数节省 | 0.09638157894736842 | ≥0.075 | PASS |
| pair-micro accuracy | 0.5494880546075085 | ≥0.58 | FAIL |
| run-macro accuracy [95% CI] | 0.5572152868664496 [0.48208440999138674, 0.6329395841023748] | point≥0.58，lower>0.50 | FAIL |
| task-macro accuracy [95% CI] | 0.5575913930507589 [0.4780537058575693, 0.6436459274377935] | point≥0.58，lower>0.50 | FAIL |
| 对 matched char-margin 的 task delta [CI] | +0.03502779307071244 [-0.05286426757718625, 0.13190540852024105] | ≥0.02，lower>0 | FAIL |
| selected gap-weighted accuracy | 0.5862908111622546 | ≥0.60 | FAIL |
| task-macro total-gap loss | 0.07444621155355517 | ≤0.08 | PASS |

所有 integrity gates 通过：4,263-row input SHA exact；1,520 exact-two parents / 294 runs / 23 tasks；
orientation oracle accuracy=1、gap loss=0；deterministic random 在 `[0.47,0.53]`；
`frozen_or_first960_read=false`。leave-one-task-out task-macro 范围为
`[0.5365243165293665,0.5722386022436522]`，说明失败不是删掉一个任务就可反转。最大的 selected task
`us-patent-phrase-to-phrase-matching` 有 67 个 decision，accuracy 仅 0.4925373134328358；同时任务间从
0.25 到 1.0 高度异质，不能只展示正任务。

## 风险曲线为什么不能救本轮

固定描述曲线在 q=0.05 时为 65 parents / 18 tasks、micro=0.6461538461538462、task-macro=
0.6388888888888888；但它只节省 0.02138157894736842 的候选执行，低于主协议 support 与节省门，而且
q=0.05 不是裁决 operating point。q=0.10 已降到 micro=0.5785714285714286、task-macro=
0.5844860947133674；q=0.20 的正式双聚类区间跨 chance。按预注册，禁止改 q、删 task 或换 vote 集合追认。

更关键的是，在相同 unanimous pool 内，margin top-q 相对 deterministic CRC subset 的 task delta 为
`-0.03710220722646631`，CI=`[-0.1020062027524714,0.023704664553946854]`。所以低覆盖高点不能解释为
margin 已校准；它可能只是小样本波动。

## 归档与工程失败

producer runtime 为 3.257731000194326 秒；GPU=0、API=0。独立 verifier 不 import producer，重建全部
central numbers、selected IDs、bootstrap、gates 与 verdict，输出
`INDEPENDENT_SELECTIVE_EXECUTION_VERIFY_PASS`。

首次 launcher 在 producer/verifier 都 rc=0 后才因 manifest 自引用失败：`sha256sum -c` 的输出继续追加
到已经进入 manifest 的 `run.log`。错误 manifest 原样保留；repair commit
`98065c85c1900c6b1ba1e0632204ab8ad63d44db` 只关闭日志 FD、增加 postflight-only 修复器。正式 staging
只重新生成 manifest 并原子提升，producer/verifier 均未重跑。该工程失败不能改变科学 no-unlock。

## 允许与禁止的解释

允许：在当前三个弱、task-heterogeneous critic 上，简单 unanimity + margin abstention 不能提供稳健的约
10% 候选数节省；selective prediction 本身又已被 FOREAGENT/CIPHER/CORA 等先例覆盖，因此本路线关闭。

禁止：不能说所有 selective execution、所有 uncertainty 或未来更强 critic 都无效；也不能把候选数节省
换算成 GPU-time speedup。下一步回到稳定主线：继续盲收 first-960 prospective runs、完善 run-clean
benchmark 与可靠 provenance；新方法必须改变可学习信号或标签，而不是在同一 OOF margin 上再调 abstention。
