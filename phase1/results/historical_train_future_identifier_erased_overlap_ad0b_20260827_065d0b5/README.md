# Historical v11 train ↔ provisional first-960 identifier-erased overlap

状态：`FORMAL_PROVISIONAL_IDENTIFIER_ERASED_OVERLAP_AUDIT_COMPLETE`

本结果包回答一个 benchmark-integrity 问题：曾用于 v11 critic 训练的历史端点，与 outcome-blind chronological
first-960 当前前缀中的代码，在结果前固定的 identifier/literal-erased token-shingle/Jaccard 定义下是否高相似。

## 固定输入与正式结果

- source commit：`065d0b56fdc366d05faf723ef03938e7f7a913f2`
- prospective snapshot：`ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e`
- 历史侧：5,519 unique train endpoints、333 physical runs；5,519/5,519 可 fingerprint。
- 前瞻侧：404 runs、11,310 endpoints；11,299 可 fingerprint，coverage=`0.999027409372237`。
- primary：Python tokenizer 删除 comment/layout；hard keyword/operator 保留；其他 NAME、number、string 分别
  归一为固定 token；token 5-gram、BLAKE2b-128、minimum 20 distinct shingles、Jaccard≥`17/20=0.85`。
- exact candidate checks=`5,923,921`；near-duplicate pairs=`0`；same-task/cross-task=`0/0`；两侧 affected
  endpoints=`0/0`；components=`0`。
- strict sensitivity Jaccard≥`19/20=0.95`：near-duplicate pairs=`0`。
- 固定 256×256 subset 的 65,536 个 pairs 上，prefix join 与 brute force edge set/digest 完全一致。
- 六个结果前 gate 全部通过，`strong_low_identifier_erased_overlap_support=true`。

producer A/B 与 non-importing verifier A/B 均逐字节一致；focused/full tests=`29/1212 passed`，full 有
47 warnings；forbidden-path/credential hits=`0/0`，GPU/API/model-fit/base-update=`0/0/0/0`。producer/verifier
wall time 分别为 `11:52.58/12:04.06`，最大 RSS 为 `2,919,188/2,857,124 KiB`。

正式 producer / verifier / remote formal manifest SHA-256：

- `409c9f046917a98f6bf26b6cac87fa1e688bccff68daf41fd9930f268d7182b6`
- `866536e98138e0ad60929afe8324e8f64a98c05784e351eb6de13a3cc8fa44e0`
- `f2e88098a61bf4144ae0692da571dc513ff7ec31ee3fbfad278bb94f61374ae2`

另一个不修改 formal root 的独立 recheck 验证了 24 个 manifest payload、全部固定计数、A/B byte identity、
禁读路径和凭据扫描；其 manifest SHA-256 为
`8f6adbd77de730977b81d418f166e5a53fc48cbaf544c9495b01ad55da7ea188`。

## 允许与禁止的解释

允许写：**在结果前固定的 identifier/literal-erased syntactic token-shingle/Jaccard 定义下，历史 v11
critic-train endpoints 与 404-run provisional future cohort 没有高相似链接。** 由于该表示比 lexical v1
更激进地消除了变量名与字面量，这加强了时间外 benchmark 的 train→future syntactic independence 证据。

禁止写：semantic clone 不存在、预训练污染不存在、predictor 没有其他泄漏、critic 有效，或最终 first-960 已经独立。
当前只有 404/960 runs，closure=false；first-960+独立 accrual closure 后必须按同一协议重跑，不能改 tokenizer、
threshold、最低长度、历史人口或 gate。

## 文件

- `formal_summary.json`：精简正式汇总；
- `producer_receipt.json`：完整 producer receipt；
- `independent_verification.json`：non-importing verifier receipt；
- `independent_recheck.json`：formal 目录第二层独立复核；
- `focused_tests.txt` / `full_tests.txt`：正式 source commit 的测试输出；
- `preflight_13.txt` / `access_attestation.txt`：预检与访问安全证明；
- `producer_resource.txt` / `verifier_resource.txt`：资源记录；
- `remote_formal_SHA256SUMS` / `remote_recheck_SHA256SUMS`：远端证据链清单；
- `failure_history.md`：未完成尝试，无科学结果且未覆盖成功目录；
- `SHA256SUMS`：本公开包的内部清单。

结果前预注册：`phase1/实验记录/2026-08-27/HistoricalTrain_First960_IdentifierErasedOverlap_v1_结果前预注册.md`。
