# First-960 内部 identifier-erased clone audit：887 snapshot

状态：`STRICT_LINEAGE_LOCAL_PASS`。这是 provisional Decision Corpus split-integrity 结果，不是 predictor effect。

固定 snapshot `887491a...` 含 435 physical runs、11,906 endpoints；11,894 endpoints 可在结果前冻结的
`python_token_identifier_erased_v1` 表示下 fingerprint，coverage=`0.9989921048210986`。该表示去 comment/layout，
保留 keyword/operator，并把其他 NAME、NUMBER、STRING 分别映射为固定 token。

primary Jaccard≥0.85 下精确检查 7,990,766 个 candidate pairs，得到 11,421 个 near-duplicate links：
parent-child=`5,713`、same-parent siblings=`235`、same-run other=`5,473`、cross-run same-task=`0`、
cross-run cross-task=`0`。strict Jaccard≥0.95 有 4,068 links，跨 run 仍为 0。因此高相似性很多，但在固定抽象下严格
局限于同一 physical run 的 lineage，而不是跨 run 复制。

producer A/B、independent verifier A/B、384-document brute-force control、五项 gates、focused=`27 passed`、
full=`1240 passed, 47 warnings`、forbidden-path 与 credential gates 均通过。结果前冻结的 independent postflight 也通过。

边界：本项不证明 semantic clone 或 pretraining contamination 不存在，也不认证未达到 minimum 20 distinct shingles 的
12 个 endpoints；当前 closure=false，first-960+closure 后必须原协议重跑。GPU/API/model-fit/base-update=`0/0/0/0`。
