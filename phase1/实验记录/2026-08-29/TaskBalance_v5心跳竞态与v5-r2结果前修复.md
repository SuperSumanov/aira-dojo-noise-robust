# TaskBalance v5/v5-r2：两次 pre-candidate parser 失败与 v5-r3 结果前修复

日期：2026-08-29（Asia/Hong_Kong）

主线：Decision Corpus + Predictor Benchmark + Audit Protocol

状态：`TWO_PRE_CANDIDATE_MONITOR_PARSER_FAILURES_BOUND_AND_R3_FROZEN`

## 1. 事故证据

权威 v4 在连续 2,160 个 10 秒 poll 后保持 `LATEST=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`，以 `TIMEOUT_RC=124` 正常结束；没有 candidate、READY、COMPLETE 或 FAILED。

supervisor 随后创建 v5，但 v5 在 monitor loop 与 preflight 之前以 `FAILED_RC=1` fail-closed。失败根固定为：

`/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5`

它只有 11 个顶层文件，fileset SHA-256=`d3ee4736512f81ad6f40a6ec7bdeb5547d48b217f9452c72461187dc14e3ba50`；`handoff_new_snapshot_ids.txt` 与 `transition_handoff_snapshot_ids.txt` 均为空，`handoff_observed_snapshot_ids.txt` 去重后只有冻结 baseline。source/protocol SHA-256=`934078533da2d34aac1325a36c5a25fd527d222651df4c4452fe6fe28d540e7f` / `6db91cddecc3b1937fd694e2b4903f02f8f81bd4c6a6cdd6b01f46944c552ee1`。candidate、READY、COMPLETE、monitor.log、preflight 与 handoff receipt 全部不存在；PID 已退出，v4/v5/supervisor 锁均 free。

这把失败点唯一定位到第一次 transition post-timeout heartbeat 的空 `grep` pipeline：在 `set -o pipefail` 下，它在后续 fallback 机会之前返回 1。v5 在 v4 最后 observation 后约 14 秒启动，而 transition/WL/receipt monitor 每 300 秒 poll，一次合法的“尚未来得及写下一条 heartbeat”被误判为 continuity failure。它不是候选、标签或科学门失败。

第一次修复由公开 commit=`1dab0292b225216b3fb79f69b3eb48b09699e3d1` 发布，fresh post-push 的 source hashes、失败根、提交安全与 focused tests=`14 passed in 0.35s` 均通过。v5-r2 启动后再次在 candidate/preflight/monitor loop 前 `FAILED_RC=1`；该失败根有 18 个顶层文件，fileset SHA-256=`0f858d36e77448aeb56390603347ad78cc3208d573b8887b8a28103db08d02aa`，candidate/READY/COMPLETE/monitor.log 仍全部不存在。

r2 的完整 gap snapshot directory 扫描仍为空，WL/receipt 只见 baseline；但 transition handoff 文件出现 baseline 与 `87ed6fa645de2fad25695b212434bd1dd64b6f1a44a34f6232c941ad8d8b9161` 两个 64-hex。回查结果盲 transition 日志确认后者来自 `script_sha256=` 字段，所有具名 `snapshot=`/`prior_snapshot=` 字段仍是 baseline。故第二个失败是旧 parser 把“任意 64-hex”误作 snapshot identity；仍不是新 snapshot 或科学结果。

## 2. 只修两处 parser 工程缺陷，不改科学协议

v5-r3 固定使用新根：

`/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5-r3`

修复只做四件事：

1. 在启动前分别绑定旧 v5 与 v5-r2 的 exact file set、旧 Git source、协议、失败点、死亡 PID 与 free lock；任一漂移即失败；
2. 继续从 v4 最后 observation 时间扫描全部 snapshot directories 和三条 support 日志，不缩短时间窗；
3. 日志只接受字段名严格为 `snapshot/prior_snapshot/latest/wl/transition/prior` 的 64-hex identity；`script_sha256`、协议哈希和其他任意 64-hex 一律忽略；
4. 若某条 support log 在边界后尚无具名 heartbeat，只允许读取该 monitor 的结果盲 state identity，并要求它等于 baseline 或唯一 current LATEST，同时把 fallback 明写入 receipt；
5. formal runner 只有在 v4 clean-timeout、旧 v5 与 v5-r2 exact pre-candidate failure、v5-r3 唯一 COMPLETE 四者同时成立时才接受 r3。

population、first-successor 定义、baseline、task-share 1/4 门、support、正式 producer/verifier 和解释均不变。多个 gap successor、support 跳过 candidate、state 非 baseline/current、旧失败根漂移、重复完成或任何新 failure 仍 fail-closed。

部署前用三条真实结果盲日志对 typed extractor 做独立 replay：transition/WL/receipt 各自唯一输出都精确等于 `887491a...62697`，`TYPED_IDENTITY_PARSER_REMOTE_REPLAY=PASS`；没有打开 candidate、state payload、标签或预测值。

## 3. 结果前 preflight

1. 方向：只续接 Decision Corpus 的 first-successor 结构确认；
2. 目标：修复 300 秒 support heartbeat 与 10 秒 latch 交接的调度竞态；
3. 已知信息：只知 v4/v5/v5-r2 marker、PID、锁、文件名/哈希、字段名和 baseline identity；
4. 未知信息：新 candidate、task balance、classification、outcome/prediction/utility 全未知；
5. population：v4 之后自动观察到的第一个非 baseline snapshot，不能由调用者传入；
6. estimand：不变，仍为固定 1/4 task-share cap 的 forward structural confirmation；
7. 对照与门：不变；该补丁不改变任何科学阈值；
8. 完整性：snapshot directory、LATEST、transition/WL/receipt state 与日志共同审计；
9. 随机性：无；
10. 资源：2,161 个至多 10 秒 poll，约 6 小时；CPU state watcher；GPU/API/model fit/base update=`0/0/0/0`；
11. 泄漏：禁止 label、outcome、prediction value、accuracy、effect、utility 和 raw archive；
12. 复现：公开 commits、两个旧失败 fileset、source/protocol SHA 与新脚本 SHA 全绑定；
13. 停止：成功只在 candidate 及三条 support receipt 齐备后写 READY/COMPLETE；任何歧义写 FAILED_RC，不能重选 snapshot。

## 4. 公开提交、post-push 与部署回执

修订由公开 commit=`9f1b57f02cdf6b9a70c870268127ffacb3bc44b7` 发布。handoff/正式 runner/static test SHA-256=`990f600732bf525c4279ef31d65a63b8d35c6316cfd2f78cad0a5da52908f0e7` / `eb384dbbd3b94a6add9ceebef78198bfc2bbf0759c3db99b9cb497b066453725` / `dbb05b0ea63bed8c9221bcbaa811a175100bd96aba00c60660a0dc20db498c80`。

fresh detached post-push：changed files=5，focused=`14 passed in 0.38s`，typed identity replay=PASS，credential filename/blob=`0/0`，git clean；没有跑无界 full suite。随后从该公开 commit 启动 v5-r3。`2026-08-29T03:58:22Z` 的独立 postflight：PID=`194734` live、lock held、LATEST 与 handoff unique identity 均为 `887491a...62697`，candidate/READY/COMPLETE/FAILED=`false/false/false/false`，连续四个 poll 正常。

handoff/preflight/deploy-manifest SHA-256=`75e136446b87a346cce9bbf9d614930c654a7f6c9062a4a968c5ffc88f307128` / `585385de90fc2d6e35b041c4173856cec560daeccd87a47ea0fedb82ce7c37f6` / `a4975902227fd135b3459b6188c900686077be3260dbf86077090e7cf45ff8f5`。公开最小回执见 `phase1/results/task_balance_v5_r3_monitor_repair_20260829_9f1b57f/`。

prospective values 仍未读，也没有科学结果；v5 与 v5-r2 两个失败根均原样保留。v5-r3 后续若出现 candidate，只能等 transition/WL/receipt 三条 support 到达同一固定 identity 后写结构 READY，不得提前读取 balance 或分类。
