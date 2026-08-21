# TraceML Human Fork Future：S1 正式裁决

日期：2026-08-21。正式状态：`IDENTITY_OR_JOIN_AMBIGUOUS`。结论是外部数据 join 资格失败，**不是** transition
scorer 效果为负；AIRA strict-future 0CP 不受影响。

## 1. 冻结门的结果

精确 commit `bae0802895214851983fa99eee784e651648d384` 的 producer×2 与完全独立 verifier×2 得到相同
聚合。134 个 graph competitions 在 141-entry manifest 中均有且仅有一个合法 direction；7 个 unused entries 被
显式列出，先前 134/141 差异本身不是失败原因。失败来自 graph tables 内部：

- node→kernel 要同时匹配 kernel ID 与 competition，4,674/174,558 不一致（0.0267762005）；
- node→tree 要同时匹配 tree ID 与 competition，906/174,558 不一致（0.0051902520）；
- 409 个 canonical fork 中 6 个 parent/child tree-comp 不一致（0.0146699267）；
- 剩余 403 个 fork 的 parent、depth+1、first-version、child-kernel uniqueness 与 edge-table exact multiplicity 均过，
  但冻结协议禁止结果后删掉异常行再定义子集。

所以 `identity_and_direction=false`，程序在 score-column open 之前停止。`best_private_score`、`score_public`、finite
support、task dominance、predictor effect 均未读取/计算；raw notebook 未下载，S2/S3 关闭。

## 2. 根因边界

固定官方 `build_graph_tables.py` 用 `kid_to_meta.get(kernel_id, {})` 拼接 kernel metadata，却不检查 node competition
是否与 kernel competition 一致；固定 `build_forest.py` 先用所有边做 weak components，再把每棵 tree 的 `comp`
直接设为 primary root 的 competition，也不检查全部 members 同 comp。公开 parquet 因而可以成功 materialize，
但这不能告诉我们跨 comp node 应使用哪一个 leaderboard metric，也不能为 6 个跨 comp canonical forks 提供唯一
label。后验过滤会改变预注册 population，不能作为本轮修复。

该发现可作为 dataset integrity 审计素材；不能写成 TraceML 整体不可用，更不能写成 critic/future-potential 不成立。
若未来上游发布新 revision 并修复 join，只能另立 revision、新预注册和新 S0，不得覆盖本轮。

## 3. 复现与资源

focused=9 passed；全量=591 passed / 25 warnings。producer 与 verifier 各两次 byte-identical；52-file manifest、
forbidden path=0、credential=0、writable files=0。summary SHA=`df469bbd...78c2`，verification SHA=
`21f4c5e1...fee2`。正式 producer 26.21s、max RSS=455,716KB；S0/S1 预估 `<100MB` 不准确，现如实更正。

commit `878e719...` 的预读 attempt 因未显式限制 CPU thread pools，在任何 producer/graph 读取前中止并独立只读
封存；新 commit 固定 OpenBLAS/OMP/MKL/NumExpr/BLIS/vecLib=1 与 `PYTHONHASHSEED=0` 后完成正式运行。两次 attempt
都没有 GPU/API/base-LLM update。
