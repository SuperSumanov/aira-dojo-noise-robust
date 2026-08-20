# WLGraph Multi-View Extension v1：时间字段勘误

日期：2026-08-20。状态：`DECLARED_FREEZE_TIMESTAMP_INVALIDATED`。

## 发现与证据

`wl_graph_multiview_protocol_v1.json` 手填的 `frozen_at_utc=2026-08-20T05:13:00Z` 不可作为冻结时间。
远端主机在 `2026-08-20T04:47:52Z` 已同时观察到该协议、协议 commit
`efbcc8f76244dda1c8e0c7a0c715fcb232665754` 和当前实现 commit
`f67157ad35385019f11a79291a1df8cdf4311806`；此时比手填时间早 25 分钟以上。因此该字段是未来时间戳，
不能用于证明时间先后。远端只读时钟收据 SHA256 为
`03a9eb776bc8e9b7d08aa3eb5eafa6e64beda27ef6dc044ddab9cd7449d87ec3`。

## 科学影响

该错误不改变已经 commit 的模型配置、输入 SHA、四个固定 arm、GPU/API=0 约束或正在进行的 train-only 构建；
也没有读取 v11 frozen、first-960 outcome 或 0812 label vault。但必须收窄后续主张：

- 原 `frozen_at_utc` 字段永久作废，不回写成一个看起来正确的新时间；
- 当前已有 first-960 前缀和 0812 temporal 只能作为 outcome-unread 支持性预测资产；
- 严格的 temporal prospective 方法结论，只能使用后续另立 activation receipt 之后生成的 physical runs；
- activation receipt 必须在 bundle 独立复核完成、预测协议 commit 并推送后，由远端 UTC 自动生成并绑定 commit、
  bundle SHA、verifier SHA，不能再次手填。

机器可读裁决见 `phase1/wl_graph_multiview_protocol_v1_erratum.json`。本勘误在任何模型效果、frozen outcome 或
前瞻 outcome 被读取前写入。
