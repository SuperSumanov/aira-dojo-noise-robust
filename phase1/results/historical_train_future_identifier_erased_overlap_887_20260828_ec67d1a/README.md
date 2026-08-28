# Historical v11 train → 435-run future identifier-erased overlap

状态：`ZERO_IDENTIFIER_ERASED_LINKS`。这是 provisional Decision Corpus split-integrity 结果，不是 predictor effect。

固定历史人口含 5,519 个 critic-train endpoints / 333 physical runs；固定 future snapshot `887491a...` 含
435 runs / 11,906 endpoints。历史侧 5,519/5,519、前瞻侧 11,894/11,906 可在结果前冻结的
`python_token_identifier_erased_v1` 表示下 fingerprint，coverage 分别为 `1.0` 和 `0.9989921048210986`。

primary Jaccard≥0.85 下精确检查 6,172,443 个 candidate pairs，得到 0 个 near-duplicate links；
same-task/cross-task=`0/0`，历史/前瞻 affected endpoints=`0/0`，components=`0`。strict Jaccard≥0.95
同样为 0。该结果把已知 404-run 零链接结论严格外延到同一时间序列中的 435 runs（新增 31 runs），
因此是顺序外延，不冒充全新独立发现。

producer A/B、non-importing verifier A/B、256×256 brute-force control、六项 gates、focused=`32 passed`、
full=`1247 passed, 47 warnings`、forbidden-path 与 credential gates 均通过。结果前冻结的 independent
postflight 也通过；label/outcome/prediction value、GPU/API/model-fit/base-update=`false/false/false/0/0/0/0`。

允许主张：在固定表示、历史人口、future snapshot 和阈值下，没有发现历史 critic-train→435-run future 的
高相似语法链接。禁止外推为 semantic clone 或 pretraining contamination 不存在，也不覆盖其他未知历史训练源；
12 个未达到最小 shingle 数的前瞻 endpoints 不在本证明内。当前 closure=false，first-960+closure 后必须原协议重跑。
