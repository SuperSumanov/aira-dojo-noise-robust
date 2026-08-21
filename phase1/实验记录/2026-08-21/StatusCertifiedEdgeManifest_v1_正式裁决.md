# Status-Certified Edge Manifest v1：正式裁决

结论：通过，状态为 `VERIFIED_STATUS_CERTIFIED_EDGE_MANIFEST`。

## 为什么需要这一步

0DC 已经严格确认了 2,079 条 status-certified relations 的 aggregate 数量与 coverage，但正式产物只包含 per-parent
counts。若论文把它称为可发布的 partial order，就必须能给出每一条 child-ID edge，而不能让读者依赖我们手工展开。
本轮是结果后 release engineering：不再检验新 headline，只把已确认关系变成可逐边审计的机器清单。

## 正式结果

控制 commit `c9bfc21c1e8428787caf4e70db404a18990910bc` 从固定的 parent census、status registry 和三份 v11 b0
endpoint identity 集合重构出 2,079 条唯一的 `VALIDITY_DOMINANCE` edges。它们来自 902 个 certified invalid
children，连接 1,498 个 finite children、658 parents、14 tasks；role 分解为 train/frozen/extension=
1,633/424/22。独立 verifier 不 import producer，逐条重构完全一致。

pair 文件中的 `better/worse` 只形成无向 endpoint union；专门的 orientation-swap test 证明交换方向不改变 endpoint
集合或结果。gap、numeric score、code、prospective outcome 均不用于生成关系。因此边只表达“可执行/有 official grade
的 finite candidate 在 validity 上支配精确认证失败的 sibling”，不表达两个有效程序的数值质量顺序。

## `EXECUTION_ERROR`-only 压力测试

2,079 条中有 2,060 条来自 `EXECUTION_ERROR`，19 条来自 `OFFICIAL_GRADE_ABSENT`。完全删除后者，剩余关系仍令
certified coverage=`0.815684264479754`、gain=`0.21117375704766786`、gap recovery=
`0.5339554173146708`；train/frozen gain=`0.22004357298474944/0.18819351975144252`。14 个支持任务中 11 个
为正，dominant-task share=`0.1883495145631068`。原全部材料门不变且仍通过，故正结论不依赖较有争议的
grade-absent 类别。

该压力测试不能替代原 headline，也不能把 execution error 当作数值最差 score。94 个 unknown、332 个未注册 slot、
invalid-invalid 与未发布 finite-finite 关系仍 unresolved；仍禁止 complete choice set、MAR、numeric-quality total
order、predictor/search utility 和算法 novelty。

## 复现与失败记录

producer×2/verifier×2 byte-identical；focused=`5 passed`，全部 phase tests=`654 passed, 25 warnings`；路径、秘密、
worktree 审计均通过。第一次 formal attempt 的四次科学重构都成功，但 shell runner 在禁止路径命中为零时被
`pipefail` 的空 `grep` 提前中止，未形成 `COMPLETE`。修复只处理空过滤退出码；新 commit、新 worktree、新输出目录
从头重跑，旧半成品不复用。正式边 SHA-256=
`dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d`。

这一步把 0DC 从 aggregate coverage audit 补全为真实可分发的 failure-aware partial-order asset，强化 D&B 数据主张；
不改变 strict-future score-channel 主实验、first-960 closure 或 clean Qwen 预算门。
