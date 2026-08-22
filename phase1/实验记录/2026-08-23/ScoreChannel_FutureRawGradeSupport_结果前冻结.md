# Score-channel future raw-grade support：结果前并行冻结

日期：2026-08-23；冻结 UTC：2026-08-22T21:02:12Z。状态：
`FROZEN_FUTURE_OUTCOME_UNREAD_WAITING_BASE_TRUTH`。当前 future identity cohort 尚未闭合，label vault、raw grade、
`y_norm` 与 replay outcome 均未打开；本协议 CPU-only，不授权 replay、GPU、API 或 model fit。

## 1. 激活依据与边界

旧 158-parent cohort 的结果前审计在 commit `5e3ebcd571676cd55188bf22ad7265b34b7dc1b8` 后才读取聚合，并由独立实现
确认：157 个 raw non-tied、10 个 normalized non-tied、147 个 clipping aliases、16 个 alias tasks、0 个反向
不可能情形。冻结 material gate（alias parents≥16 且 tasks≥4）两项均通过。formal analysis/verification SHA-256：

- `38788c89ca8231428482d9bea1a43e5a641eda7a6efa26dec89eb6499e594ba5`；
- `4b56b9e2e3cb9c52f390dd92b3877f818ef7b2edecc27cde919c06a09fb22789`。

这只激活旧协议允许的“另名追加 raw-grade support estimand”。它不反转旧 cohort verdict，不把 raw 结果称为方法
效果，也不允许覆盖 future 原始 `y_norm` machine status。

## 2. 完全相同的选择集

扩展必须等待原 `score-channel-future-truth-support-v1` producer 与独立 verifier 都完成，然后逐字节复用其
`selected_parents.jsonl`。同时再从 closed cohort、structural sibling clique 和 SHA lottery 独立重建 selection；任一
row、顺序、candidate identity 或 SHA 不一致即拒绝。禁止按 raw grade、`y_norm`、task 或结果重选 parent。

锁定的 base 协议/producer/verifier SHA-256 分别为：

- `54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d`；
- `7df41993d978ae4942d9d8a5dac7ff0a06ae9564edfba30e2d420c7e4a24aa60`；
- `090bcf603aecac3181705206690fe29da7012c20c92d0fe832be65f11503ea4f`。

## 3. 并行 estimand 与固定门槛

- raw informative：同一 selected sibling set 中 `max(graded)-min(graded)>1e-12`；
- normalized reference：同一集合 `max(y_norm)-min(y_norm)>1e-12`；
- raw grade 必须全部符合固定 MLE-bench grader 的官方五位小数网格；off-grid 即 fail closed；
- 只报告 tied/non-tied、alias、boundary、run/task balance 与 per-task 计数，不输出 card-level label；
- raw metric 跨 task 不同量纲，因此禁止构造跨任务 raw-gap bins；support 计数不需要 task orientation；
- 若未来设计 effect test，必须在 outcome 前另建完整 orientation receipt。

为避免结果后调门，raw support 原样复制 base 的四个阈值：non-tied parents≥80、含 non-tied 的 tasks≥8、dominant
task share≤0.25、selected physical runs≥60，四项全过。raw PASS 只允许准备**另名** raw-grade replay matrix、
orientation receipt、power analysis 与 GPU-hour request；不能自动提交。raw KILL 则不请求该实验。无论 raw 状态如何，
原 `y_norm` 状态必须单列且不变。

协议 SHA-256=`4b13814ad53758d21e7f7b531ede5b9a63fd244c7e305833d0513eb77195c8c0`。

## 4. 双实现与攻击测试

producer 复用 base producer 的闭合/选择实现；独立 verifier 不导入 extension producer 或 base producer，而走已经
独立实现的 base verifier 重建 cohort、vault、clique 与 lottery，再独立聚合 raw support。当前 7 个聚焦测试覆盖：

1. base `y_norm` 因 79/80 KILL、raw 80/80 PASS，且 base 状态未被覆盖；
2. 双跑 summary 逐字节一致；
3. 六位小数 off-grid grade 双实现均拒绝；
4. candidate 跨 parent 复用双实现均拒绝；
5. extension raw count 篡改被独立 verifier 拒绝；
6. verifier 源码不导入任一 producer；
7. protocol bytes 与两份实现内置 SHA 一致。

## 5. 13 项预飞

1. 当前唯一主线仍是 future score-channel identifiability；本项只是 result-blind measurement amendment；
2. 旧 alias 结果已知且明示，future raw aggregate 未知；
3. sampling unit 是 base 完全相同的 selected sibling parent；
4. cohort/base truth/base verification/grader 全部 SHA 绑定；
5. official raw grade 只恢复到五位小数，不声称 unrounded truth；
6. raw 与 normalized 在同一 sibling set 比较，不按结果选 task/subset；
7. 四个阈值从 base 原样复制，不重新 power-shop；
8. identity closure 必须先于任何 label open；
9. producer×2、verifier×2 与字节一致性必须通过；
10. 输出 aggregate-only，不写 label/code/stdout/winner；
11. 运行前后做 forbidden-open、文件名和高置信内容凭据扫描；
12. CPU-only，GPU/API/model fit/base-LLM update 全为 0；
13. 任一 SHA、base status、selection、grid 或独立重算不一致即保留失败目录并停止。

## 6. Push 后 exact-commit 验证

冻结代码、协议、测试和本报告以 commit `78c44ac841b22b8b0f0cf1eb32214a7a79187de5` push。fresh detached
no-smudge worktree 上，联合聚焦测试 22/22、完整 `phase1/tests` 798/798（33 warnings）；commit 文件名/高置信内容
凭据扫描为 0/0。整个验证 future truth open=false，GPU/API/model fit=0/0/0。不可变远端 `SHA256SUMS` manifest
SHA-256=`6e8666d5f3dc61b27b526590a692b02e007151bebbb0500adb3ebf9bcfec75f3`，收据镜像在
`phase1/results/score_channel_future_raw_grade_freeze_20260823/`。

## 7. Truth 语义与噪声边界

本 extension 的 exact raw non-tie 是**logged artifact-conditional support**：比较同一次已执行 candidate 产生的固定
`submission.csv` 在 pristine grader 下的官方五位小数分数。对这一 estimand，task orientation 只影响 winner，不影响
是否 non-tied；同一 artifact 的 grader 是确定的。

它不等于“重跑代码后 ordering 必然稳定”，也不自动通过 test-retest noise gate。若 raw gate 最终 PASS，后续 power
analysis 必须同时报告：原 exact artifact support，以及仅在既有 repeat-grade 资产可估计的 task 上做的 noise-margin
sensitivity；缺失 task 不得从别的 task 池化填值。该 sensitivity 必须在 replay outcome 前冻结，不能用未来 gap 选阈值。
因此当前 raw PASS 仍只会允许准备设计请求，不构成可靠性或效果结论。
