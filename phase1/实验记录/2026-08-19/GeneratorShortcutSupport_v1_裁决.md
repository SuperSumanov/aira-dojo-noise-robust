# GeneratorShortcutSupport v1：裁决

日期：2026-08-19。裁决：`INSUFFICIENT_GENERATOR_SHORTCUT_SUPPORT`。

## 结果

- Linux 全套测试：`393 passed in 35.10s`；
- 31,742 cards / 676 runs / 28 tasks / 11 clients；client 缺失 run=0；
- train pairs=11,946；known-client=11,946；
- same-client=11,946，cross-client=0，cross-client/same-environment=0；
- 5-fold physical-run OOF same-client=5,318 pairs / 28 tasks；
- 10 个 client 通过单 client 的 LOSO 结构支持门，但 cross-client 两个强制门均失败。

producer 双跑逐字节一致；独立 verifier 两次重建 pool 计数一致。summary SHA=
`59e607e5f62973d515780d8f5881cb69aa47011b5b569242df04292b0bf11cfe`，verification SHA=
`6032a80dbfa20fca921ac0b85a004a6d82b23a411c9b4647a3ff9e4b1abfb596`。

## 科学边界

学长提出的“不同策略模型的输出风格使 value pairs 容易”不能按 pair 两端 client identity 直接成立，因为每一对的
client 都相同。该结构结果是有价值的反混杂证据，但没有解锁正方法，也没有否定更细的同-client run/style/search-
phase shortcut。按预注册不训练 predictor、不读效果、不把支持门改成跨 pair 的生态相关分析。

后续回到两条已守住的路线：时间更晚的新 archive 进入 exact-stratum future cohort；同时可在不打开 0812 label
vault 的前提下，把激活前固定 scorer 的预测做成 escrow，留待和未来 clean checkpoints 一次性共同评估。
