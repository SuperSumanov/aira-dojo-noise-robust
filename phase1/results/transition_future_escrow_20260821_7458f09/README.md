# Transition future escrow：正式激活与初始托管

日期：2026-08-21。正式状态：`FORMALLY_ACTIVATED_INITIAL_SUPPORT_ONLY`。本结果只建立时间外预测托管，不含
任何 prospective 效果结论。

- source commit：`7458f0969b92a258ea0e495bbbee282aa12b748e`；
- activation：`2026-08-21T07:05:03.916471Z`；
- frozen snapshot：`83ab1d681ed863d2374a6648df4801e6dbd6fb80d89f4f20cec8d46de1d5c047`；
- model summary SHA-256：`7b32ddc85217245d65c767445439072e4dd08f4da88523ce5c52fc3156122bf3`；
- activation SHA-256：`dd3aeb4afce7ff64423f9539beadba133cfeb3310a74169eb18ea27f7ba487d3`；
- initial escrow summary SHA-256：`a3a2977ea2efb7c439e9669ffa24ffe7d6e9e2a5ce7f16a7e40ab8bca5649b50`；
- conclusion SHA-256：`4e2eca820535e749bd060c9666b358801a3c0b158b77634514c68ab3ebf5b6ec`；
- output-manifest SHA-256：`489df1660c8015e84eb8b237623050655297c150f218c7f40f4ae082bbfe2339`。

两次模型生产与两次独立复算、activation 双复核、initial escrow 双生产/双复核以及 prior append replay 全过。
训练 reference 与 future margin 最大独立复算误差都是 0.0；append replay 保留 1,665/1,665 旧 pairs。23 个
focused tests、582 个 phase tests、17 个 stage rc、226-entry manifest、forbidden-path trace 与三类 credential
scan 全部通过；远端全量目录递归只读。

初始 1,665 pairs 全部为 activation 前 support-only，strict/eligible 均为 0；未读 outcome、未计算 accuracy/CI，
所以 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT` 是预期状态。只有严格晚于 activation 生成且通过冻结来源与
支持门的新 runs 才能进入未来效果检验。

旧 `921769f-v1` attempt 因 80 次 forbidden-name 路径元数据接触无效，且没有 conclusion/COMPLETE；它的旧时间
边界永久不使用。修复后只核对协议登记的 source blobs，本次正式系统调用审计命中为 0。

完整只读产物：`/research/d7/spc/yzyang4/transition-future-escrow/7458f09-v1`。
