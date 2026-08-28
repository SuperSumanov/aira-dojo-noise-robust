# Historical train ↔ first-960 identifier-erased：887 时间外延预注册

冻结时间：2026-08-28T05:21:33Z。本协议写在读取 435-run historical↔future similarity 结果之前。

## 固定问题与人口

历史侧逐字节复用 v11 三个 `intask_split=train` pair 文件与 `cards_current_v11.jsonl`：5,816 rows、5,519
unique endpoints、333 physical runs、23 tasks。前瞻侧固定为 snapshot `887491a...` 的 chronological
provisional first-960：435 runs、11,906 endpoints、3,053 structural pairs、34 tasks、closure=false；registry、ledger
和 summary SHA 均写入机器协议。

404-run ad0b 的 0-link 结果已经公开，因此本项是增加 31 runs 的 sequential temporal extension，不包装成完全独立发现。
但 435-run 的任何 similarity、affected endpoints、components 或 gate 状态在本文冻结前均未读取。

## 表示、门与解释顺序

表示完全不变：Python tokenizer 去 comment/layout，保留 keyword/operator，其他 NAME/NUMBER/STRING 分别映射到固定
token；5-token shingle、BLAKE2b-128、minimum 20 distinct shingles，不按 task/run 预筛。primary Jaccard=`17/20`，
`19/20` 只作 strict sensitivity，不能 rescue。

解释顺序预先固定：

1. 六项 integrity gates 全通过且 primary link count=0：`ZERO_IDENTIFIER_ERASED_LINKS`；
2. gates 全通过但 link count>0：`LOW_IDENTIFIER_ERASED_OVERLAP_ONLY`；
3. 任一 gate 失败：`INTEGRITY_GATE_FAIL`。

通过最多支持固定 syntactic abstraction 下未发现历史训练端与 435-run future prefix 的高相似链接；不证明 semantic
equivalence absence、pretraining contamination absence，也不提供 predictor effect。first-960+closure 后仍须原协议重跑。

## 复验与安全

正式运行必须来自包含本协议的 clean public commit，执行 producer A/B、non-importing verifier A/B、256×256 brute-force
control、focused/full tests、稳定 LATEST、strace forbidden-open 与 credential gates，再做结果前冻结逻辑的独立 postflight。
禁止 prospective label/outcome/prediction/accuracy/effect/utility、raw senior archive，以及把历史 label/observation 字段作为计算
输入。GPU/API/model-fit/base-update=`0/0/0/0`；失败后不得换表示、阈值、人口、task/run 或解释顺序。
