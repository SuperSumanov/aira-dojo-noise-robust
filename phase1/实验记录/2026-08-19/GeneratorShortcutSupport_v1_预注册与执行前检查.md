# GeneratorShortcutSupport v1：预注册与执行前检查

日期：2026-08-19。状态：`PREREGISTERED_SUPPORT_GATE_NOT_RUN`。

## 问题与边界

学长在 train/test 污染的探索性实验中观察到 value→value 约 0.60，而同父 sibling decision 约 0.50，
并提出 value pair 可能允许 critic 利用策略模型/client 的风格捷径。本文只在学长 augmented 数据的
`intask_split==train` 上建立结果盲资格门；不读取 test、v11 frozen、0812 temporal vault 或任何新前瞻 outcome。
即使支持门和后续效果门通过，也只允许“generator/client shortcut 是 value-pair 可学习性的一部分”，不允许
“完全解释 critic 表现”或因果外推。

## 冻结结构与后续矩阵

- physical-run OOF：每个 run 由固定 SHA-256 domain 分到 5 folds；跨 fold pair 不进入 OOF 测试。
- 结果池：all、same-client、cross-client、以及 client 不同但 hardware/time_limit/execution_timeout 相同的严格池。
- 后续模型（资格门通过后才实现）：client-only train prior、char-TFIDF pairwise LR、固定 static pairwise LR。
- 后续主指标：task-macro tie-aware accuracy；同时报告 micro、逐任务、run/task clustered CI。
- 后续同池比较：严格 cross-client 同环境池上的 char/static 相对 client-only paired delta。
- client-held-out：只对 OOF same-client pairs≥80 且任务≥2 的 client 做 leave-one-client-out；不得按效果选 client。

## 结果前固定支持门

必须全部满足才允许效果实验：

1. known-client train pairs ≥4,000；
2. OOF same-client pairs ≥400 且任务≥6；
3. OOF cross-client same-environment pairs ≥400 且任务≥6；
4. 至少 2 个 client 各有 ≥80 个 OOF same-client pairs 且任务≥2。

效果实验成功门在读取任何 accuracy 前固定为：

1. client-only 在 cross-client same-environment 的 task-macro 95% task-cluster CI 下界 >0.5；
2. char-TFIDF 的 cross-client 与 same-client task-macro 配对任务差异 CI 下界 >0；
3. 至少两个非单任务 client 上，run-OOF char-TFIDF 相对 leave-client-out 的 paired delta 同向为正。

任一失败均关闭强机制解释；不改 pool、阈值、client 或 fold 救结果。

## 13 项执行前检查

1. 旋钮从产物侧验证：summary 固定 fold domain、5 folds、输入 SHA 与 scope。
2. 新路径先便宜验证：两个 synthetic focused tests 通过后才上全量 CPU。
3. 测试集查重：unordered endpoint pair 重复 fail closed；只接收 train split。
4. 看分布：资格阶段输出逐任务和逐 client 支持，不先看汇总效果。
5. 评估配平：后续以 task-macro 和同环境严格池为主，不用单任务加权 micro 代替。
6. 贵 run 存模型：本资格门 0 GPU；后续 TF-IDF 保存 fold config 与逐 pair 预测。
7. 泄漏三查：pair 去重、physical-run OOF、test/frozen/temporal 完全不读；后续再查代码 SHA。
8. RNG：无随机 shuffle；fold 是固定 SHA-256 映射。
9. 密钥：577 MB cards 与 pair 文件在 JSON 解析前流式高置信扫描；命中即拒绝。
10. 墙钟：纯 CPU 元数据统计，无 Slurm/GPU；预计 5–10 分钟。
11. 功效：结果前固定 pairs/tasks/client 三层支持门，失败不训练 predictor。
12. 链 rc：shell 使用 `set -eo pipefail`；不在 `date` 后误读 `$?`。
13. 扩语料抽签：输入 SHA 固定为学长 commit `92a9651` 的不可变 LFS 对象；不接受 append 后重排。

## 复现与独立性

producer 正式双跑必须逐字节一致；独立 verifier 不 import producer，重新解析 locked inputs、重建 run folds 与
所有 pool 计数。完整 `phase1/tests` 必须先通过。GPU=0、API=0、底座更新=0。
