# First-960 结构权重时序外延 404：正式裁决

日期：2026-08-27

运行状态：`FORMAL_STRUCTURAL_WEIGHT_EXTENSION_PASS`

科学裁决：`ROBUST_OPPORTUNITY_YIELD_CLAIM_NO_GO`

固定 snapshot：`ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e`

结果前公开源码 commit：`7b9ddf64efcbf75107e3bdc7846d7467454ddc90`

## 结论

404-run 外延确认了一个较窄的描述事实：physical-run 的任务分布继续变均衡时，pair-micro benchmark 的任务权重仍然更集中。
first240→first404：

- run-HHI：`0.05597222222222222 → 0.047532104695618076`，差
  `-0.008440117526604146`；
- pair-HHI：`0.08303759912408124 → 0.12479008004370566`，差
  `+0.04175248091962443`；
- dominant pair-task share：`0.1714990746452807 → 0.2947295423023578`；
- 360/380/400/404 四个固定检查点全部保留反转；ad0b 重建 first339 与 first404 也都保留方向。

但预注册的稳健机制主张没有成立，不能称为“非单批次 artifact”或“opportunity yield 在两个指标上均为主要机制”：

- 最大单 drop attribution=`1.0617531614480789`，超过 `<0.5` 门；删除该 drop 后 pair-HHI 差变成
  `-0.002578347695087399`，反转消失；
- 31 个 leave-one-task-out 中 30 个保留反转，但删除 dominant OSIC task 后 pair-HHI 差为
  `-0.0018797549643278927`，因此包含 dominant-deletion 条款的 E3 失败；
- opportunity-yield 对 pair-HHI 正增量的 Shapley fraction=`0.5991375958702558`，但对 run→pair TV 仅
  `0.44105064109821923`，E4 的双指标门失败。

最强允许表述是：**run-level coverage 与 pair-level benchmark weight 可以持续背离，但当前 404-run 幅度及其机制解释仍由
OSIC 的高 decision yield、特别是一个 0820 drop 强烈驱动。** 这支持发布 task-macro、pair-micro、drop leverage 与层级 provenance，
不支持宣称一个跨任务稳健的 opportunity-yield 定律，也不提供 predictor accuracy、方法优越性或 search utility。

## 结果前固定门

| 门 | 裁决 | 观测值 |
|---|---|---|
| E1 extension 时序持续性 | PASS | 360/380/400/404=`4/4` |
| E2 无单 drop artifact | **FAIL** | max attribution=`1.0617531614480789` |
| E3 单任务稳健性 | **FAIL** | `30/31`，但 dominant OSIC deletion 不保留 |
| E4 yield 为主要机制 | **FAIL** | pair-HHI=`0.5991375958702558`；TV=`0.44105064109821923` |
| E5 版本内方向一致 | PASS | reconstructed first339 与 first404 均反转 |

失败 E2 的固定批次为
`0820-osic-pulmonary-fibrosis-progression-8seeds-4c1127356fce21d7`，只删除 first240 之后属于该批次的 5 runs。
第二高 attribution=`0.2704785924588167`，来自 0822 OSIC drop；这并不能 rescue E2。dominant-task deletion 是
唯一失败的 task deletion；`30/31` 的高比例也不能绕过预注册的 dominant-deletion 必须通过条款。

## 版本敏感性

provisional chronology 会被晚到的早期 run 重排，因此旧 7cda first339 与 ad0b 重建 first339 从未被声明为逐字节同一 cohort。
两者差值为：run-HHI `+0.0008527597218959126`、pair-HHI `+0.0003201852947791184`、pair max share
`-0.0003560037604609656`（旧值减重建值）。方向一致，但不能称严格 append-only held-out extension；closure 后必须按同一协议重跑。

## 复验与安全

- producer A/B（不同 `PYTHONHASHSEED`）逐字节相同；
- 不 import extension producer 的 verifier A/B 逐字节相同；
- focused=`12 passed in 2.43s`；full=`1225 passed, 47 warnings in 80.95s`；
- exact-path syscall audit：forbidden opens=`0`；
- commit filename/blob/result credential hits=`0/0/0`；
- label/outcome/prediction/raw archive 未打开；GPU/API/model fit/base-LLM update=`0/0/0/0`。

第一次正式 attempt 的测试全部通过，但 producer 尚未生成 trajectory 就因绝对脚本入口无法 import `phase1` 而 fail-closed；v2 仅改为
Python module 入口，从全新 worktree 和输出目录完整重跑。详见 `failure_history.md`。

关键 SHA-256：

- `trajectory.json`：`2dbd96452efe07a0e8edbcd4dc7e14daf8d45503c601712b49f3425c1a5d304c`
- `independent_verification.json`：`d31a3ff38f291ee674e7307bfc134d711fa1204ed49a6c0c01ecd08da2e74f62`
- `headline_metrics.json`：`7535a647df1fd9afa8ace16e4e0f301fcd82a1e2e05e6d333b660794d57658c8`

`trajectory.json` 保留完整 1..404 prefix、固定 milestones、Shapley/midpoint 分解及逐 drop/task 攻击；其余文件保留独立验证、
preflight、测试、路径与安全收据。
