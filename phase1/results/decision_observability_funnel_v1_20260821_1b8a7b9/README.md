# Decision Observability Funnel v1

正式代码 commit：`1b8a7b94f7175823763ef866e0dde2ce202828b7`。
正式状态：`VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION`。

本目录保存远端只读正式产物的紧凑副本。完整产物位于：

`/research/d7/spc/yzyang4/decision-observability-funnel/1b8a7b9-v1`

完整 release census 有 9,088 个 parent-level source child slots 和 7,760 个 raw/finite child slots；child-slot loss
share=`0.14612676056338025`。对应的 declared undirected sibling-pair capacity 从 9,755 降至 5,998，loss
share=`0.3851358277806253`，比 child loss 多 `0.23900906721724502`，放大倍数=
`2.6356283154144`。finite capacity 中发布 5,897 条 unique edges，coverage=`0.9831610536845615`；所以当前
release 的主要 pair-capacity 缺口发生在 source→raw，而不是 finite→published projection。

全部六个冻结门通过：14 个 tasks 达到 source pair capacity≥100，其中 12 个 pair loss严格大于 child loss；
train/frozen roles 也分别满足。所有 3,252 个 parents 仍保留至少两个 finite candidates 和至少一条 published
edge，因此结果是 within-parent choice resolution 的压缩，而不是 decision-parent 消失。

producer×2 与 verifier×2 逐字节一致，独立重建最大差=0；focused=`6 passed`，完整 phase tests=
`638 passed, 25 warnings`；forbidden-path 与两类秘密扫描均为 0，正式可写文件=0。本地选定文件全部通过远端
`SHA256SUMS` 校验。

这里的 9,755 是按每个 parent 的 `C(source_declared_size,2)` 得到的 declared capacity，不是 9,755 次真实发生
的 agent comparison，也不恢复完整 labeled choice set。1,328 个 parent-level missing slots 不能与先前 996 个
distinct target identities 直接等同。没有读取 code、outcome、orientation 或 prospective vault。
