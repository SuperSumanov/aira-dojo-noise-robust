# Decision Critic：模型规模、冻结骨干与数据增强实验

## 结论摘要

在当前日志覆盖的范围内，没有观察到模型参数规模带来稳定、单调的收益。Qwen2.5 instruct 系列在不同规模上的结果彼此接近；换成 Qwen3 base 后，平均表现略高，但同样没有随参数量增加而持续提升。只训练预测头时，Qwen3-4B 的结果约为随机水平（50%）。

将 decision 训练集与 value 训练集按 1:1 混合后，仍在原 decision 测试集上验证，Qwen3 的跨规模平均准确率从约 55.13% 降至约 54.00%，下降约 1.13 个百分点；因此这组数据增强没有带来改善。

## 可复现版本

本文对应的仓库 commit 为：`7528bbff4ef9868fb9066e780f9d48e55e54c763`。

复现实验时应先 checkout 该 commit，再确认以下输入文件和日志路径存在：

- `data/mle_critic/decision_pairs_runsplit.jsonl`
- `data/mle_critic/value_pairs_runsplit.jsonl`
- `data/mle_critic/decision_pairs_runsplit_augmented.jsonl`
- `logs/mle_critic/decision/`

若数据由 Git LFS 管理，checkout 后还需执行 `git lfs pull`，以确保拿到该 commit 对应的 LFS 对象。

## 指标与统计口径

- 指标为日志中的 `eval_pair_accuracy`，即 pairwise decision accuracy；每次 validation 固定为 1303 对。
- 表中“最终记录”是每个日志最后一次出现的 `eval_pair_accuracy`，不是从所有 checkpoint 中挑选的最高值；这是为了保持不同运行在相同“训练结束/中断时刻”的可比性。
- 更稳妥的实验报告应同时记录两个值：`best_eval_pair_accuracy`（整个训练过程中最高的 validation accuracy）和 `final_eval_pair_accuracy`（最后一次 validation accuracy）。前者适合描述按 validation 选择最佳 checkpoint 时的可达到性能，后者反映训练结束时模型的实际状态。若只能选择一个用于模型选择，应使用 best，但不能把 best 当作无条件的最终泛化性能。
- 某些大模型运行被信号中断。按实验要求，14B 运行全部不纳入均值；其余运行若日志没有出现完整结束标记，仍保留最后一次记录，并在状态列注明“中断”。
- 日志将该集合称为 validation；本文按实验约定称为 decision 测试集表现。数据切分与样本数以日志中的 `split=in-task total=... validation=1303` 为准。

## 1. Qwen2.5 instruct：参数规模实验

来源目录：`logs/mle_critic/decision/batch128_epoch2_warmup_0.03/`。训练流程由 `src/mle_critic/scripts/train/h200/train_decision.sh` 产生，数据集为 `data/mle_critic/decision_pairs_runsplit.jsonl`，模型为 Qwen2.5 instruct 系列。14B 未完成，排除。

| 模型 | Best pair accuracy | Final pair accuracy | 状态 |
|---|---:|---:|---|
| Qwen2.5-1.5B | 56.10% | 52.11% | 中断，最后记录 epoch 1.46 |
| Qwen2.5-3B | 53.57% | 52.72% | 中断，最后记录 epoch 1.86 |
| Qwen2.5-7B | 54.80% | 52.72% | 中断，最后记录 epoch 1.20 |
| **均值（1.5B/3B/7B）** | **54.82%** | **52.52%** | |

结果没有随规模增加而上升，支持“增加参数没有明显影响”的结论。由于这些日志没有完整跑完，均值应视为最后记录的阶段性汇总。

## 2. 仅训练预测头

来源日志：`logs/mle_critic/decision/only_head/Qwen3-4B_critic_decision_seed7.log`。相较全参数微调，手动冻结 Qwen3-4B backbone，仅更新预测头；数据仍为 decision pairs。

| 模型 | Best pair accuracy | Final pair accuracy | 状态 |
|---|---:|---:|---|
| Qwen3-4B（head-only） | **49.88%** | **49.81%** | 中断，最后记录 epoch 2.36 |

该结果基本等于随机二分类的 50%，说明冻结 backbone 后预测头没有学到可用的 decision 信号。

## 3. Qwen2.5/Qwen3 base：统一 base 模型实验

来源目录：`logs/mle_critic/decision/batch128_epoch2_warmup_0.03_base/`。相较第 1 组，使用 base 模型，并加入 Qwen3 系列；14B 均不纳入平均。

| 模型系列 | 规模 | Best pair accuracy | Final pair accuracy | 状态 |
|---|---:|---:|---:|---|
| Qwen2.5 base | 1.5B | 55.33% | 55.03% | 完成 |
| Qwen2.5 base | 3B | 54.80% | 52.80% | 完成 |
| Qwen2.5 base | 7B | 55.03% | 54.57% | 完成 |
| **Qwen2.5 base 均值** | | **55.05%** | **54.13%** | 3 个模型 |
| Qwen3 base | 1.7B | 55.33% | 54.80% | 中断，最后记录 epoch 1.76 |
| Qwen3 base | 4B | 58.79% | 55.41% | 中断，最后记录 epoch 1.49 |
| Qwen3 base | 8B | 56.64% | 55.18% | 完成 |
| **Qwen3 base 均值** | | **56.92%** | **55.13%** | 3 个模型 |

按 final 系列平均，Qwen3 base 比 Qwen2.5 base 高约 **1.00 个百分点**（55.13% vs. 54.13%）；按 best 平均，差距约为 **1.87 个百分点**（56.92% vs. 55.05%）。这更像是模型系列或预训练方式的差异，而不是参数规模效应：两个系列内部都没有随规模单调提升，Qwen2.5 的 3B 甚至低于 1.5B 和 7B。

## 4. 1:1 decision/value 数据增强

来源目录：`logs/mle_critic/decision/augmented_batch128_epoch1/`。训练数据为 `data/mle_critic/decision_pairs_runsplit_augmented.jsonl`，由 `decision_pairs_runsplit.jsonl` 与 `value_pairs_runsplit.jsonl` 的训练部分按 1:1 混合生成；验证仍使用原 `decision_pairs_runsplit.jsonl` 的测试集。Qwen3-14B 未完成，排除。

| 模型 | Best pair accuracy | Final pair accuracy | 状态 |
|---|---:|---:|---|
| Qwen3-1.7B-Base | 51.65% | 51.11% | 完成 |
| Qwen3-4B-Base | 56.49% | 56.10% | 完成 |
| Qwen3-8B-Base | 55.72% | 54.80% | 完成 |
| **均值（1.7B/4B/8B）** | **54.62%** | **54.00%** | |

与第 3 组 Qwen3 base 的同规模 final 均值（55.13%）相比，增强后的 final 均值为 54.00%，变化为 **-1.13 个百分点**；按 best 均值比较则为 54.62% vs. 56.92%，变化为 **-2.30 个百分点**。因此在本次 1:1 混合和当前训练超参数下，加入 value 训练样本没有改善 decision 测试集表现；4B 单点虽较高，但不足以抵消 1.7B 的明显下降，也没有形成随规模增长的趋势。

## 总体判断与限制

1. **参数规模不是主要瓶颈。** 在 1.5B--8B 范围内，准确率波动约几个百分点，未见单调趋势；14B 因未完成而不能据此判断。
2. **可训练的 backbone 很重要。** head-only 约 49.81%，而全参数训练通常在 52%--56% 区间。
3. **Qwen3 base 系列在本批实验中平均最好。** 按 final 优势约 1 个百分点，按 best 优势约 1.87 个百分点；且部分运行中断，不能视为稳健显著提升。
4. **数据增强未改善结果。** augmented Qwen3 平均比未增强实验低约 1.13 个百分点。

后续若要作严格的模型规模结论，应让每个规模完成相同 epoch，并使用多个随机种子；同时在表格中并列报告 best/final 两列，并预先声明主指标。当前文档的数字主要用于比较这些已有日志，而不是显著性检验。
