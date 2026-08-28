# Decision Corpus 435-run split-integrity certificate：正式结果

## 裁决

`PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE`。

这是本轮最实质的正方向结果：在同一 outcome-blind 435-run future snapshot、同一
`python_token_identifier_erased_v1` 表示和预注册阈值下，机器证书同时确认：

1. future 内部有大量高相似代码，但 0.85 下 11,421 links、0.95 下 4,068 links 全部局限于同一
   physical run；跨 run 都是 0。
2. 固定历史 v11 critic-train population 到 future 的 0.85/0.95 links 都是 0。

因此，当前证据支持“高相似性来自同一搜索 lineage 的局部迭代，而不是跨 physical-run 或固定
historical-train→future 的复制”这一 benchmark-integrity 主张。

## 机器证书

- source commit：`25efd3a9237e93177e3c8c91b8f73169a70d4213`
- future snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`
- future population：435 runs / 11,906 endpoints / closure=false；11,894 可 fingerprint。
- historical population：333 runs / 5,519 endpoints；5,519 可 fingerprint。
- primary/strict threshold：`17/20` / `19/20`。
- 七个 certificate gates 全部为 true：两侧 integrity、两项 zero-link、同一 future population、同一表示与阈值、
  两个 independent postflight。

builder A/B 与 non-importing verifier A/B 各自逐字节一致；focused=`7 passed`，full=
`1260 passed, 47 warnings`。正式 runner 重新校验两份 Git 安全结果包，以及 within/historical 各自的 formal 与
postflight 原始清单；没有重新打开 raw corpus/archive 或 task/run/card/code/edge identities，prospective
outcome/prediction values 未读，GPU/API/model-fit/base-update=`0/0/0/0`。

## 证据绑定

- result-before protocol SHA-256：`779ac3f1f5aef522a305b22b578dace2c0a8462fe748a7cd1b30dd20037ef5da`
- certificate / independent verification SHA-256：
  `b44035bd073a83d4c57a03550db9c4b88af8afa8df95268c42f18541cdccca5c` /
  `45dc560b882b31df3564740bd619ac2c7248a9edcc19656a8ef865f0720af944`
- formal / deployment manifest SHA-256：
  `a7e6aeb9e806ebeb70b9d7ddd2089c08b6cd6716ec2cd70921b20fcf4a1a7161` /
  `92833795950123c9e77dcb09f9f1323957cce5ec8eab8eead5d68d50b4056ed1`
- formal root：`/research/d7/spc/yzyang4/split-integrity-certificate-887/formal-25efd3a-887491a-v1`
- deployment root：`/research/d7/spc/yzyang4/split-integrity-certificate-887/deploy-25efd3a-887491a-v1`

## 解释边界

允许写：固定表示与阈值下，没有发现跨 future physical runs 的高相似链接，也没有发现固定历史
critic-train population→future 的高相似链接；这是一份可重建、机器可验的 provisional split-integrity certificate。

不能写：semantic clone 或 pretraining contamination 不存在、所有历史训练源均覆盖、12 个不可 fingerprint endpoints
已认证、predictor accuracy/effect/search utility 为正，或最终 first-960 已完成。当前只有 435/960、closure=false；
最终 cohort + closure 后必须不改协议重跑。

公开结果包：`phase1/results/split_integrity_certificate_887_20260828_25efd3a/`。
