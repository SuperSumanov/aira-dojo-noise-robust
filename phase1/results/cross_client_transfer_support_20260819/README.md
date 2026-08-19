# Cross-client transfer support v1

日期：2026-08-19。正式裁决：`INSUFFICIENT_CROSS_CLIENT_TRANSFER_SUPPORT`。

结果前 commit `2e7ea07fc7ff5dfe476e6b6d8bfcf8877ff91adb` 固定 exact-stratum 与全部支持门。
远端 Linux 全套 `399 passed in 35.11s`；producer 双跑逐字节一致，不 import producer 的 verifier 双跑一致。

锁定数据含 31,742 cards / 676 runs / 28 tasks / 11 clients / 11,946 train pairs；其中 11,030 pairs
满足 pair 两端同 client 且 exact `(task, hardware, time_limit, execution_timeout)`。跨 client exact-code
重复导致的排除数在所有 client 均为 0。

但在要求每个 held-out test stratum 由其他 client 提供至少 50 pairs/2 clients 后，0 个 client 同时通过
test≥200 pairs/4 tasks/15 runs、train≥1,000 pairs/3 clients 与 dominant task≤0.50，因此正式 eligible pool
为空，不运行 char-TFIDF/static LOSO 效果实验。

最接近的是：

- `deepseek-v4-pro`：415 test pairs / 4 tasks，但只有 14 test runs、922 train pairs；
- `qwen3.5-397b-a17b`：442 test pairs / 4 tasks，但只有 14 test runs、895 train pairs。

summary SHA=`43405484450ffea994ba69ef06b45c7c8e9db9962a8bda5e84327cf10513bb94`；独立验证
SHA=`19ea5b0a8c6d8c85a4f5f1df180c860076a32e7489cce59f09e0b5bde2da41e1`。

科学含义不是“不能跨 generator 泛化”，而是现有 generator 与 task/execution environment 的联合覆盖不足，
无法对该命题做严格识别。允许的下一步是未来数据生产显式平衡共享 task×environment×client 矩阵；不得降低门、
合并环境或在当前数据上跑效果后追认正结论。
