# Selective Parent Recovery：因果顺序基线反证审计

正式分类必须保持为 `DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL`。

这是一个结果已知后、但在三个顺序基线 readout 前冻结的 development-only falsification。它使用与已发布 887
Selective Parent Recovery 证书完全相同的时间切分、候选集、`2691` 个内容方法已选择测试点和阈值
`1006/16929`，检验 identifier-erased 内容相似度是否只是便宜的因果顺序代理。

## 有效的正面证据

`max_prior_step` 是有效且全覆盖的顺序对照：recorded parent 在全部 `10895` 个 parent-present edges 上都严格早于
child step；在固定的 `2691` 个选择点上，内容方法错误 `7` 次，而该步数基线错误 `492` 次。配对表为：双方正确
`2196`、双方错误 `4`、仅内容正确 `488`、仅步数正确 `3`。因此内容/步数错误比为 `7/492`，仅内容/仅步数胜出比为
`488/3`。

差异不是单一任务或 run 驱动：满足预注册最小 discordance 的任务/run 分别为 `19/96`，净内容优势比例均为 `1`；
最大单任务/run discordance share 分别为 `118/491` 和 `49/491`，均通过预注册 anti-dominance 门。这个结果支持一个窄的
正资产：在该 development time split 上，内容表示包含简单 step recency 不能解释的 recorded-parent 信息。

## 为什么正式分类仍然失败

第二个预注册 primary baseline 把 blind-manifest 行序当成因果时间；实际 `10895` 个 parent-present edges 中有 `5449`
个 recorded parent 并不位于 child 之前。该基线在固定选择点上只覆盖 `2034/2691=226/299`，低于预注册 `9/10`
支持门，因此不能与有效 step baseline 一起给出正式 strong classification。secondary generation timestamp 也退化：全部
`10895` 个 parent/child timestamp 相等，覆盖为 0。

不能结果后删除无效 primary baseline、改变 classification，或用它极差的数字“救回”正式通过。正确处理是保留完整性失败，
把有效 `max_prior_step` 结果标为强描述性反证，并在未来未见的 Target-522 confirmation 中把该基线预先列为 mandatory
control。

## 复验与边界

- protocol SHA-256：`d6553882e56a3e6137aca1ef3d7f0beecd264171323dc38878fb9d970293f23e`；
- source commit：`cb74a936204a44acbf957e9b9345e34c66b49aab`；
- formal result / independent verifier SHA-256：`34412b5281ceae6091536ac811b7b141edb15ba1b6043465abf8d00892927532` /
  `a9cf85a8aeae4145d1bba12ae1de8e0641b58bdcba9143ade0c43e2a692e8509`；
- formal/postflight manifest SHA-256：`0a3d3d278b535889d02aca2d51fcdf5060134a1cd974e7396d85aac3edc33659` /
  `bb6ab5cd91ed826f4e67baa0ae6477d752b59daf66d97480c6388a05098706ed`；
- focused/full tests：`38/1522 passed`（47 warnings）；producer/verifier A/B 各自逐字节一致，独立 verifier 不导入
  producer 且全部 aggregate 字段相等；
- r1 因模块调用路径错误在任何 scientific output 前退出，`FAILED_RC=1`，失败历史保留；r2 是唯一权威 formal；
- forbidden open/network/credential hits 均为 0，formal 目录只读。

本包不发布 task/run/card/parent identities 或逐 edge 数据，不把 recorded parent 当外部语义/因果真值，不声称一般 lineage
方法 novelty、predictor effect、scaling、search utility 或 Target-522 confirmation。prospective first-960/Target-300 values、
Target-522 candidate/profile 与 senior raw archives 均未读取；GPU/API/model-fit/base-update=`0/0/0/0`。
