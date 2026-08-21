# Decision-Corpus evidence index v3：正式裁决

结论：通过，状态为 `INDEPENDENTLY_VERIFIED_OBSERVABILITY_AWARE_EVIDENCE_INDEX`。

控制 commit `ce5c558509b1f481f9e9df1212d9f00c3cf00bce` 在固定 v2 index 上新增且只新增
`decision_observability`，形成 7 个互不合并的 estimand、20 份 artifact 与 181 项 JSON assertions。新增两份 artifact
分别是与远端正式 manifest 哈希一致的漏斗 summary 和不 import producer 的独立 verifier；v2 的六个条目逐项继承，
没有改写旧 claim、boundary、hash 或 assertion。

因此可以把以下数据结论纳入统一 release contract：source child-slot loss=
`0.14612676056338025`，declared pair-capacity loss=`0.3851358277806253`，放大=
`2.6356283154144×`；source/finite/published pair 数分别为 9,755/5,998/5,897。train 与 frozen roles 都通过原冻结门，
14 个任务有至少 100 source pair capacity，12 个任务表现为 pair loss 大于 child loss。

这不是新方法效果。机器合同明确拒绝 actual-comparison、decision-point-disappearance、complete-choice-set、MAR、
predictor/search utility、prospective effect 与 first/only 语言。全部 3,252 parents 仍保留可发布决策；9,755 只是
per-parent `C(n,2)` 的 declared structural capacity。

双 builder、双 verifier 逐字节一致；正式完整回归为 `643 passed, 1 skipped, 25 warnings`，其中 skip 是结果前控制
commit 尚无 checked-in index 的预期行为。worktree 漂移、秘密扫描、prospective outcome read 与正式可写文件均为 0。
本地回传的 30 个 payload 文件逐一通过远端 `SHA256SUMS`。正式 index hash=
`424f06b161086972fedf55d5e8e06e22d92c21e1558a04b2dd6c55e3cb637b49`。

该裁决强化 Decision Corpus / D&B 容器，但不改变 first-960 closure、strict-future transition escrow 或 clean Qwen
G0/G1 的授权门。

