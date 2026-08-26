# Historical v11 train ↔ provisional first-960 fuzzy overlap

状态：`FORMAL_PROVISIONAL_HISTORICAL_TRAIN_FUTURE_OVERLAP_COMPLETE`

本结果包回答一个 benchmark-integrity 问题：曾用于 v11 critic 训练的历史端点，与 outcome-blind chronological
first-960 当前前缀中的代码，在结果前固定的 lexical token-shingle/Jaccard 定义下是否高相似。

## 固定输入与正式结果

- source commit：`f9c6de27afd933d9ceee04e67acbd51d25947798`
- prospective snapshot：`8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248`
- 历史侧：5,816 train rows、5,519 unique endpoints、333 physical runs、23 tasks；5,519/5,519 可 fingerprint。
- 前瞻侧：366 runs、10,683 endpoints；10,674 可 fingerprint，coverage=`0.9991575400168492`。
- primary：token 5-gram、BLAKE2b-128、minimum 20 distinct shingles、Jaccard≥`17/20=0.85`。
- exact candidate checks=`2,880`；near-duplicate pairs=`0`；same-task/cross-task=`0/0`；两侧 affected endpoints=`0/0`；components=`0`。
- strict sensitivity Jaccard≥`19/20=0.95`：near-duplicate pairs=`0`。
- 固定 256×256 subset 的 65,536 个 pairs 上，prefix join 与 brute force edge set/digest 完全一致。
- 六个结果前 gate 全部通过，`strong_low_historical_train_future_overlap_support=true`。

producer A/B 与 non-importing verifier A/B 均逐字节一致；focused/full tests=`14/1182 passed`，full 有 47 warnings；
forbidden-path/credential hits=`0/0`，GPU/API/model-fit/base-update=`0/0/0/0`。producer/verifier wall time 分别为
`6:21.20/6:25.34`，最大 RSS 为 `4,643,904/4,641,060 KiB`。

正式 producer / verifier / remote formal manifest SHA-256：

- `fbba6dbe10937b7376b4bb2b052934bcf1b47cf16610ab2be872d0101ae28194`
- `7f3c0c7be582efdf4c747d7fe9a7cd7d47d33564788e62dabea45374180ee188`
- `8b4dc3aef2ada8f848362f049517511bd2658d847f5911f32435206c48c55730`

另一个不修改 formal root 的独立 recheck 验证了 21 个 manifest payload、全部固定计数、A/B byte identity、禁读路径
和凭据扫描；其 manifest SHA-256 为
`91e368c6e81e2dd3eb19791f1ed509697bcc29d67fb7c389ee0c34416d6c3713`。

## 允许与禁止的解释

允许写：**在结果前固定的 lexical token-shingle/Jaccard 定义下，历史 v11 critic-train endpoints 与 366-run
provisional future cohort 没有高相似链接。** 这强化了时间外 benchmark 的 train→future lexical independence。

禁止写：semantic clone 不存在、identifier-renamed clone 不存在、预训练污染不存在、predictor 没有其他泄漏、critic
有效，或最终 first-960 已经独立。当前只有 366/960 runs，closure=false；first-960+独立 accrual closure 后必须按同一
协议重跑，不能改 tokenizer、threshold、最低长度、历史人口或 gate。

## 文件

- `formal_summary.json`：精简正式汇总；
- `producer_receipt.json`：完整 producer receipt；
- `independent_verification.json`：non-importing verifier receipt；
- `independent_recheck.json`：formal 目录第二层独立复核；
- `focused_tests.txt` / `full_tests.txt`：正式 source commit 的测试输出；
- `preflight_13.txt` / `access_attestation.txt`：预检与访问安全证明；
- `producer_resource.txt` / `verifier_resource.txt`：资源记录；
- `remote_formal_SHA256SUMS` / `remote_recheck_SHA256SUMS`：远端完整证据链清单；
- `failure_history.md`：未完成尝试，均无科学结果且未覆盖成功目录；
- `SHA256SUMS`：本公开包的内部清单。

结果前预注册：`phase1/实验记录/2026-08-26/HistoricalTrain_First960_FuzzyOverlap_v1_结果前预注册.md`。
