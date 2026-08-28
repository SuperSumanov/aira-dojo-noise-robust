# Historical release→future 与 Evidence Index v8 正式闭环

日期：2026-08-28

future snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

## 一句话结论

在结果盲、physical-run-bound 的固定 syntactic relation 下，完整可重建 v11 历史 release 到当前 435-run future
的 18,510,294 个 primary candidate pairs 中没有发现任何链接；该证书已经机器化并入 16-entry Evidence Index v8，
但在 first-960 与 closure 前仍严格标为 provisional。

## 1. 为什么这次比此前证书更强

此前 historical→future 零链接证书的历史侧只覆盖 5,519 个 critic-train endpoints。完整 release 审计把历史侧扩到：

- 16,012 endpoints；
- 667 physical runs；
- 25 tasks；
- cards SHA-256=`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`。

future 仍绑定同一 outcome-blind snapshot：11,906 endpoints、435 runs、34 tasks、closure=false。因此这是人口覆盖的
严格扩张，不冒充此前完全未知的独立发现。

## 2. 冻结协议与正式结果

表示固定为 `python_token_identifier_erased_v1`；primary 阈值 Jaccard 17/20，strict sensitivity 19/20。任务与 run
不用于 candidate prefilter。六个门覆盖历史/future fingerprint coverage、future affected fraction、跨任务 affected
fraction、大型多任务 component 以及 bipartite join self-check；任何门失败均优先于漂亮的链接计数。

正式结果：

- historical fingerprint：16,012/16,012；
- future fingerprint：11,894/11,906；未覆盖 12 个 endpoints（10 tokenization failure、2 too short）；
- primary exact candidate pairs：18,510,294；
- primary links / affected historical / affected future / components：0 / 0 / 0 / 0；
- strict links：0；
- classification：`ZERO_IDENTIFIER_ERASED_RELEASE_LINKS`；
- all pre-registered gates：pass。

## 3. 资源失败没有被隐藏

首轮 1,800 秒 envelope 在 producer 完成前超时：formal rc=124、deployment rc=1，没有创建 producer result，也没有
读取失败轮结果值。r2 唯一资源改动是把 envelope 改为 5,400 秒；表示、阈值、人口、门和分类规则全部不变。

r2 三套原始 manifest：

- formal：`4089cef1c7a42886ae6a363d3854e2f4e89e254829549a4681ea6bfaaed80fac`；
- postflight：`868a11eda261ea78f71f4148eb60bf7b36a4b413ee708b7bbc03da3d1c6f5a98`；
- deployment：`9a178a93e4f2b074363f120a3e1974c47f003cf874a6b0f13942ffede16af69c`。

producer A/B、formal verifier A/B、fresh postflight verifier A/B 均逐字节一致；subset brute-force self-check 一致。
focused/full=`19/1269 passed`，full 有 47 warnings。发布的 aggregate-only 紧凑包 manifest 为
`152f6f7c2d12f8c47e0fd809a56eb2a3ad8cd3dac826b62115c994201a0da985`。

## 4. Evidence Index v8

v8 结果前协议 SHA-256=`a463a6e7ede5bb9b46dbe6081ae46d26d6c2e8410e858acf9d022c642633deda`。
它不修改 clean-provenance v7 的 14 entries，只按固定顺序追加：

1. physical-run split integrity certificate；
2. complete-release temporal-overlap certificate。

正式结果为 16 entries、43 artifacts、3 bound files、499 exact JSON assertions。builder A/B 与不 import builder 的
verifier A/B 均逐字节一致；focused/full=`30/1288 passed`，full 有 47 warnings。关键哈希：

- index：`e97eca05d99a2eb3b5429539469a7e790f20f40cf70670cdbdc6a2c0c3e730a3`；
- independent verification：`3fea00a811c4422485311d4e8a0d7233fd9caf7828282f00c9a910ca8942ab69`；
- formal summary：`d466322c38eccaf9eb47b8386e281f0bbaea7ed7f4881db85404d1f01cef77ff`；
- formal manifest：`73a5884be6fffaed9d8ca3cb7972226c95bd1db3627cd1e330931dfd8f047b06`。

## 5. 可写与不可写

可写：在固定 identifier/literal-erased syntactic relation 与预注册完整性门下，完整 v11 release 到固定 future prefix
得到零链接 temporal-split certificate；它补强 physical-run/time split 的可审计性。

不可写：

- “不存在 semantic clones”；
- “没有 pretraining contamination”；
- “覆盖了所有历史数据源”；
- “12 个不可 fingerprint endpoints 也被认证”；
- predictor accuracy/effect/search utility 有任何提升；
- first-960 或 closure 已完成。

全程未读取 prospective label/grade/outcome/prediction values、未打开 raw senior archives，GPU/API/model-fit/
base-update=`0/0/0/0`。

## 6. 发布路径

- `phase1/results/historical_release_future_identifier_erased_overlap_887_20260828_8bf9512_r2/`
- `phase1/results/decision_corpus_evidence_index_v8_887_20260828_3d30826/`
