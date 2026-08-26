# Provisional first-960 snapshot-chain formal receipt

状态：`PROVISIONAL_FIRST960_SNAPSHOT_CHAIN_INDEPENDENTLY_VERIFIED`。

## 固定问题

append-only source registry 不推出 provisional chronological first-960 membership append-only。晚上传但时间更早的 run
可以进入 rank `<960` 并挤出旧尾部；达到 960 后，旧 WL/transition 的 prior-support-subset 条件会误拒绝合法 snapshot。

修复不改 frozen scorer、activation、模型、预测值、first-960 排序或 closure。每代 artifact 绑定不可变 snapshot；跨代只
要求 source set containment + sequence subsequence + row identity、共同预测逐字段相同，以及所有增删都由固定 rank 解释。

## 正式验证

- verifier source commit：`7017387a149317eee450e1d5289444f08d2fd29f`；
- deployable monitor/control commit：`f21a76c0a56c65eb1f24cafc33db33a65302935a`；
- 合成 append/stasis/churn 与篡改反例：通过；旧 WL verifier 在合法 churn 反例上按预期误拒绝；
- `7017387` fresh Linux：focused/full=`24/1089 passed`，真实旧式 artifact shadow 双跑一致；
- `f21a76c` 真实 monitor replay：focused/full=`25/1090 passed`；producer、原独立 scorer verifier、chain verifier 均 rc=0；
- 真实 `d748→8579`：362→366 runs，added/removed=`4/0`，共同/新增 pairs=`2728/27`；
- 不传 legacy prior 生成的当前 2,755-row `pairs.jsonl` 与旧 `8579` artifact **逐字相同**；
- outcome/effect/GPU/API/base-LLM update=`未读/未计算/0/0/0`。

第一次 formal full-suite launcher 未锁 BLAS 线程，pytest 在登录节点扩到约 28 CPU；该 run 被主动 TERM，只有
`*.staging/FAILURE`，没有 `COMPLETE`，不计正式证据。v2 显式锁定 OMP/MKL/OpenBLAS/NumExpr/VecLib/BLIS 为 1 后通过。

正式远端只读包：

- source verifier：`/research/d7/spc/yzyang4/provisional-first960-chain/7017387-real-d748-8579-v2`，
  `SHA256SUMS` hash=`62f90ef59e88bf647f503aa09a0aa0c97429a5f95de6371cf24a457b0d16d6b3`；
- deployable monitor replay：`/research/d7/spc/yzyang4/provisional-first960-chain/f21a76c-monitor-replay-v1`，
  `SHA256SUMS` hash=`06b0aaeb40a5c1206a093745b35fe1e0ae89857fa066960e069cb3aa758179e0`。

公开结果 commit `9db2d9f965b342853bd1ce944dd84051f898ccc9` 的 fresh post-push worktree 又通过
focused/full=`11/1093 passed`，本目录原 7-entry manifest 全部通过；post-push formal manifest hash=
`0d267216c7848a2dd9cf7528fef6b63a48dc3876b4277103f51c7a3e681ef146`。它只认证公开可复现性，不新增科学主张。

## 部署

旧 transition monitor 经精确 cmdline 核验后正常 TERM，历史 artifact 全保留。新 monitor 从同一个 `8579` artifact/SHA
接管，PID=`2320379`，300 秒轮询、72 polls（约 6 小时）。首轮为 `no_change`。新 snapshot 到达时才重建当前 prefix
artifact；closure 前 support gate 仍为 provisional，不授权 effect/accuracy 揭盲。

## 边界

这是 benchmark/audit protocol 的正向完整性资产，不是 predictor accuracy、transition gain 或 search utility。当前真实
362→366 区间没有 removal；真实 churn 的通过行为由结果前合成反例冻结，待自然 accrual 首次触发时再写真实 receipt。
