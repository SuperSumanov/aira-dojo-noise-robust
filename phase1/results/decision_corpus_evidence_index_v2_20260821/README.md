# Decision-Corpus evidence index v2

正式状态：`INDEPENDENTLY_VERIFIED_SOURCE_AWARE_EVIDENCE_INDEX`。控制 commit：
`8da197b89ebe513df0516cf71186c068078bf67b`。

v2 在不合并 estimand 的前提下，把 v1 的五项证据扩为六项：

| 条目 | 经哈希绑定的正证据 | 强制边界 |
|---|---|---|
| decision corpus | 发布 pair 是 context-consistent、physical-run sibling，且同预算 train/frozen 隔离 | 不证明完整 source choice set、预测准确率或搜索收益 |
| source opportunity | 3,252 parents 的 fragment 边界；870 个不完整 parent 中 721 个可恢复身份；996 个 missing identities 中 902 个恢复 journal status | 不恢复 missing numeric outcome；不假定 MAR；不允许 complete-choice-set 语言 |
| label repeatability | 10-task 独立 regrade 子集的 pair-order raw agreement=`0.9658601259529334` | transported ceiling 依赖已披露假设，不是 predictor accuracy |
| normalized clone | 预注册 token/AST 覆盖范围内跨 run、跨 task duplicate endpoints 均为 0 | AST 强 coverage 门失败；不排除 fuzzy/语义/训练污染 |
| deployment cost | 18 fits、4,608 queries 的 A/B 成本正门与跨运行稳定性通过 | 不计算 frozen accuracy，不证明 search acceleration |
| prospective gate | first-960 cohort outcome-blind 累积且保险库保持关闭 | cohort/closure 未完成，不能写 prospective effect |

其中 source-opportunity 的 902 个已恢复节点为 893 个 `EXECUTION_ERROR` 与 9 个
`OFFICIAL_GRADE_ABSENT`；另有 94 个仍为 unknown。正确 estimand 因而是
`quality | generated and successfully executed/evaluated`，不能把 labeled fragment 无条件外推为 agent 面对的全部候选。

独立 verifier 从固定 v1 index 与冻结 v2 schema 重建整份 index，再逐一核对 18 个 artifact 的 UTF-8/LF
规范化 SHA-256 和 136 个 JSON assertions；不 import builder。正式双 builder、双 verifier 都逐字节一致；
全套 phase tests 为 `620 passed, 1 skipped, 25 warnings`，两类秘密扫描均为 0，
`prospective_outcomes_read=false`。index normalized SHA-256=
`fdb77b4458c4342a0fa62c860ed7141478e38a1dc5c26ac369e70ba961ff5c02`；正式 `SHA256SUMS` 文件 SHA-256=
`03f9776ed84fb97bdafaf62f890bedc3fbbb30b3d0031fdb699c76269d41c74b`。

Linux 正式 verifier 与本地回传后 verifier 输出逐字节相同，SHA-256=
`602a4f721e0d7e386917deeab31245ef3f621f0e05b2c3459efabd26abb1e3bd`。复核命令：

```bash
python -m phase1.verify_decision_corpus_evidence_index_v2 \
  --repo-root . \
  --index phase1/results/decision_corpus_evidence_index_v2_20260821/index.json \
  --out /tmp/decision_corpus_evidence_index_v2_verification.json
```

本 README 是正式 bundle 回传后的解释文件，不在远端只读 `SHA256SUMS` payload 内；其余文件均来自
`/research/d7/spc/yzyang4/decision-corpus-evidence-index-v2/8da197b-v1`。
