# Prospective Operator Support v1：执行前冻结

日期：2026-08-19。状态：`NOT RUN`。本轮只做 outcome-blind 结构资格审计，不改变 production policy，
不打开 label vault，不授权 randomized logging、GPU/API 或因果/方法主张。

## 唯一问题与已知信息

问题：当前 prospective eligible manifests 中，同一 parent 下是否有足够多、任务分布不过度集中的
`Debug`/`Improve` 混合 operator children，使未来预算守恒的 randomized operator logging 在结构上可行？

在冻结本文前，已探索性看到全体 4,424 endpoints 的单节点 operator 边际计数为 Debug=2,034、
Improve=1,998、Draft=392；这些数字不再作为未见结果。尚未计算且本轮唯一新资格信息是 parent 内 operator
混合、exact-two mixed parents 与其任务分布。本轮不能产生搜索收益或 operator 效果。

## 固定输入与实现

- snapshot：`b3ef1f75b7a111327c3dbad03aee6f03098de01307573ce520f04fa2339314b4`；
- transactions：35 行，SHA256=`6db342bc711ef4b0445171db796a3efb52b7989524120a17795a1480a7fd1408`；
- 每个 transaction 必须绑定 intake summary SHA；只读 `eligible_blind_manifest.jsonl` 的 identity 与
  `lineage.parent/op`，不输出 code；
- producer：`phase1/audit_prospective_operator_support.py`；
- verifier：`phase1/verify_prospective_operator_support.py`，不 import producer，只从匿名 parent artifact
  重建 parent 统计与 scope；
- parent 单位：`(task, physical_run_id, parent_id)`；输出 parent identity 只保留 SHA256。

## 固定资格门

所有门同时通过才记为 `OPERATOR_RANDOMIZATION_SUPPORT_FEASIBLE`：

1. eligible runs≥150、tasks≥15、endpoints≥3,000；
2. Debug/Improve 各≥1,000 endpoints 且各覆盖≥15 tasks；
3. mixed-operator parents≥100、mixed tasks≥10；
4. exact-two mixed-operator parents≥60；
5. mixed parents 的 dominant-task share≤0.25。

阈值是生产接入的结构下限，不是显著性检验。通过也只允许进入 scheduler event-stream authenticity 与
预算 ledger 设计；`production_activation_authorized=false`、`causal_claim_allowed=false` 保持不变。

## 十三项检查

1. 方向：D&B decision-faithful benchmark 的 interventional extension，不恢复旧 HCE/TD/多保真。
2. 代码：完整 40 位 clean commit；结果写入新目录，禁止覆盖。
3. 输入：固定 35-transaction snapshot 与逐 intake SHA。
4. 单位：parent，不把 child 当 iid。
5. 已见结果：单节点 op 边际计数已明确披露；只裁决尚未看的 parent mixing。
6. 特征：只读 task/run/card/lineage；不计算 code 特征。
7. 泄漏：不打开 `label_vault.jsonl`、score/outcome/prediction。
8. 安全：intake 必须声明 credential=0、env 未读；manifest 再做 credential-shaped bytes 门。
9. 统计：只报精确计数、任务分布与预先固定的结构门，不报虚假 CI。
10. 复现：producer 双跑逐字节一致；独立 verifier；保存 input/output SHA。
11. 资源：CPU-only，预计<5分钟；GPU=0、API=0、底座更新=0。
12. 失败：任何 SHA、blindness/security 或 schema mismatch 立即 fail closed。
13. 停止：支持不足则不改阈值、不筛任务；支持通过也不接 production，先取得学长 scheduler 的
    append-only 完整事件流与真实 displaced-slot ledger。
