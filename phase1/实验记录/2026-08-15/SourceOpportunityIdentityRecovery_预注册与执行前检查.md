# Source opportunity identity recovery：预注册与执行前检查

日期：2026-08-15。状态：在查看 `parent.children_ids` 对 source-incomplete parents 的恢复率前冻结。

本实验承接 `VERIFIED_LABELED_SIBLING_FRAGMENT_BOUNDARY`，不恢复已撤回的完整 choice-set 主张。唯一问题是：
在不读 outcome 的前提下，v11 parent lineage 能否恢复被发布过滤掉的 source sibling **身份集合**，从而把
fragment benchmark 升级为带显式 missing identities 的 opportunity registry。

## 冻结输入与单位

- cards：`phase1/cards_current_v11.jsonl`；
- 已核验 parent 表：远端成功产物
  `/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2/producer/per_parent.csv`；
- source commit：实现与执行时的精确 40-hex commit；
- 统计单位：`(release_role,parent_id)`；主分析只含 `source_declared_size > raw_card_child_count` 的
  source-incomplete parents。

## 冻结定义与裁决门

对每个 incomplete parent，只有同时满足以下条件才记为 `exact_identity_recoverable`：

1. parent card 存在；
2. parent `children_ids` 唯一且包含所有 retained raw child IDs（该包含关系已由上游审计证明）；
3. `len(children_ids) == source_declared_size`；
4. `len(children_ids - retained_ids) == source_declared_size - raw_card_child_count`。

不从 ID 猜执行/评分/剪枝状态。缺失 child 没有 card 或 journal receipt 时，status 与 outcome 明确记为 unknown。

固定正门为：

- complete、非 orphan parents 的 lineage 正控一致率必须为 1.0；
- 所有 incomplete parents 的 exact identity recovery rate 至少 0.80；
- train 与 frozen 各自至少 0.75；extension 因已知仅 11 个 incomplete parents，只作描述；
- producer 与不 import producer 的 verifier 必须逐 parent、逐 role、逐 hash 完全一致。

全过=`VERIFIED_HIGH_COVERAGE_SOURCE_IDENTITY_RECOVERY`；有恢复但未过门=`PARTIAL_SOURCE_IDENTITY_RECOVERY`；
零恢复或结构控制失败=`SOURCE_IDENTITY_RECOVERY_UNSUPPORTED`。无论哪一类，都不自动允许“完整 labeled choice set”、
missing-at-random、因果效应或 search utility 主张。

## 13 项执行前检查

1. **唯一问题**：只测缺失 sibling identity recoverability，不训练 predictor。
2. **主因变量**：incomplete-parent exact recovery rate；role rate 是预定分层。
3. **正控**：source-complete、parent-present rows 必须 100% 对齐。
4. **负控**：synthetic duplicate/extra/missing child IDs 必须 fail 或不可恢复。
5. **数据隔离**：禁止读取 first-960、prospective vault、pair orientation、gap、code、stdout、runtime 与 numeric grade。
6. **统计单位**：parent-equal；不得用 child 数加权伪造高覆盖。
7. **orphan 处理**：parent card 不存在一律计不可恢复，不删除。
8. **>5 处理**：沿用实际 source size，不截断为旧生成上限。
9. **失败保留**：逐 parent 输出 reason；不丢弃低覆盖 task/role。
10. **双实现**：verifier 不 import producer，重读 cards 与上游 CSV。
11. **复现**：记录输入 SHA-256、source commit、命令、Python 版本与产物 manifest。
12. **安全**：输入 parse 前做高置信凭据扫描；产物再次扫描；GPU=0、API=0。
13. **预算/停止**：两次顺序读取约 306 MB cards，预计少于 5 分钟；固定一次正式执行，不调阈值、不补样。

若高覆盖门通过，下一步只设计 journal-level status recovery；若未通过，则不绕过 lineage 失败，保留 labeled-fragment
边界并报告不可恢复比例。
