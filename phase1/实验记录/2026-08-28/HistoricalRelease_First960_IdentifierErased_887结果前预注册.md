# 完整 v11 release → First-960(435-run) identifier-erased overlap 结果前预注册

冻结时间：2026-08-28T06:49:40Z

状态：`RESULT_BLIND_PROTOCOL_FROZEN`

协议：`phase1/historical_release_future_identifier_erased_887_protocol_v1.json`

协议 SHA-256：`22f2d4f4853c11398429c40f91f952711ee2003bc27bec7c977726c82f0771ea`

## 问题与人口

在不读取 prospective label、outcome、prediction、accuracy 或 search utility 的前提下，检查完整、可逐字节重建的
v11 历史 release 是否与固定 435-run chronological future snapshot 存在 identifier/literal-erased 高相似链接。

- historical：`cards_current_v11.jsonl`，SHA-256=`6794acbf...01b75`，16,012 endpoints、667 runs、25 tasks；
- future：snapshot=`887491a...`，11,906 endpoints、435 runs、34 tasks，closure=false；
- 两侧 physical runs 必须零交集。

已知信息必须披露：历史 critic-train 子集 5,519 endpoints 到同一 future 的 primary links=0 已知；within-future
cross-run primary links=0 也已知。因此本轮是人口扩张，不是独立 discovery cohort。

## 固定表示、门与解释顺序

- Python tokenize；去 comments/layout；非 keyword identifier→`<IDENT>`，number/string 分别统一；
- 5-token shingles，BLAKE2b-128，至少 20 个 distinct shingles；
- primary Jaccard≥17/20；strict sensitivity≥19/20，后者不得 rescue primary；
- 不按 task/run 预筛 candidate；exact prefix join，固定 256×256 brute-force equality control；
- fingerprint coverage 两侧≥0.99；future affected fraction≤0.01；cross-task future affected fraction≤0.005；
  至少 10 endpoints 且至少 3 tasks 的 large multi-task components 必须为 0。

解释顺序在结果前固定：

1. 所有门过且 primary links=0：`ZERO_IDENTIFIER_ERASED_RELEASE_LINKS`；
2. 所有门过但 links>0：`LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS`；
3. 任一门失败：`RELEASE_SPLIT_INTEGRITY_GATE_FAIL`。

不允许改 population、representation、threshold、task、subset、gate 或顺序来 rescue；失败根保留 immutable
`FAILED_RC`。结果仅支持固定 syntactic relation 下的 temporal-release integrity，不证明 semantic clone 或
pretraining contamination absence，也不提供 predictor effect。

## 复现与资源

producer A/B 与不 import 新 producer 的独立 verifier A/B 均须逐字节一致；source commit、协议、v11 release receipt、
snapshot 输入与全部依赖逐哈希绑定。正式运行前后 `LATEST` 必须仍为同一 887 snapshot。focused 预检为
`18 passed`。CPU-only；每个命令 timeout=1,800s、virtual memory=32 GiB；GPU/API/model-fit/base-update=
`0/0/0/0`。
