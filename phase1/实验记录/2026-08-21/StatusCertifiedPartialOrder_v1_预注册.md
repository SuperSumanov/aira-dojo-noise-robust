# Status-Certified Source Partial Order v1：结果前冻结

日期：2026-08-21。当前仍以 `phase1/CURRENT_DIRECTION.md` 的 Decision Corpus / strict-future 主线为准。本实验
CPU-only，只扩展数据合同，不训练 predictor/controller，不读取 first-960 或任何前瞻 outcome。

## 问题与直接先例边界

现有 release 有 9,755 个 source-declared `C(n,2)` pair capacity，但只发布 5,897 条 finite pair edges。独立 status
registry 已恢复 893 个 `EXECUTION_ERROR`、9 个 `OFFICIAL_GRADE_ABSENT` 和 94 个 unknown。问题是：在不猜 missing
numeric score 的前提下，把每个 finite child 对同 parent 已认证 invalid child 的 `finite ≻ invalid` 关系加入，能否
材料性恢复 source-level 可认证关系覆盖。

这不是算法 novelty。NAS-Bench-101 已把 invalid architecture 返回最差 error；PESC、BE-CBO 等 constrained BO 已把
feasibility 与 objective 分开；AMLB 也显式分析 framework failures。只允许把贡献写成：自然 MLE-agent sibling、
真实 source provenance、unknown 保留 unknown 的 failure-aware partial-order release 与覆盖审计。

## 冻结输入与关系

- per-parent source census SHA-256=
  `75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`；
- missing-status registry SHA-256=
  `bfb9870d83c50ef2d06bf2d374fc9f9213f41665f4cebeab7ab31837bcfde0d2`；
- parent 数固定 3,252，role 数固定 train/frozen/extension=2,293/845/114；status rows=996；
- 仅 `UNIQUE_NODE_RECOVERED` 且 category 为 `EXECUTION_ERROR` 或 `OFFICIAL_GRADE_ABSENT` 的 child 可认证 invalid；
- 每个 parent 新增关系数严格为 `finite_child_count × certified_invalid_count`；published finite edges 原样保留；
- unknown、journal collision、未注册 missing slot、invalid-invalid 及未发布 finite-finite relation 均保持 unresolved；
- `C(n,2)` 仍是 declared capacity，不是真实 agent comparison log；validity-first 关系不是 Kaggle numeric-score 大小。

## 固定材料门

只有以下全部通过才允许 `VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY`：新增关系至少 1,000；source
coverage 绝对增加至少 0.10；至少恢复 published→source 缺口的 0.25；train/frozen coverage gain 各至少 0.08；
source capacity≥100 的支持任务至少 10 个，其中至少 8 个有正增益；单任务新增关系占比不超过 0.35；全部整数
accounting 精确且 unknown promotion=0。任一材料门失败，只保留描述并关闭；不得结果后改 category、阈值、任务集或
把 unknown 记失败。

## 13 项执行前检查

1. 方向：Decision Corpus failure-censored release，不是旧 HCE/TD/probe/多保真。
2. 问题：status-certified relation 能否材料性恢复 source pair resolution。
3. 输入：两份不可变、已独立验证且 SHA 锁定的 metadata artifact。
4. 单位：`(role,parent)` 完整 census；role/task 仅预定分层。
5. 关系：finite 对 exact certified invalid 的 validity dominance；不看 numeric outcome。
6. 分母：逐 parent `C(source_size,2)`，禁止把 capacity 写成发生过的比较。
7. 未知：94 个 unknown 与未注册 slots 保持 unresolved。
8. 完整性：parent/role、child uniqueness、journal parent、status/category count 全部硬校验。
9. 统计：有限总体精确计数，无 IID CI、无 bootstrap。
10. 控制：synthetic positive、unknown、duplicate、parent mismatch、double-count 回归测试。
11. 复现：producer×2、独立 verifier×2、固定 commit/protocol/input hash、全套 phase tests。
12. 资源：single-thread CPU，GPU/API/base-LLM update 均为 0；不读 code/orientation/outcome/vault。
13. 停止：门失败即关闭；任何实现失败保留，不按结果追救。预计墙钟小于 30 分钟。

