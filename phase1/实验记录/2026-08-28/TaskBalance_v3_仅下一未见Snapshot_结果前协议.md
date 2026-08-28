# Task-balance v3：仅下一未见 snapshot 的结果前协议

状态：`IMPLEMENTATION_FROZEN_FIRST_UNSEEN_SUCCESSOR_PENDING`。冻结时间为
2026-08-28T05:11:36Z；写本文时 outcome-blind `LATEST` 仍为 `887491a...`。

## 为什么需要 v3

887 snapshot 的 v2 正式运行在读取 balance 结果前按预注册规则退出：guard baseline 含 30 个任务，当前结构人口含
34 个任务。该运行没有 `forward_a.json` 或分类，不能在同一 snapshot 把新增任务补零后重跑来 rescue。

不过“新增任务在 baseline 中计数为零”是 append-only benchmark 的必要定义。v3 因此只修协议接口，不改 25% cap、
整数 debt、first-960 chronology、共同支持或安全边界：baseline task set 必须是 current task set 的子集；新增任务显式
零扩展；任务删除、pair/run 计数回退、dominant task 改变仍 fail closed。旧 v2 的 task-universe equality 行为保持不变。

## 防止事后选择

v3 禁止以 887 为 current snapshot。唯一允许的人口是：包含本协议与 v3 代码的公开 commit 之后，由受审计 transition
chain 首次出现、且已取得 exact receipt-only common-support verification 的最早 immutable successor。不得跳过更早的
eligible successor，也不得从多个 snapshot 中人工挑选。

主判定只有两类：所有 task 的 pair share≤25% 且 debt=0 时为 `CAP_PASS`，否则为 `CAP_FAIL`。HHI、TV、debt delta、
dominant/non-dominant 增量和 added-task count 都只作 secondary，不能 rescue primary。即使通过，也只支持 provisional
Decision Corpus 的结构 balance，不支持自然摄取因果、producer compliance、predictor accuracy 或 search utility。

## 实现与当前验证

- `task_balance_guard_forward_validation_v2.py` 与其独立 verifier 新增默认关闭的
  `allow_task_expansion`；默认值 `false`，故 v2 字段与失败语义不变。
- v3 入口显式打开该开关；producer 与 verifier 仍是分离实现，verifier 不 import producer。
- synthetic tests 覆盖：v2 对新增任务继续 KILL、v3 显式零扩展且独立复核、dominant task 改变继续 KILL、verifier
  不 import producer。当前 focused=`8 passed`。

正式运行前仍须绑定未来 snapshot/summary/ledger/common-support 的确切 SHA，执行 producer A/B、verifier A/B、完整测试、
trace 与 credential gates。prediction/label/outcome/accuracy/effect/utility/raw archives 禁读；
GPU/API/model-fit/base-update=`0/0/0/0`。

## 六小时边界后的连续性续接（结果前修订）

原 v3 latch 在 `2026-08-28T12:05:57Z` 完成固定 2,160 次轮询并正常写入 `TIMEOUT_RC=124`；最后一行仍为
`LATEST=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`。旧 root 没有
`FAILED_RC`、`candidate.tsv`、`READY` 或 `COMPLETE`，`monitor.log` SHA-256 为
`5aa5c35e02c5cb119c0dc45f8e87382278e741ae664af2058f1f083c76f24190`。正常超时不是科学失败，但若不续接，
下一批到达时会失去“首个后继”的可验证选择机会。

续接不改变科学协议，只延长观测窗口。新脚本必须在任何 successor 出现前公开，并只在以下六项同时成立时建立固定
`latch-continuation-after-887-v4`：

1. 旧 root 是上述精确正常超时且从未 latch candidate；
2. 当前 `LATEST` 仍为 887；
3. 按 mtime 排序的最新 immutable snapshot directory 仍为 887；
4. transition、WL、receipt state 均仍为 887；
5. 从旧 monitor 最后时间起，三条独立 support monitor 日志中出现的唯一 snapshot identity 均为 887；
6. 续接脚本逐字节等于公开 control commit 中的 git object，且该 commit 是当前公开分支祖先。

任一不满足即 fail closed。通过后仍只锁第一个 observed successor，并继续等待三套 support 到达同一 identity；不得由
调用者传 snapshot 或跳过更早 successor。cap=25%、整数 debt、task-expansion 与 ordered classification 均不变。
TERM/INT/HUP 必须留下失败回执；再次正常六小时超时则保留新的 `TIMEOUT_RC`。本修订没有读取 balance 值、预测值、
label/outcome、accuracy/effect/utility 或 raw archive，也没有授权 GPU/API/model fit/base update。

## 续接上线与独立回执

续接脚本已在任何 successor 出现前由公开 commit
`6b3a7ba626798cd4bf15147eef3da90293e98158` 的 exact git object 启动；SHA-256 为
`8900896df4a13861dd53dd3d9b6de8c20d9b9d499fe1063c07b33ccd9ce814b8`。固定 root 为
`/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v4`。

`2026-08-28T13:47:37Z` 的结构回执：PID=`4061250` 且 live，lock=`held`；candidate、READY、COMPLETE 均不存在，
FAILED/TIMEOUT 均不存在。continuity receipt 逐项确认旧 timeout、当前 LATEST、最新 snapshot directory、三套 support
state 和三条 support 日志的唯一 snapshot identity 全部为 887；`earlier_successor_observed_or_skipped=false`。

该 exact push 的 fresh Linux post-push root 为
`/research/d7/spc/yzyang4/task-balance-v3-first-successor/postpush-6b3a7ba-v1`：focused=`13 passed in 0.29s`，
完整 `phase1/tests=1424 passed, 47 warnings in 80.52s`；Python=`3.11.15`，凭据文件名/内容命中=`0/0`，
GPU/API/model-fit/base-update=`0/0/0/0`，`SHA256SUMS` SHA-256=
`b979e874e7823660e30689f88e8ff1260e1ccf194fe3e4159e22d2e77efa2de8`。

这些回执证明选择链连续且实现可复验，不是 `CAP_PASS` 或任何 predictor 正效果；真实 candidate 仍未产生。
