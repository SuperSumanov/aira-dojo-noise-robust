# Meta Kaggle Human Fork Exact Parent：S0a 正式裁决与 S0b 实现预检

日期：2026-08-21。正式 S0a 状态：`S0A_PASS`。这只是输入与 schema 资格通过，不是 human-fork 支持规模或
predictor 效果结论。

## 1. 输入裁决

official daily snapshot 的 acquisition 前后 raw CRLF listing SHA 均为 `5a310281...87181ab`，normalized listing
SHA 均为 `965de66d...d00f35`。六张 CSV 总计 8,216,765,816 bytes，逐文件 SHA 已写入固定 input manifest。
新增三张主表为：

- `Kernels.csv`：307,652,726 bytes，SHA=`dccccbad...2983680`；
- `KernelVersions.csv`：4,927,636,096 bytes，SHA=`d8a6a7a4...0a98725`；
- `Submissions.csv`：2,597,744,302 bytes，SHA=`6185b27e...eea63d`。

`Competitions` 与两个 link tables 的 SHA 精确复现 S0a 前已绑定值。dataset metadata SHA 也未变化。receipt 的
filename/content secret hits 均为 0。

## 2. Schema 裁决与零 outcome 接触

header 明确包含：

- `Kernels.{Id,ForkParentKernelVersionId,FirstKernelVersionId}`；
- `KernelVersions.{Id,ScriptId,ParentScriptVersionId,CreationDate,VersionNumber}`；
- `KernelVersionCompetitionSources.{KernelVersionId,SourceCompetitionId}`；
- `Competitions.{Id,DeadlineDate,FinalLeaderboardHasBeenVerified,HasLeaderboard}`。

所以 exact-parent S0b 所需字段全部存在。`KernelVersionKernelSources` 的 header 也再次确认其字段是
`KernelVersionId,SourceKernelVersionId`；它仍被禁止作为 fork parent。outcome table 在 S0a 只读第一条 header，
data rows opened=0；没有打开 public/private value、notebook code 或 personal text fields。

## 3. S0b 实现预检

在任何 S0b data row 前已实现 producer 与不 import producer 的 verifier。两者使用不同的 CSV projection 与全局
ID 去重实现：producer 写 64 个二进制 hash partitions，verifier 写 97 个文本 partitions；都精确而非 Bloom/filter
近似。全局 Kernel/KernelVersion ID、被引用 Competition ID、first/parent version join、parent field agreement、
parent/child time order、acyclic、singleton competition 与 completed/verified 状态均独立重建。

每个 parent 固定按 child hash 选一对，orientation 用独立 hash domain；大 fork group 不产生组合放大。模块没有
outcome table 文件名、source-version outcome key 或 public/private score 字段输入。当前 7 个合成/反例测试通过，
覆盖 formal-scale pass、独立重建逐字段一致、5% agreement 边界、全局无关 duplicate、稳定 pair selection、
forbidden input source scan 和缺 header fail closed。

正式运行前还需把 input/protocol SHA 写入 runner、跑全部 phase tests、从精确 commit 建立隔离 worktree，并执行
producer×2/verifier×2。S0b 只会输出 identity/support counts；即使过门，也先冻结 S1 才能打开 outcome rows。

工程纠错：commit `6c4bcd2...` 的第一次 formal attempt 在隔离 worktree materialization 时停止。Git 默认 LFS
smudge 试图获取一个与本实验无关的历史 `full_artifacts.tar.gz`，但该 61KB pointer 对应的 server object 为 404；
因此 focused/full tests 与真实 CSV data rows 均未开始。重试只给 `git worktree add` 增加项目正式 runner 已采用的
`GIT_LFS_SKIP_SMUDGE=1`，所有登记 source files 都是普通 Git blobs；输入 SHA、协议、算法和门槛不变。旧 partial
worktree 不复用、不晋升。
