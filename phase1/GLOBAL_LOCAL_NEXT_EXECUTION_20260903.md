# 下一项效果实验：跨 seed、同预算的 global → local 迁移

2026-09-03；执行准备，不是效果结果或正式五臂预算授权。

优先验证真实 global 质量监督是否改善 local sibling 决策，并排除“只是多训练”“只是多见代码”及局部过拟合。
遵循 `global_local_calibration_candidate_protocol_v2.json` 的五臂，不恢复更早的 interleaved arm。

## 拟执行矩阵

| 臂 | 用途 | 拟 seed |
| --- | --- | --- |
| L1 | local 单遍，识别重复训练的伤害；不是同预算主对照 | 6、7、8 |
| Lbudget | local-only，同预算基线 | 6、7、8 |
| Gbudget | global-only，同预算迁移基线 | 6、7、8 |
| G_to_L | global 单遍后 local 单遍 | 6、7、8 |
| Ghash_to_L | 同样代码和顺序，global 标签改为端点一致的哈希排序 | 6、7、8 |

这是 15 个拟议训练单元，尚未授权。三个 seed 事前提出，不按结果换 seed；pivot model 和精确预算须根据
G0 墙钟而非 dev accuracy 确定。G0 本身只有 seed 6、十步，不是跨 seed 或效果验证。

## 运行前必须补齐的实质问题

1. **阶段顺序**：已读的 exact trainer 在数据加载后调用 `rng.shuffle(training_records)`，通用 Trainer
   还会执行训练采样。仅拼接两个来源不会实现“先 G 后 L”。必须提供显式、可恢复的阶段采样计划，并从
   实际 batch 回执验证顺序、消费次数、seed 和断点恢复，不靠文件名证明阶段训练。
2. **预算匹配**：同样 optimizer steps 不自动等于同样 token/计算量。需固定 tokenizer、序列化、batch 与
   实际消费预算；对所有 primary 同预算臂输出真实有效 token、padding、optimizer steps 与 allocation。
   在生成计划前定义末批处理，不能靠结果后改截断来“凑相同预算”。G_to_L/Ghash_to_L 的 row/order/token/step
   必须严格一致；L1 明确例外。若无法同时满足原预算契约，需先提出修订，不得悄悄放宽。
3. **数据边界**：现有 G0 的 4,689/551 train/dev 是历史开发数据。不能把已触碰的历史 outer test 或前瞻
   vault 直接升级成新的确认集。正式五臂仍需 producer provenance、experiment-closed split 和零重叠；
   如先做历史探索，应另立探索方案并保留它不能确认部署泛化的限制。
4. **成本与存储**：先让批准的唯一 G0 successor 完整产出十步、一次 dev、checkpoint 和耗时。当前 CPU
   修复回归通过，但 4 GiB checkpoint 预留被研究盘用户配额拒绝，未提交重试。解决存储后重新核验资产与
   117 分钟/no-requeue/累计预算上限，再运行；不能删除未知旧 checkpoint 腾空间。

## 原成功门保持不变

G_to_L 相对 Lbudget 平均至少 +2 个百分点、每 seed 同向、task-clustered CI 下界大于 0；还须超过
Gbudget 和同池 TF-IDF。只有这些通过后才检验相对 Ghash_to_L 的真实质量标签收益。完整报告
Draft/Improve、task macro、seed 离散度、LOTO 和单任务贡献，不把单 seed、挑任务或局部过拟合回避当迁移。

## scaling 支线

沿用 v2 的 0.6B/4B/8B × seed 6/7 六-run 矩阵，但规范、outcome-before 的 config-v2 sidecar 当前为 0。
缺失来源条件不能通过补写历史配置来满足；因此现在不启动 clean scaling、不复用已撤回旧 checkpoint。
