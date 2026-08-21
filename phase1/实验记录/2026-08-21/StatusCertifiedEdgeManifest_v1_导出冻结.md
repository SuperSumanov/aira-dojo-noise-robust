# Status-Certified Edge Manifest v1：结果后导出冻结

日期：2026-08-21。该步骤不再检验新的确认性材料门，而是把已通过的 2,079-relation coverage audit 转成可直接使用的
child-ID edge manifest，并同时做 `EXECUTION_ERROR`-only 压力统计。

固定输入为：三份 v11 b0 train/frozen/extension pair 文件的 `normalized_utf8_lf_v1` hashes；source per-parent
SHA=`75c022...36d03`；status registry SHA=`bfb987...de0d2`；正式 partial-order summary normalized SHA=
`fb6bbf...e9af4`。完整值见 `status_certified_edge_export_protocol_v1.json`。

pair 文件只用于取得每个 `(role,parent)` 的 finite endpoint ID 集合。实现会读取 `better/worse` 两个 endpoint 字段，
但把它们立即作为无向集合；禁止使用谁 better、`gap_raw`、score、code 或任何 prospective outcome。每条输出边固定为
`valid_child_id VALIDITY_DOMINANCE invalid_child_id`，并携带 role/task/run/parent、invalid category 与 status journal
SHA。必须逐 parent 验证 endpoint union 数等于正式 finite count、pair rows/unique edges 与 source census 一致、invalid
child 不在 finite endpoint 集、边全局唯一且总数精确为 2,079。

结果后敏感性固定为完全删除 `OFFICIAL_GRADE_ABSENT` edges，只保留 `EXECUTION_ERROR`；重新计算总体、train/frozen
role 与 task-support 统计，并逐项复核原来的 relation-count、overall gain、gap recovery、train/frozen gain、task 数和
dominant-task-share 材料门。该敏感性不能替代原 headline，也不允许改变任何门值。

producer×2、独立 verifier×2、完整 phase tests、strace 禁止路径、秘密扫描和只读产物全过后才发布。资源为
single-thread CPU，GPU/API/base-LLM update=0；预计墙钟小于 30 分钟。
