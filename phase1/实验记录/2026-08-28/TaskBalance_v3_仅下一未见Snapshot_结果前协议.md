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
