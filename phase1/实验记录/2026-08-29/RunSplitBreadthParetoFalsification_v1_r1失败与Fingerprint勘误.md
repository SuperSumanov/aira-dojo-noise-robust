# Run-Split Breadth Pareto Falsification v1：r1 失败与 Fingerprint 勘误

日期：2026-08-29

## 1. r1 事实

公开冻结 commit=`1563655a998851d41e9038fa5bda79a78f650247` 的 formal r1 位于
`/research/d7/spc/yzyang4/historical-run-split-breadth-pareto/formal-1563655-r1`。13 项预飞、全部 immutable input/package
manifest 及 focused/full tests=`36/1587 passed`（47 warnings）完成后，第一个 producer 在完整 539-pair graph 的 fingerprint
assertion 处以 `FAILED_RC=1` fail-closed。

r1 没有 `producer_a.json`、没有 verifier invocation、没有 `COMPLETE`。异常发生在 fold partition、split profile、support gate 和
acquisition curve 之前，因此 hash split 的两折计数和任何 method curve 均未 readout；不得从 r1 得出科学结论。

## 2. 根因

上一轮发布包的 `graph_census.orientation_free_identity_fingerprint_sha256` 直接继承 qualification 的
`strict_residual_profile` fingerprint。该 schema 编码 `(relation, split, unordered endpoints, parent)`。新 producer/independent
verifier 的重建 graph fingerprint 则编码 `(unordered endpoints, parent, task, physical run)`，与 qualification 的
`identity_fingerprints.strict_residual` 对应。

两者都被上一轮独立 verifier 认证，但用途和 schema 不同；r1 错误地把 graph identity fingerprint 与 profile fingerprint 直接
比较。错误属于完整性绑定实现，不涉及 population、split salt、support、budget、method、seed 或 Pareto threshold。

## 3. 唯一允许的修复

producer 与 non-importing verifier 各自新增相同语义但独立实现的双绑定：

1. prior `graph_census` fingerprint 必须精确等于 qualification `strict_residual_profile` fingerprint；
2. 当前重建 graph identity fingerprint 必须精确等于 qualification `identity_fingerprints.strict_residual`。

新增 synthetic regression 明确证明两个 schema 不可互换；相关 focused tests=`37 passed`。protocol 与 formal runner 不改。

- protocol SHA-256：`76a6ad30188c53c4f93b1132d45f16608d025057a5624eae7c5b9f13d4544396`（不变）
- repaired producer SHA-256：`d8966a0b26c7b2bb57152038a56fbd838ae780dcd4851c78d792ff7954a1b9be`
- repaired independent verifier SHA-256：`d915167bbd1a359dc338d45c3649faa99b66eeb821fbe09d9814f34f1f5d3fd4`
- repaired synthetic test SHA-256：`10d3675052b69adf4c808eb836257b18a46d5a0365fe4442afcadefa285daa5b`
- formal runner SHA-256：`a78591031f99dc488e6c5f61cb91f4e172af17e638b52127398d638a7bfe3d8e`（不变）

只有该修复公开提交后，才可在 fresh `r2` root 整轮重跑；禁止复用 r1 worktree/output，禁止在修复窗口读取 split counts 或改任何
科学 gate。
