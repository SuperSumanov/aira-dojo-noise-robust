# 0829 Plant Pathology 无 checkpoint 结构拒收

- exact audit commit: `eff897058251bcbc4e97c1a616b8f9630a045cce`
- failed intake log SHA-256: `0e55dc25cdd58e251d7378a80c6938201a64be44f4b6b5594051f02cb4c8cc3e`
- diagnostic receipt SHA-256: `094fe135ca00ecdb3ad9de8ec69c7da026624918508b67266b78321fb8127f4a`
- rejection registry SHA-256: `e77654a795ebc05a773ea81aacd91801303d2a57c5a14b43c290204e26852093`
- remote formal manifest SHA-256: `64b70620c5f79fb76d203bd175a8e036e133631761bfb3ed1a9cf14d76b71586`
- focused/full tests: `29 / 1835 passed`（full 有 48 warnings）

正式 A/B 与独立 verifier 一致确认：归档发现 8 个 run roots，但 checkpoint journals 为 0，8/8 均为
live-only roots；live event journals、env、label、outcome、prediction values 未读。因此只能用
`ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS` 整归档拒收，不能局部 salvage。

本目录只支持 outcome-blind 结构摄取恢复，不是 predictor 或 search utility 效果结论。
