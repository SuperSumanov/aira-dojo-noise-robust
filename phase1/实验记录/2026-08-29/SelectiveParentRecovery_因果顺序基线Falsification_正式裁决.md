# Selective Parent Recovery：因果顺序基线 Falsification 正式裁决

## 裁决

正式分类必须保持为 `DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL`。第二个预注册 primary baseline 的
因果顺序前提不成立，且支持覆盖不足；不能结果后删掉它再把总分类升级。

与此同时，唯一有效且全覆盖的 cheap causal-order control `max_prior_step` 被内容方法大幅、配对且跨任务/run 地击败。
因此本轮给出一条强但严格限界的正面证据：**在 887 development time split 的固定内容选择点上，identifier-erased
内容相似度所包含的 recorded-parent 信息不能由简单 step recency 解释。** 这不是正式 prospective confirmation，也不把
recorded parent 当外部语义或因果真值。

## 冻结与总体完整性

- order-baseline readout 前冻结 protocol SHA-256：
  `d6553882e56a3e6137aca1ef3d7f0beecd264171323dc38878fb9d970293f23e`；
- 固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；
- 固定 test ambiguous/selected：`2907/2691`，内容 selected correct/errors=`2684/7`，阈值=`1006/16929`；
- source commit：`cb74a936204a44acbf957e9b9345e34c66b49aab`；
- r1 因 worktree module 调用错误在 scientific output 前退出，`FAILED_RC=1`；协议、population、阈值、baseline 与门均未改，
  r2 为唯一权威 formal。

## 有效的 max-prior-step 对照

recorded parent 对所有 `10895` 个 parent-present edges 都满足 parent step < child step，故该对照的因果顺序前提通过。

| 固定 selected population | 内容方法 | max-prior-step |
|---|---:|---:|
| comparable rows | 2,691 | 2,691 |
| correct | 2,684 | 2,199 |
| errors | 7 | 492 |

配对 correctness 为 both-correct=`2196`、both-wrong=`4`、content-only-correct=`488`、step-only-correct=`3`。
内容/step 错误比=`7/492=0.014227642276422764`；content-only/step-only 胜出比=
`488/3=162.66666666666666`。全部 ambiguous test 上，该基线正确/错误=`2268/639`，precision=`252/323`。

固定 strongest threat 即 `max_prior_step`。达到预注册最小 discordance 的任务/run=`19/96`，两层
fraction-net-content-positive 均为 `1`；最大单任务/run discordance share=`118/491` / `49/491`，分别低于 `2/5` /
`1/5`。全部 aggregate 与 breadth gates 对该有效对照均通过。

## 无效或退化的两个顺序信号

`nearest_prior_manifest_row` 不能解释为 causal order：`10895` 个 parent-present edges 中，recorded parent 不在 child
manifest row 之前的有 `5449` 个。它只在 `2034/2691=226/299` 个固定选择点上预测，低于 primary baseline 预注册的
`9/10` coverage 门。因此即使这些可比行上 content errors/order errors=`3/1357`，该数字也不能用于总分类救回或作为
公平的 full-support 对照。

secondary generation-time baseline 同样不能用：`10895/10895` parent/child generation timestamps 相等，严格先前覆盖为
0。它没有 rescue authority。

## 正确的论文位置

这条结果加强的是数据集与审计协议，而不是新 lineage 算法：发布 Selective Parent Recovery certificate 时，必须同时报告
`max_prior_step` control，说明内容信号并非纯 step recency；但 887 仍是 development time split，且 falsification 是在原
内容结果已知后冻结。未来 Target-522 confirmation 必须在 candidate profile 未见时预先加入同一有效 step baseline，才有
资格升级为前瞻确认。不得回改 887 的 baseline set 或 classification。

## 复验与安全

- result/verifier SHA-256：`34412b5281ceae6091536ac811b7b141edb15ba1b6043465abf8d00892927532` /
  `a9cf85a8aeae4145d1bba12ae1de8e0641b58bdcba9143ade0c43e2a692e8509`；
- producer/verifier A/B 各自逐字节一致，独立 verifier 不导入 producer，全部 aggregate 字段相等；
- focused/full=`38/1522 passed`（47 warnings）；
- formal/postflight manifest=`0a3d3d278b535889d02aca2d51fcdf5060134a1cd974e7396d85aac3edc33659` /
  `bb6ab5cd91ed826f4e67baa0ae6477d752b59daf66d97480c6388a05098706ed`；
- forbidden open/network/credential hits=`0/0/0`，formal 目录只读；
- prospective first-960/Target-300 values、Target-522 candidate/profile、senior raw archives 未读，无 row-level release；
  GPU/API/model-fit/base-update=`0/0/0/0`。

发布包：`phase1/results/selective_parent_order_baseline_falsification_887_20260829_cb74a93/`。
