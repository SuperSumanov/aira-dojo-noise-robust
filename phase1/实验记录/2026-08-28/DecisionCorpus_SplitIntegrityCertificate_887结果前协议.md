# Decision Corpus Split-Integrity Certificate：887 结果前协议

冻结时间：2026-08-28T05:34:48Z。此时 435-run 内部 identifier-erased verifier B 与 435-run historical→future
producer A 都尚未完成，两个真实结果均未读取。

## 要形成的正资产

本项不再增加一个零散 clone 数字，而是把同一表示、同一阈值、同一 435-run population 上的两条证据组合成机器可验的
provisional split-integrity certificate：

1. future population 内部，跨 physical run 是否存在 identifier/literal-erased 高相似链接；
2. 固定历史 v11 critic-train population 到 future population，是否存在同定义链接。

两项都使用 `python_token_identifier_erased_v1`、token 5-gram、Jaccard 17/20 primary、19/20 strict sensitivity；不按
task/run 预筛。certificate builder 只允许读取两份 formal summary、independent postflight 与 manifest，不得重新打开 raw
corpus、archive 或 identity-bearing edge。

## 结果前分类

- 两份 postflight 与全部 gates 通过，且内部 cross-run links=0、historical→future links=0：
  `PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE`；
- gates 均通过但至少一个零链接条件为假：`PROVISIONAL_LOW_OVERLAP_CERTIFICATE_WITH_EXCEPTIONS`，必须报告全部非零计数；
- 任一 postflight 或 gate 失败：`NO_SPLIT_INTEGRITY_CERTIFICATE`。

顺序固定，strict sensitivity、子集或某个 task/run 都不能 rescue。builder A/B 与 non-importing verifier A/B 必须各自
逐字节相同；输入 formal/postflight manifests 必须逐项通过。

## 边界

即使最高档通过，也只说明固定 syntactic abstraction 与 0.85 阈值下，在 fingerprintable endpoints 中未发现两类链接。
它不证明 semantic clone 或 pretraining contamination 不存在，不覆盖所有可能的历史训练来源，也不认证低于 minimum
shingle 的 endpoints。当前 closure=false，first-960+closure 后必须原协议重建。因此这是 D&B benchmark-integrity 正资产，
不是 predictor effect 或新 clone-detection 方法。

prospective label/outcome/prediction/accuracy/effect/utility、raw senior archives 及 task/run/card/code/edge identities 禁读；
GPU/API/model-fit/base-update=`0/0/0/0`。
