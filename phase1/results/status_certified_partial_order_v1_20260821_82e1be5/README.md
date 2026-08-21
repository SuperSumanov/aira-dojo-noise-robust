# Status-Certified Source Partial Order v1

正式状态：`VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY`。控制 commit：
`82e1be5839506556e0edde5cd240e1918e2eed66`。

本实验只读两份已经独立验证并由 SHA-256 固定的 metadata：3,252-parent source census 与 996-row missing-status
registry。它不读取 candidate code、numeric outcome、pair orientation、prospective vault、raw archive 或 checkpoint。

## 正结果

现有发布边在 9,755 个 source-declared `C(n,2)` capacity 中覆盖 5,897 条，即
`0.6045105074320861`。对每个 parent，仅把 finite child 与同 parent `UNIQUE_NODE_RECOVERED` 且类别为
`EXECUTION_ERROR`/`OFFICIAL_GRADE_ABSENT` 的 child 组成 validity-dominance relation；94 个 unknown 和 332 个
未注册 missing slots 继续 unresolved。

该规则从 902 个 certified invalid children 得到 2,079 条新增且与发布边不重叠的关系，使 certified relations=
7,976、coverage=`0.8176319835981548`，绝对 gain=`0.2131214761660687`，恢复原 source-minus-published
关系缺口的 `0.5388802488335925`。train/frozen/extension 的 gain 分别为
`0.22235838779956427`、`0.18819351975144252`、`0.13924050632911392`。14 个 source capacity≥100 的支持
任务中 11 个有正增益；最大任务新增关系占比=`0.18759018759018758`。全部九个预注册门通过。

## 边界

这是 failure-aware 数据合同，不是新算法。NAS-Bench-101 已把 invalid architecture 返回最差 error，constrained BO
也早已分开 feasibility 与 objective；本项目只主张自然 MLE-agent sibling 上、由 provenance 认证且保留 unknown 的
partial-order coverage。`C(n,2)` 不是真实 agent comparison log；validity-first relation 不是 missing Kaggle score 的
估计；仍有 1,779 条关系 unresolved。因此不允许 complete-choice-set、MAR、numeric-quality ordering、predictor/search
utility 或 first/only 语言。

## 复核

producer×2 与不 import producer 的 verifier×2 均逐字节一致，独立重建最大差=0；focused=`5 passed`，完整
phase tests=`649 passed, 25 warnings`。forbidden scientific path、两类秘密扫描、worktree 漂移和正式可写文件均为
0。正式 summary SHA-256=`fb6bbf07c9be7b119e301718d1e78121d2e566b93decdec6b6b0fbaf011e9af4`，独立
verification SHA-256=`ba3a2af06a472839c6be107d69842d99c5a9279b713e5b7cce743c878034a01f`，完整
`SHA256SUMS` SHA-256=`99161ed78c3c99acdc0c4874e4d4d042ac7bd65e3c2e84cf36048bf8282d82ab`。回传后 54 个
manifest payload 全部匹配。

完整只读远端产物：

`/research/d7/spc/yzyang4/status-certified-partial-order/82e1be5-v1`

本 README 是回传后的解释文件，不属于远端只读 `SHA256SUMS` payload。

