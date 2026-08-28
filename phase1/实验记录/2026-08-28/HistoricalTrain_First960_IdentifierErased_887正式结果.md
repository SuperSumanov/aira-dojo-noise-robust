# Historical train → first-960 prefix identifier-erased：887 正式结果

## 裁决

`ZERO_IDENTIFIER_ERASED_LINKS`。

结果前协议固定在 source commit `ec67d1a6f31bde898631019867408687bac1fa99`，协议 SHA-256 为
`aa3b232c732c53bb24bf2fbac6932276d458f2e6a6ae20321edee0ff2d04ca1b`。正式运行只把已知 404-run 结果
顺序外延到同一 first-960 时间序列的 435-run snapshot `887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；
新增 31 runs，不声称这是独立于 404-run 的全新发现。

## 固定人口与结果

- 历史 v11 critic-train：5,519 endpoints / 333 physical runs；5,519 可 fingerprint，coverage=`1.0`。
- 前瞻：435 runs / 11,906 endpoints；11,894 可 fingerprint，coverage=`0.9989921048210986`。
- 表示：`python_token_identifier_erased_v1`；primary Jaccard=`17/20`，strict sensitivity=`19/20`。
- primary exact candidate checks=`6,172,443`；near-duplicate links=`0`；same-task/cross-task=`0/0`。
- 历史/前瞻 affected endpoints=`0/0`；components=`0`；strict links=`0`。
- 六个 gate 全真；`strong_low_identifier_erased_overlap_support=true`。

producer A/B、non-importing verifier A/B 均逐字节一致；256×256 brute-force control 一致；focused=`32 passed`，
full=`1247 passed, 47 warnings`。forbidden-path/credential=`0/0`，历史 label/observation 字段未用于计算，前瞻
outcome/prediction value 未读，GPU/API/model-fit/base-update=`0/0/0/0`。

## 结果前与结果后完整性

- formal root：`/research/d7/spc/yzyang4/historical-train-future-identifier-erased-overlap/formal-ec67d1a-887491a-v1`
- deployment root：`/research/d7/spc/yzyang4/historical-train-future-identifier-erased-overlap/deploy-ec67d1a-887491a-v1`
- postflight root：`/research/d7/spc/yzyang4/historical-train-future-identifier-erased-overlap/postflight-ec67d1a-887491a-v1`
- formal / deployment / postflight manifest SHA-256：
  `42c5875cc160410176946b261ebdb2571677a28b5af180c38b5434c171221a28` /
  `a230bcf7100cb68138c21bc9cbb58729d6f852fdff97bef28cb548449e030988` /
  `3fba262747830208a40b7a4cf673f93990d5814670b538ac2a87c5acc8c19e67`。
- independent recheck 在 formal `COMPLETE` 前冻结：逻辑 SHA-256=
  `0ce8df4d2ecee8f102a2780e743bc17335fb8778be06772526ca12ccac1496dc`；finalizer SHA-256=
  `e122bf4ed44160957b9659e6a789aeaca39b7b9d5f4daa8cdca7ff53b10e51d0`。
- formal summary / independent recheck SHA-256：
  `87e7298376319ab0afd1aa5bdbb7990fdfbe071513b3981f5fc203c74c678f27` /
  `6e666a0691657b46dee11e76593e342efb94b9de62b44d18ac1aa0cd26d53565`。

## 可以写与不能写

可以写：在固定 identifier/literal-erased syntactic representation、阈值、历史人口和 435-run future snapshot 下，
未发现历史 critic-train→future 的高相似链接。这与同一 snapshot 内部“11,421 个高相似链接全部 run-local”的结果一起，
支持 run-clean 时间前瞻切分在该固定语法定义下没有跨 split 高相似污染。

不能写：semantic clone 不存在、pretraining contamination 不存在、全部历史训练源均被覆盖、12 个不可 fingerprint
endpoints 已获认证、predictor 有正效果，或 first-960 已 closure。最终 960 runs + 独立 closure 后必须原协议重跑。

公开结果包：`phase1/results/historical_train_future_identifier_erased_overlap_887_20260828_ec67d1a/`。
