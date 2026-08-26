# Agentic Benchmark Checklist Crosswalk v2：清洁证据迁移预注册

冻结时间：2026-08-26T14:56:38+08:00。本文写在任何 crosswalk v2 formal artifact 生成或提升之前；本地实现与
smoke 可先行，正式件只能从随后公开的精确 source commit 在 fresh Linux worktree 生成。

## 1. 迁移目的与 source v1 的有限角色

ABC crosswalk v1 的 24 项人工判断与保守状态仍可作为文本模板，但其 evidence catalog 含已撤回的 v6、prediction
coverage matrix 和 task-balance guard v1。v2 允许打开 hash-pinned v1 `crosswalk.json` 来迁移 checklist item 文本、
status、ownership、外部 URL 与 remaining gaps；不允许打开 v1 catalog 指向的六个受污染 evidence artifacts，也不继承
v1 的 access attestation。

source v1 normalized-LF SHA-256=
`fb622cd16e95d6e340ce6fba4bf6661329ec005ec43b184b5ef3cbf29d179b1b`。旧 v1 文件保持 immutable historical record，
不删除、不覆盖。

## 2. 冻结迁移

删除 6 个 evidence IDs：`evidence_index_v6`、`evidence_index_v6_independent`、`coverage_7cda`、
`coverage_7cda_independent`、`balance_guard`、`balance_guard_independent`。

加入 11 个 clean IDs：v7 index/independent、receipt-only common support/independent、taint registry、structural-weight
trajectory/independent、opportunity-yield audit/independent、task-balance structural-only v2/independent。最终 catalog
固定为 29 files，24 个 ABC items 必须全部引用且无孤儿证据。

受影响 rationale 只做 provenance-aware 改写，不改变 criterion、ownership、external URLs 或 remaining gaps。24 项 status
必须与 v1 逐项完全相同：PASS_LOCAL/PARTIAL/INHERITED_UPSTREAM/NOT_APPLICABLE=`9/9/5/1`；特别是 T.1、T.6、
T.10、R.1、R.3、R.10、R.12 仍 PARTIAL，R.13 仍 NOT_APPLICABLE。不得利用 clean migration 升级任何人工 PASS。

## 3. 认识与访问边界

机器 verifier 只认证 schema、item set/order、保守 status、引用闭包、路径安全与本地 evidence SHA-256；不认证人工
semantic assessment，也不计算 aggregate compliance score。receipt-certified support 不等于 orientation/tie/margin、
accuracy/effect/utility；结构 weighting 与 task-balance 不等于 method effect 或 producer compliance。

formal 允许读取 source v1 crosswalk template 本身；禁止打开 v6、withdrawn matrix、task-balance v1/forward v1、prediction
pair/value、prospective label/outcome 或 raw archive payload。GPU/API/model-fit/base-LLM update=`0/0/0/0`。

## 4. 正式门与杀死条件

- builder A/B 与 non-importing verifier A/B 分别必须逐字节一致；
- items/evidence/status-count 固定为 24/29/(9,9,5,1)；
- 6 个 removed IDs、5 类 forbidden path fragment 在 candidate catalog/items 中必须为零；
- 11 个 added IDs 均须 hash 验证且至少被一个 item 引用；所有 29 个 catalog entries 必须无 orphan、无重复路径；
- production trace 中 source v1 template 精确打开一次或多次是允许事件，但 source v1 的六个 removed evidence artifacts、
  prediction/outcome 路径命中必须为 0；
- focused/full tests、13 项预检、clean worktree、credential scan、manifest 任一失败，不得 `COMPLETE` 或提升；
- verifier 不得 import builder；semantic certification 与 aggregate score 永远为 false。

冻结前本地 smoke=`11 passed, 1 skipped`，只证明实现能运行，不是 formal evidence 或新的 D&B compliance 分数。
