# First-960 暂定集合 churn 与 Prediction Escrow 完整性：正式裁决

日期：2026-08-26。正式状态：`PROVISIONAL_FIRST960_SNAPSHOT_CHAIN_INDEPENDENTLY_VERIFIED`。

## 1. 裁决

确认一个在 960 前不会暴露、达到 960 后会确定触发的控制层 bug：source registry append-only，但按固定时间全序重建的
provisional first-960 membership 不是 append-only。旧 WL append verifier 与 transition producer/verifier 都要求 prior
prediction support 是 current 的 subset；迟到的较早 run 挤出旧尾部时，该条件会误拒绝合法 cohort。若新 run 排在 960
之后、prefix 不变，旧 WL verifier 还会因“later escrow is not a growing append”误拒绝。

正式修复保留 frozen scorer、activation、模型与 chronological estimand，只把跨 snapshot 条件改为：不可变 snapshot
binding；source set containment + sequence subsequence + old-row identity；共同预测逐字段相同；prior/current-only rows
分别必须来自被挤出/进入的 run。transition 发生 removal 时 current artifact 不传 legacy prior，再由原独立 scorer verifier
与新 chain verifier 双重核验。

## 2. 验证结果

合成 target=2 反例在读取任何真实 outcome 前冻结，覆盖 append、prefix stasis、合法 insertion+displacement、共享预测
篡改、旧 run row 篡改和 transition 错传 prior。新 verifier 全部按预期；旧 WL verifier 对同一合法 churn fixture 按预期
返回 subset failure。

真实 `d748→8579` shadow 为 362→366 runs、added/removed=`4/0`、共同/新增 pairs=`2728/27`；共同 rows 全部精确。
`7017387` formal focused/full=`24/1089 passed`，receipt 双跑逐字一致，manifest hash=
`62f90ef59e88bf647f503aa09a0aa0c97429a5f95de6371cf24a457b0d16d6b3`。

deployable monitor commit `f21a76c0a56c65eb1f24cafc33db33a65302935a` 随后在真实数据上端到端 replay：focused/full=
`25/1090 passed`；不传 legacy prior 的 producer、原 independent scorer verifier 和 chain verifier 全部 rc=0；新
2,755-row `pairs.jsonl` 与旧 `8579` artifact 逐字相同。formal manifest hash=
`06b0aaeb40a5c1206a093745b35fe1e0ae89857fa066960e069cb3aa758179e0`。

公开结果 commit `9db2d9f965b342853bd1ce944dd84051f898ccc9` 随后在 fresh post-push worktree 通过
focused/full=`11/1093 passed`，公开包原 7-entry manifest 全验；post-push formal manifest hash=
`0d267216c7848a2dd9cf7528fef6b63a48dc3876b4277103f51c7a3e681ef146`。

第一次 formal full-suite launcher 未显式锁 BLAS 线程，pytest 在登录节点扩到约 28 CPU。发现后主动 TERM；失败目录只有
`FAILURE`、没有 `COMPLETE`。v2 显式锁定六类线程变量为 1 后通过。该失败是资源契约错误，不混入正式计数。

## 3. 部署状态

旧 transition monitor PID `2247188` 经 `/proc/<pid>/cmdline` 精确核验后 TERM，旧 artifact 不删不改。新 monitor
PID=`2320379`，从原 `8579` snapshot、artifact path 与 summary SHA 无损接管；300 秒一次、72 polls。首轮
`no_change`。intake monitor 未停止。

## 4. 主张边界

- 允许：我们在 outcome 前发现并修复了 chronological provisional cohort 的非单调 membership 与 prediction escrow
  append 假设冲突，提供合成反例、真实 shadow、独立数值复算与常驻 monitor。
- 不允许：称 predictor accuracy 提升、transition critic 为正、support gate 已最终通过或 closure 已成立。
- 当前真实 shadow 没有 run removal；“真实 churn 已发生并通过”仍不可说。第一次自然 removal receipt 到来后才能补该事实。
- closure 前任一结构支持门都可因 churn 反转，只能叫 provisional，不能触发揭盲。

直接证据：`phase1/results/provisional_first960_snapshot_chain_f21a76c_20260826/`。
