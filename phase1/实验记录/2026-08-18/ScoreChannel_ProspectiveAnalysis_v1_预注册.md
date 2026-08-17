# Score-channel prospective analysis v1：结果前冻结

状态：`IMPLEMENTED_NOT_RUN`。本分析器必须在正式 replay outcome 可见前 commit；它不授权 GPU 作业。

## 唯一 headline

在每个已冻结 parent 内，只保留同时有 finite pristine `sub_score` 和 **keyed** `stdout_val` 的候选；共同候选
少于 2 个的 parent 不可判定。两种信号都乘 outcome 前冻结的公开 task metric orientation，再在完全相同的
候选集上以 tie-aware expected top-1 预测 frozen `y_norm` 最优候选。headline 是逐 parent
`external_top1_credit - stdout_top1_credit` 的均值。

这严格条件化于共同覆盖，不把 submission/stdout 缺失当低分，也不把 bare parser 放入 headline。coverage、
bare、rc、runtime 与 per-task 只作完整分解，不替换主比较。

## 冻结推断与裁决

- primary CI：physical-run clustered bootstrap，10,000 次，seed=20260813；
- secondary CI：task-clustered，同样 10,000 次；
- run sign：先在每 run 内平均 parent delta，再做双侧 exact binomial sign test；
- ties：signal 和 truth 均以 `abs_tol=1e-12` 的所有并列项计算期望 credit；
- task stress：逐 task leave-one-task-out headline；任何值 `<=-0.10` 不允许 GO；
- **GO**：delta>0、run-sign p<0.05、run-CI lower>0、所有 task LOTO>-0.10；
- **BORDERLINE**：正点估计但任一确认门未过；
- **KILL**：点估计<=0；共同覆盖为 0 则单列 `INSUFFICIENT_COMMON_CHANNEL_COVERAGE`。

不得按 task、hard/easy、parser 类型、gap、成功退出或 coverage 子集替换 headline；固定 150-run gate 后不因中间
结果追加 run。主张仍是 scoring-channel mechanism，不自动等于全候选 search speedup。

## 完整性

分析器重新验证 selection/replay/approval/orientation/result 的逐层 SHA、四 shard 完整性、每 card 唯一性、
manifest identity、worker commit 与 intake label-vault SHA。输出只含逐 parent credit/coverage 和聚合统计，不输出
raw code、stdout、sub score 或最终 grade。不导入主实现的 `verify_score_channel_prospective_analysis.py` 已一并
冻结；它从原始锁定输入独立重建逐 parent credit、bootstrap、run sign、LOTO、裁决与输入收据。
