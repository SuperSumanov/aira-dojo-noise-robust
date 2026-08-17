# FailureMechanism × LengthHeterogeneity v1 裁决

## 冻结与复现

- 预注册/实现 commit：`acf63075237e1e2f9ceb925a81fde6d95f295ccd`
- code-free registry SHA256：`ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747`
- 正式结果双跑逐字节一致，SHA256：`d85ec8a42a09160e19c71961f419b59108034f293f02a0722b839a24d9915377`
- 完整测试：`360 passed in 31.02s`
- GPU/API/底座更新：0/0/0；未读 frozen endpoint code 或 numeric grade。

## 结果

494 pairs / 13 tasks / 126 runs 上，整体 raw-byte longer-success credit 为
`0.4493927125506073`。四个达到 30-pair 支持门的类别 range 为
`0.11340275445078934`，小于冻结门 0.15；task-stratified permutation
`p=0.4312956870431296`，大于冻结门 0.01。支持数量门通过，但两个核心效应门均失败。

## 裁决

**INSUFFICIENT_FAILURE_MECHANISM_LENGTH_HETEROGENEITY**。该支线关闭，不按结果翻转长度方向、不重组 taxonomy、
不降低类别支持或显著性门，不进入 search utility。

## 对既有 length 前瞻 v1 的规格纠错

commit `990be2a5bbdd40b203d802ae2a0273a7b14c957b` 把旧 LOTO 中的“length-only LR”错误简化成
“raw UTF-8 bytes 更长者预测 retained success”。旧模型实际使用 `truncate_code` 后的字符数、`log1p` 与
训练侧拟合的 logistic coefficient；旧结果没有授权固定 raw-byte 方向。两者不是同一 estimand/scorer。

因此该 prospective length v1 在任何新 cohort outcome 被读取前标记为
**VOID_SPECIFICATION_ERROR**。它没有产生新 transaction 或 outcome，不属于结果后撤门。若未来继续，只能另立 v2，
在旧 494 对上冻结原模型的完整训练配方、系数/截距与独立收据，再对全新、时间上更晚的 cohort 一次性确认。
