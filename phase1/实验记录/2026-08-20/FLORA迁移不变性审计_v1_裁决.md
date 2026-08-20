# FLORA 迁移不变性审计 v1：裁决

## 一句话结论

原版 FLORA workflow graph 不能等价搬到 MLE sibling endpoint；但“search lineage 在 pair 内完全相同”的省略理由
也被数据否定，因为 v11 5,897 对与前瞻盲前缀 1,473 对都只有 `step` 在每一对上不同。下一步应补一个严格单列的
适配 graph/multi-view extension，同时把 `step-only` 作为位置偏差负控；当前没有 graph 效果正结论。

## 为什么这仍是有用进展

它把模糊的“补个 GNN”拆成三个不可混淆的对象：

1. FLORA 的 workflow-internal DAG：我方没有，不能伪装成直接 reproduction；
2. search-lineage graph：在 sibling ranking 中除 step 外全部恒定，而且 step 已被当前 static scorer 使用；
3. candidate-code AST/token graph：我方可构造，但这是新的适配表示，只能先冻结再到 future outcome 上测试。

因此后续不会花 GPU 复刻一个预测对象错误的模型，也不能用“不适用”跳过整个 graph family。真正有信息增量的
候选只剩 candidate-code graph 及其与 global code/lineage 的多视图融合；正负结果都必须由未揭盲 extension 裁决。

完整数字、复核、安全和失败链见
`phase1/results/flora_transfer_invariance_v1_20260820_fa7468f/README.md`。
