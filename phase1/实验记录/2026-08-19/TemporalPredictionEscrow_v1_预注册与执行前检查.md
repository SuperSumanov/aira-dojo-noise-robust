# TemporalPredictionEscrow v1：预注册与执行前检查

日期：2026-08-19。状态：`PREREGISTERED_NOT_RUN`。

## 目的与矩阵

把 2026-08-13 22:19 UTC 已激活固定的 `static_lr`/`char_tfidf_lr` bundle，对 0812 analyst-blind temporal
holdout 的 805 endpoints / 103 structural sibling pairs 生成无标签 prediction escrow。固定矩阵为 1 bundle ×
2 arms × 805 endpoints；0 GPU·h、0 API，预计 5–10 分钟。

本实验不接受 label-vault 参数，不读取 `label_vault.jsonl`，不计算 accuracy/utility。0812 vault 继续保留到未来
clean checkpoints 也完成预测冻结后再决定是否一次性打开；本 escrow 本身没有科学效果裁决。

## 固定输入

- blind views SHA：`c0d6d207f39ea8d113a90c73e75c982ca9e77356d061ac8bffd8caa53e201dc9`；
- sibling structure SHA：`2c67ab3dae40c34b3eea233ae049afa2462d88e689b737b21421a7a1862c993b`；
- fixed scorer SHA：`c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23`；
- freeze receipt SHA：`cfab01a80536a50ef21c47ac269c7ce54a11a3b1f0b6daa5700873cbb02ce178`；
- 16,012-endpoint denylist SHA：`2f0cc4f3dc203801c569237716ba82cbc2bde2f854b67eee6efa9452e92447e6`。

## 成功门

必须全部满足：805 endpoints、57 runs、9 tasks、103 pairs；endpoint ID 与 exact-code SHA 对 pre-cutoff denylist
重叠均为 0；所有分数 finite；两个 arm 对 103 pairs 全覆盖；producer 双跑逐字节一致；不 import producer/scorer
的数值 verifier 最大绝对差≤1e-12；系统调用 trace 中 `label_vault.jsonl` open=0。

任何失败只报告 escrow 不完整，不补 endpoint、不改 scorer、不打开 vault。

## 13 项执行前检查

1. 旋钮由 summary 固定 bundle/receipt/input SHA 和两个 arm。
2. synthetic roundtrip + 独立数值 verifier 先跑通。
3. unordered pair 重复、self pair 与 endpoint 缺失均 fail closed。
4. 只报告 endpoint/run/task/pair 分布，不报告效果。
5. 没有评估配平问题；未来开 vault 时才预注册 task/run clustered inference。
6. 固定 endpoint 分数、逐 pair margin/selection 与所有 SHA。
7. pre-cutoff ID/exact-code 两层查重；未来开 vault 前再查 train/test run。
8. 无随机过程；left/right orientation 固定于已封存 structure。
9. blind views 在 JSON 解析前做高置信 credential scan；命中即拒绝。
10. CPU-only、预计 5–10 分钟，无 Slurm 墙钟风险。
11. 103 pairs 已知只够支持性分析，不能单独承担论文确认性结论。
12. shell `set -eo pipefail`，失败立即停止。
13. 所有输入 SHA 固定，不受后续语料 append 影响。
