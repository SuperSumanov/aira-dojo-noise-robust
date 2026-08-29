# Endpoint-budget task heterogeneity audit

固定分类：`EXPLORATORY_TASK_HETEROGENEITY_AUDIT_COMPLETE_NOT_CONFIRMATORY`。

本目录只发布 aggregate/public 产物，不含 raw/hash task/run/pair identity、per-pair probability 或 private task rows。私有 witness 在
formal root 中以 owner-only mode-0400 封存：
`/research/d7/spc/yzyang4/endpoint-task-heterogeneity-audit/formal-d2fb68c-r1`。

## 绑定

- analysis commit：`d2fb68c38b75eabd0f3520775da9aa16ea0e6ad6`
- input artifact commit：`9f9705a14eac5bf73a070ac7c37091a815c4e31b`
- protocol SHA-256：`f3aea61901210b17acf2632c0c5a91541dae0fb2b9435ea231d0822657e0a99e`
- formal manifest：`6928273091f64ce9aa304a05909364e5df40a6d9b55c93d28f5fd612e52651d8`
- public result SHA-256：`001f58d11f13016ba66e09bcee7aabe313f1defa4ad3756153254784343f6ab5`
- private witness SHA-256（内容不发布）：`cc7c41ab3cdc800cf1b57c8ee6e9bd49082a6b3898af92a839b2d1f129f5b682`
- independent verifier SHA-256：`f0da519895b963e9a0708eaca062d609d39f56500cefcc113a20bc48049a59f2`

## 裁决

pooled accuracy 的描述性增益不能代表跨任务稳健性：两个预算的 task-macro accuracy 都为负，terminal 最大任务主导正贡献，pure
breadth 还加大了诱导训练 labels 与 outer-train task availability 之间的分布距离。因此旧两臂规则不晋级。唯一允许的新假设是另行
冻结 distribution-matched yield + task/run anti-dominance acquisition；本历史审计不能作 efficacy confirmation，也不能用于删除或
重加权任务。
