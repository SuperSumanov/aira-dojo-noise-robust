# Score-channel：raw grade 与 `y_norm` ordering alias 结果前冻结

日期：2026-08-23；冻结 UTC：2026-08-22T20:49:03Z。状态：
`FROZEN_POST_HOC_RAW_GRADE_NOT_READ`。本分析只针对 outcome 已知的旧 158-parent cohort，不能改变旧 primary verdict，
也不授权打开当前 future truth vault、提交 replay、GPU、API 或 model fit。

## 1. 为什么必须在新 truth 前查这一层

旧 direct truth-support audit 已知 148/158 parents 的 `y_norm` 全并列，3 个 common-channel parents 也全部并列；
但它没有区分真实 external grade 同分与 normalization alias。源码审计现已确认两层分辨率变换：

1. 固定 MLE-bench commit `507f92e1138bb6e40dac5c6ee7a6758e6424bf97` 的 `Grader.__call__` 明确执行
   `round(score, 5)`；`grade_helpers.py` SHA-256=
   `7d55512a893699b2e17041f3cd3bd0c2aba955c73f50872b3c69238546b87005`；
2. `phase1/cards.py::normalize_graded` 再按 medal thresholds 线性变换并裁到 `[0,1]`。因此所有低于下锚点的弱
   candidate 都写成 `y_norm=0`，所有超过 gold 的都写成 1，即使五位小数官方 raw grade 仍不同。

这不是恢复未四舍五入分数的计划；当前 archive 中的 `graded` 已是官方五位小数输出，unrounded score 不可恢复。
问题只是在同一 task、同一 parent 内，是否又被 `y_norm` clipping 额外抹掉了可排序性。

## 2. 已知与未知严格分开

冻结前已知：selected parents/candidates=158/320，`y_norm` tied/nontied=148/10，common comparative=3，
common `y_norm` nontied=0。冻结前未知且未读：raw `graded` informative parent 数、`y_norm` tied 但 raw distinct 的
alias 数、common parent 在 raw truth 下是否可辨识、以及其描述性 channel credit。机器协议把这些 timing facts 写死；
协议 SHA-256=`b917182570fd3484b87457b9185d5220eef3bc5fdda5030e847897a3c7f052cd`。

## 3. 固定 estimand 与裁决

- raw informative：同一 selected sibling set 的 `max(graded)-min(graded)>1e-12`；
- normalized informative：同一集合 `max(y_norm)-min(y_norm)>1e-12`；
- alias：normalized tied、raw informative；反向情形必须为 0，否则 fail closed；
- normalized tie 再固定分成 all-zero、all-one、interior；
- common channel 仍要求至少两名 sibling 同时有 finite pristine external 与 keyed finite stdout；只在 common raw
  informative parent 上给 task-oriented、tie-aware top-1 描述值；
- 不输出 card-level raw grade、`y_norm`、channel value 或 winner。

material alias 门固定为 alias parents≥16 且涉及 tasks≥4。通过只允许在当前 future vault 打开前**另名追加**
raw-grade truth-support estimand，并保留原冻结 `y_norm` gate 原样报告；不通过则不改 future gate。无论结果如何，旧
machine verdict 不变、方法正主张不允许。

## 4. 输入与复现

selection、replay、approval、orientation 与四个 result shards 沿用旧正式 SHA，producer/verifier 均逐项复核；
verifier 不导入 producer，独立重建 vault identity、raw/normalized support、boundary、common support 与 tie-aware
credit。合成测试覆盖 alias、共同覆盖正控制、反向不可能状态、candidate reuse 和五位小数网格，共 5/5 通过。

## 5. 预飞

1. 只改变 truth representation 审计，不改变 candidate/parent/task/cap；
2. 旧 aggregate 已知，明确标 post-hoc；
3. 全部输入按 SHA 绑定；
4. raw 与 normalized 在相同 sibling set 比较；
5. 不按结果选 task/subset；
6. no training/checkpoint；
7. 当前 future vault 路径不作为参数；
8. 无随机数与 bootstrap；
9. 提交前做文件名与高置信内容凭据扫描；
10. CPU-only，GPU/API/model fit 均为 0；
11. known aggregate、grader commit/SHA、五位小数语句任一不符即 fail closed；
12. producer×2、verifier×2 必须逐字节一致；
13. 只有 protocol/code/tests/report commit+push 并经 fresh exact-commit 测试后才允许真实旧输入运行。

## 6. 结果后追加：正式审计

结果前代码与协议先以 commit `5e3ebcd571676cd55188bf22ad7265b34b7dc1b8` push，并在 fresh no-smudge
exact-commit worktree 通过聚焦 5/5、完整 791/791（33 warnings）后，才打开旧 cohort 的 raw `graded` 聚合。
producer×2、独立 verifier×2 均逐字节一致；future truth forbidden-open、文件名与高置信内容凭据扫描均为 0。

正式结果：

- selected parents/candidates/tasks=`158/320/17`；
- official five-decimal raw `graded`：non-tied=`157`、tied=`1`；
- `y_norm`：non-tied=`10`、tied=`148`；
- normalized tied 但 raw non-tied 的 alias parents=`147`，涉及 tasks=`16`；
- normalized non-tied 但 raw tied 的反向不可能状态=`0`；
- 148 个 normalized ties 中 all-zero=`128`、all-one=`20`、interior=`0`；
- 五位小数网格违规=`0`；
- common comparative parents=`3`，三者在 raw truth 下均 non-tied；external/stdout 描述性 top-1 credit
  均为 `1.0`，delta=`0.0`。

冻结 material gate 的 parent/task 两项均通过，状态=`MATERIAL_Y_NORM_ALIASING`。这证明旧“148/158 truth ties”
主要是我方 medal-threshold clipping 的 measurement alias，而非官方 grade 本身缺乏分辨率；但 common support 仍仅
3 parents，不能据此声称 external 优于 stdout，也不能反转旧 primary/KILL。下一步严格按冻结权限，只在 future
vault 打开前追加另名 raw-grade support estimand，并保留原 `y_norm` gate 原样。

正式 analysis SHA-256=`38788c89ca8231428482d9bea1a43e5a641eda7a6efa26dec89eb6499e594ba5`；独立 verification
SHA-256=`4b56b9e2e3cb9c52f390dd92b3877f818ef7b2edecc27cde919c06a09fb22789`。聚合证据保存于
`phase1/results/score_channel_truth_aliasing_audit_20260823/`。
