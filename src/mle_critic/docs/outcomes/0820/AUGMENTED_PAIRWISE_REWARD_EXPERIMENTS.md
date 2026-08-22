# Augmented Pairwise Reward：实验内配对、LOTO 与 Decision 实验

## 结论摘要

这批实验第一次在当前 augmented 数据上观察到比较清楚的模型规模效应，但这个结论只成立于
in-task value-pair 排序任务。14B 延续了这个趋势，并让 value→decision 迁移第一次超过
TF-IDF；但直接在 decision pairs 上训练仍没有稳定的规模效应。

1. Value pair 从“同一 task 的全部可用节点互相配对”改成“只在同一个 experiment 内配对”。
   这样至少控制了策略模型、硬件、时间预算和采集批次等 experiment 级差异，减少 critic 仅靠
   环境或生成风格判断 better/worse 的机会。
2. Decision pair 拆成 draft 和 improve 两部分。Draft 利用不同 run 的第一批 solution 共享相同
   输入这一点跨 run 配对；improve 保留局部决策的语义，并跨过中间 error/debug 节点寻找最近的
   正常 parent。经过 gap filter 和 run split 后，两部分分别贡献 3,895 和 2,661 条 pair。
3. 当前所有训练目标都统一为“给定两个 solution，判断哪个最终 grade 更高”。模型只学习标量
   score 的相对次序，不预测value（大V），现阶段优先确认任务是否可学。
4. In-task value pair 上，Qwen3 0.6B--14B 的两个 seed 平均 final accuracy 依次为 **58.64%、
   60.67%、62.01%、64.68%、65.76%**，平均 final eval loss 依次为 **0.7096、0.6954、
   0.6770、0.6607、0.6324**。14B 相对 8B 的 accuracy 增益缩小到 1.08 个百分点，但 loss
   继续明显下降，整体 scaling 仍成立。
5. 便宜基线并没有失效。Value pair 上 TF-IDF logistic regression 为 **61.18%**：0.6B 明显
   落后，1.7B 平均仍略低；4B 平均超过约 0.83 个百分点，但 seed 6 的 final 仍略低；8B 两个
   seed 都超过基线，平均领先约 3.50 个百分点；14B 两个 seed 的 final 都是 65.76%，领先约
   4.57 个百分点。
6. Spooky Author 的 leave-one-task-out 没有稳定、单调的 scaling。4B/8B 的结果明显高于随机，
   但 1.7B 比 0.6B 更差，8B 又低于 4B，而且各模型后半程 eval loss 明显恶化。这个设置测的是
   完全没有目标任务训练样本的跨任务 zero-shot 排序，与 agent 已经接触目标数据和运行环境后的
   MLE 决策不是同一个问题。
7. Value→decision 迁移使用 seed 7 value checkpoint。Filtered decision accuracy 从 0.6B
   到 14B 为 **56.25%、56.25%、59.06%、59.38%、60.63%**。14B 首次超过 TF-IDF 的
   **59.90%**，但只高 0.73 个百分点，而且 decision 侧只有一个 seed。
8. 直接用 5,596 条 decision train pairs 训练 2 epochs 后，0.6B/1.7B/4B/8B 的 best accuracy
   为 **56.56%、55.73%、59.38%、55.83%**，没有模型规模效应，也没有稳定优于
   value→decision。所有模型的 eval loss 都在训练早期达到最低点，随后明显恶化；第二个 epoch
   基本是在增加置信度和过拟合，而不是改善排序。

因此当前最稳妥的判断是：**experiment 内 value 排序具备 learnability 和模型规模效应；增大到
14B 能继续改善 value，并小幅改善 decision 迁移，但直接 decision supervision 本身仍不稳定。**
下一步应优先补直接 decision 的多 seed、14B/27B 和更短训练/更强正则，同时继续推进以更多算力
换 performance 的 RL 实验。

## 可复现版本与实验口径

本文整理时仓库 HEAD 为 `d44f4b0347154417ee5adc7a3b5b59ddd22ccb2c`。Experiment-level
value 数据流水线主要对应 `92a9651f2e13a9e43623235b82c07c19721bc2ee`，augmented decision
pair 构建对应当前 HEAD。

主要数据和日志：

- `data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl`
- `data/augmented_mle_critic/merged_decision_pairs_filtered_runsplit.jsonl`
- `logs/augmented_mle_critic/reward_0815/seed6/`
- `logs/augmented_mle_critic/reward_0815/seed7/`
- `logs/augmented_mle_critic/loto_spooky_author/`
- `logs/augmented_mle_critic/decision/`
- `logs/augmented_mle_critic/decision_0815/`
- `logs/augmented_mle_critic/light_predictor/light_predictor_results_augdata.json`
- `logs/augmented_mle_critic/light_predictor/light_predictor_results_filtered_decision.json`

直接 decision 训练入口是
`src/mle_critic/scripts/train/pro6000/train_aug_reward_decision.sh`。本文更新时该脚本仍是 worktree
中的未提交文件，不包含在上述 HEAD；复现时不能只 checkout commit 而忽略它。

Value 和 LOTO 训练的共同配置为：

- Qwen3 Base 0.6B、1.7B、4B、8B 全参数微调；value 另包含 14B；
- 2 张 96 GB GPU，bf16，DeepSpeed ZeRO-3；
- `max_len=16384`，task conditioning 开启，budget conditioning 关闭；
- learning rate `1e-5`，cosine scheduler，warmup ratio `0.03`；
- 各模型有效 pair batch 均为 128；
- 训练 1 epoch，每 10 个 optimizer step 评估一次。

本文同时报告 Best 和 Final record。Best 是日志内所有 validation checkpoint 的最高 accuracy，
存在多次查看 validation 后的选择偏差；Final 是最后一次记录，不一定正好对应完整训练结束。
Seed 6/7 的 4B 和 seed 6 的 8B 没有正常结束标记，但都记录到约 epoch 0.96，因此保留最后一次
validation。新增的 14B value 两个 seed 都完整训练到 1 epoch。LOTO 的 8B 没有正常结束标记。

直接 decision 实验使用同样的模型输入和有效 batch 128，但训练 2 epochs、每 9 个 optimizer
step 评估一次；目前只有 seed 7 的 0.6B、1.7B、4B、8B。1.7B 和 8B 完整结束，0.6B 和 4B
记录到 epoch 1.85 后被中断。

## 1. 数据构建改动

### 1.1 Value pair 改为 experiment 内配对

旧流程会把同一 MLEBench task 的全部可用节点放进一个池中。两端可能来自不同策略模型、不同
硬件、不同时间限制、不同执行上限或不同采集日期。即使 physical-run split 没有泄漏，critic
仍可能通过代码风格、常用模型或搜索阶段等 experiment-level 特征判断哪一端更可能得高分。

新流程先按 experiment 生成独立的 `batch_cards.json`，再在每个 batch 内调用 value pair
builder。Builder 内部仍按 task 分组，但它一次只能看到当前 experiment 的 Cards。最后才把各
batch 的 pair 拼接、做 task-specific gap filter，并应用 frozen physical-run split。

当前 reward-pair 配置使用 `budget_steps=-1`，所以 pair 标签比较的是两个节点自身的有限
external grade，不使用未来子树 value。这里继续沿用 “value pair” 作为数据文件名，但实际训练
目标已经是 solution quality 的 pairwise ranking。

当前 value 数据包含 28 个任务：

| Split | Pair 数量 |
| --- | ---: |
| Train | 11,946 |
| Test | 1,574 |
| 合计 | 13,520 |

这个改动显著降低了环境差异，但不能证明所有 shortcut 已被消除。同一 experiment 内仍可能存在
run、搜索深度、代码长度和策略行为差异；另外多个 pair 会共享 Card endpoint，因此 1,574 条
test pair 也不能当成 1,574 个完全独立样本来做显著性估计。

### 1.2 Decision pair 拆成 draft 和 improve

Draft 是每个 run 的第一批 solution。一个 experiment 内的不同 run 在 draft 阶段共享相同任务
输入，还没有受到后续搜索轨迹影响，因此可以把各 run 的 root children 合成一个 decision set，
构造原来同父逻辑无法覆盖的跨 run draft pairs。

Improve pair 仍比较一次局部搜索决策产生的 sibling。与旧实现的主要区别是：如果 lineage 中间
出现一个或多个 error/debug 节点，builder 会继续向上追溯到最近的正常 parent，避免错误节点把
本来可比较的分支截断。

实际数据量如下：

| 数据阶段 | Draft | Improve | 合计 |
| --- | ---: | ---: | ---: |
| Raw | 7,651 | 5,587 | 13,238 |
| Gap filtered | 5,772 | 2,661 | 8,433 |
| Run split 后 train | 3,552 | 2,044 | 5,596 |
| Run split 后 test | 343 | 617 | 960 |
| Run split 后合计 | 3,895 | 2,661 | 6,556 |

Draft pair 在 gap filter 后有 1,877 条没有进入最终 split，因为跨 run draft pair 的两端可能分别
落在 train 和 holdout run，`apply_runsplit` 会丢弃这种跨界 pair。Improve sibling 位于同一个
physical run，因此没有这个损失。即使如此，draft 仍贡献最终数据的 59.4%，确实显著扩大了
decision 数据量。

后续报告 merged decision accuracy 时最好同时报告 draft 和 improve 子集。两者的数据语义和
split 行为不同，只看 960 条合并 test pair 可能掩盖其中一类的退化。

## 2. 统一为 pairwise learnability 目标

模型对每个 solution code 输出一个标量 `s(x)`，训练损失为 Bradley-Terry loss：

```text
L = -log sigmoid(s(better) - s(worse))
```

训练只要求 higher-grade solution 的 score 更高。这么做的目的是先回答更基础的问题：
静态 code 和 task 信息中是否存在足够稳定的信号，让模型判断两个方案谁更好。

排序 value （rl中的大V）同时混合了策略，随机性，和MCTS。
当前阶段先放弃它，可以把失败更明确地归因于 pair ranking 本身是否可学。

## 3. In-task value pair 实验

### 3.1 两个 seed 的结果

| 模型 | Seed 6 Final acc | Seed 7 Final acc | 两 seed 平均 Final | 两 seed平均 Best | 两 seed平均 Final loss |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-0.6B-Base | 58.07% | 59.21% | **58.64%** | 59.21% | 0.7096 |
| Qwen3-1.7B-Base | 59.40% | 61.94% | **60.67%** | 60.67% | 0.6954 |
| Qwen3-4B-Base | 60.67% | 63.34% | **62.01%** | 62.80% | 0.6770 |
| Qwen3-8B-Base | 66.01% | 63.34% | **64.68%** | 64.96% | 0.6607 |
| Qwen3-14B-Base | 65.76% | 65.76% | **65.76%** | 66.14% | 0.6324 |

从两个 seed 的平均看，accuracy 随模型规模单调上升，0.6B 到 14B 提升 **7.12 个百分点**；
final eval loss 也随规模单调下降。14B 相对 8B 的 final accuracy 只增加 **1.08 个百分点**，
低于此前相邻规模约 1.3--2.7 个百分点的增益，说明 accuracy scaling 已开始变缓；但 final loss
从 0.6607 降到 0.6324，模型的 pair margin 质量仍在改善。Seed 间波动没有改变平均规模排序。
不过 14B 的两个 seed 虽然 final accuracy 恰好相同，第一次 validation 分别为 57.69% 和
63.53%，相差 5.84 个百分点；它们只是最终收敛到同一点，不能据此认为训练方差已经消失。

### 3.2 随训练步数的变化

把 5 个模型、2 个 seed 在相同 validation 时刻做宏平均：

| 平均 epoch | Eval accuracy | Eval loss |
| ---: | ---: | ---: |
| 0.11 | 54.73% | 0.6858 |
| 0.43 | 60.22% | 0.6717 |
| 0.64 | 61.70% | 0.6777 |
| 0.86 | 62.43% | 0.6748 |
| 0.96 | 62.35% | 0.6750 |

Accuracy 的训练步数 scaling 很明确，但主要发生在前 0.6--0.8 epoch，之后进入平台。Eval
loss 在约 0.43 epoch 最低，后期略有回升。因此“训练越久越好”只大体成立到平台期。

小模型尤其存在 accuracy 和 loss 不同步的问题。0.6B 的两-seed final accuracy 达到 58.64%，
但 final loss 0.7096 比随机 margin 对应的 `log(2)=0.6931` 更差，说明它虽然排对了更多 pair，
却可能在少数错误 pair 上给出过大的反向 margin。这里不应只看 accuracy，也要继续保留 loss 和
margin 分布诊断。

### 3.3 与 light predictor 比较

同一 value 数据上的便宜基线为：

| 模型 | Test accuracy |
| --- | ---: |
| TF-IDF + logistic regression | **61.18%** |
| Static features + logistic regression | 60.17% |
| Static features + gradient boosting | 57.94% |

0.6B 打不过 TF-IDF 和 static LR；1.7B 两-seed平均比 TF-IDF 低 0.51 个百分点。4B 平均比
TF-IDF 高 0.83 个百分点，但 seed 6 的 final 60.67% 仍低于 TF-IDF，因此还不能称为每个 run
都稳定领先。8B 的两个 seed 分别为 66.01% 和 63.34%，都超过 TF-IDF，平均优势为 3.50 个
百分点。14B 的两个 seed final 都是 65.76%，比 TF-IDF 高 4.57 个百分点；其 seed 6 best
达到 66.52%。

这组结果支持“需要一定模型容量才能超过文本统计捷径”，但两个 seed 仍不足以做严格显著性
结论。TF-IDF 已达到 61.18% 也说明 experiment 内配对没有消除所有浅层可学信号。

## 4. Spooky Author Leave-One-Task-Out

LOTO 从训练池完全移除 `spooky-author-identification`，使用其余 27 个任务的 12,556 条 pair
训练，并在目标任务的全部 964 条 pair 上评估。这里只运行了 seed 6。

| 模型 | Best accuracy | Final accuracy | Best 所在 epoch | Final loss |
| --- | ---: | ---: | ---: | ---: |
| Qwen3-0.6B-Base | 56.74% | 55.29% | 0.61 | 0.7799 |
| Qwen3-1.7B-Base | 53.01% | 50.73% | 0.41 | 0.8082 |
| Qwen3-4B-Base | 61.41% | 59.85% | 0.41 | 0.7942 |
| Qwen3-8B-Base | 60.58% | 57.68% | 0.41 | 0.8078 |

这组结果没有单调 scaling：1.7B 低于 0.6B，8B 低于 4B；所有模型的 best 都出现在训练中段，
final accuracy 比 best 低 1.5--2.9 个百分点，final loss 则上升到约 0.78--0.81，表现出明显
过拟合。4B 和 8B 高于随机不是“完全没学到信号”，但单 seed、非单调规模关系和后半程退化都
说明它不是稳健的 scaling 结果。

更根本的问题是评估任务可能偏离实际目标。LOTO 要求模型在没有见过目标 task 的任何训练 pair
时，直接判断这个任务中两份 MLE solution 谁更好；而真实 AIRA agent 至少会读到数据说明，并在
目标环境里执行和迭代。这更接近 zero-shot 跨任务代码排序，而不是 critic 在已知任务上的局部
决策。另一方面，输入仍包含 task name，base model 的预训练知识也可能提供先验，所以它又不是
严格的“零信息”测试。

因此 LOTO 可以作为很强的 domain-generalization 压力测试，但不适合作为当前 critic 是否有用
的唯一主指标。更贴近目标的测试是：保留目标任务、hold out 新 run/新 experiment/新策略模型，
或者直接测 critic 对实际搜索收益的改善。

## 5. Value checkpoint 到 Decision pair 的迁移

`logs/augmented_mle_critic/decision/` 评估的是 seed 7 value-pair 模型在 decision pairs 上的
zero-shot transfer。每个规模使用其 value validation 上保留下来的 checkpoint，因此 checkpoint
步数并不一致；另一组 seed 的 checkpoint 没有保存，不能估计 decision 迁移的 seed 方差。

| 模型 | Checkpoint | Filtered decision（960） | Unfiltered decision（1,708） | Filter 收益 |
| --- | --- | ---: | ---: | ---: |
| Qwen3-0.6B-Base | checkpoint-60 | 56.25% | 54.10% | +2.15 pp |
| Qwen3-1.7B-Base | checkpoint-90 | 56.25% | 55.39% | +0.86 pp |
| Qwen3-4B-Base | checkpoint-80 | 59.06% | 57.90% | +1.16 pp |
| Qwen3-8B-Base | checkpoint-60 | 59.38% | 57.38% | +2.00 pp |
| Qwen3-14B-Base | checkpoint-90 | **60.63%** | **58.02%** | +2.60 pp |

14B 把 filtered accuracy 再提高 1.25 个百分点，并首次超过 TF-IDF。不过整个序列并不平滑：
0.6B 和 1.7B 打平，4B 和 8B 也几乎打平，主要是 4B 和 14B 两次台阶式提升。Decision 侧又
只有 seed 7，因此它仍弱于 value test 上跨两个 seed 的单调 scaling 证据。

Gap filter 对五个模型都带来正收益，幅度为 0.86--2.60 个百分点，说明去掉外部 grade 分差太小
的 pair 确实提高了标签可辨识度。但 filtered test 只剩 960 条，而且包含大量共享 endpoint；
这项提升仍应在新的 seed/checkpoint 上复核。

Filtered decision 的 light predictor 为：

| 模型 | Test accuracy |
| --- | ---: |
| TF-IDF + logistic regression | **59.90%** |
| Static features + gradient boosting | 54.58% |
| Static features + logistic regression | 51.88% |

14B 的 60.63% 比 TF-IDF 高 0.73 个百分点，是目前唯一超过 TF-IDF 的 decision 结果；8B 和
4B 仍分别低 0.52 和 0.83 个百分点。这个优势还小于单个 seed 常见波动，不能单独视为稳定胜出。

与各模型 seed 7 的 value Best 相比，迁移到 filtered decision 后分别下降约 2.96、5.69、
4.98、4.54 和 5.13 个百分点。这比“完全不能迁移”稍好，但清楚表明 experiment 内全局
solution 排序和局部 decision 仍不是同一个任务。

## 6. 直接在 Decision pairs 上训练

`logs/augmented_mle_critic/decision_0815/` 使用 5,596 条 merged filtered decision train
pairs 训练，并在同一数据文件的 960 条 test pairs 上评估。训练配置与 value 实验基本一致，
但从 1 epoch 增加到 2 epochs。目前只有 seed 7，尚未训练 14B。

| 模型 | Best accuracy | Best epoch | Final accuracy | Final loss | 最低 eval loss（epoch） | 状态 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Qwen3-0.6B-Base | 56.56% | 1.43 | 56.35% | 0.7563 | 0.6866（0.82） | epoch 1.85 后中断 |
| Qwen3-1.7B-Base | 55.73% | 1.43 | 55.21% | 0.8603 | 0.6863（0.41） | 完成 |
| Qwen3-4B-Base | **59.38%** | 1.23 | 58.33% | 0.8645 | 0.6963（0.41） | epoch 1.85 后中断 |
| Qwen3-8B-Base | 55.83% | 0.62 | 55.31% | 0.8883 | 0.7030（0.21） | 完成 |

结果没有模型规模效应：4B 最好，8B 反而退回 0.6B/1.7B 水平。最佳的 4B 也只有 59.38%，
比 TF-IDF 的 59.90% 低 0.52 个百分点。相比同规模 value→decision 迁移，直接训练的 Best
分别变化 **+0.31、-0.52、+0.31、-3.54 个百分点**；没有证据表明换成更贴近目标的数据后就
自然学得更好，8B 甚至明显更差。但这里每个规模只有一个 seed，更准确的解释是当前训练设置对
8B 不稳定，而不是“大模型一定更差”。

更清楚的问题是过拟合。四个模型的最低 eval loss 都出现在 epoch 0.21--0.82，而 Best accuracy
除 8B 外出现在 epoch 1.23--1.43。到 epoch 1.85，eval loss 已升到 0.76--0.89，远高于训练
早期和 `log(2)=0.6931`。Accuracy 还能维持在 55%--58%，说明模型大体保留了一些排序方向，
但在错误 pair 上给出了越来越极端的 margin。第二个 epoch 没有带来可靠收益，后续不应继续照搬
当前 2-epoch 配置。

这里还有两个未拆开的变量：merged test 中 draft 只有 343 条、improve 有 617 条，而两类 pair
的语义不同；同时训练集只有 5,596 条，明显小于 value 的 11,946 条。下一轮应分别报告
draft/improve accuracy，并尝试 0.5--1 epoch、降低 learning rate、weight decay 或更早停止。

## 7. 总体判断与下一步

Experiment 内配对后出现清楚的 value scaling，是一个有意义的进展。它支持此前无 scaling
至少部分来自数据异质性和环境 shortcut。不过本轮同时改变了 pair 范围、数据量、gap filter 和
采样方式，不能把改善严格归因于单一因素；要做因果确认，需要在同一批 Cards 上构造 global-task
和 within-experiment 两个 matched 数据集直接比较。

新增结果说明，扩大模型和换成直接 decision supervision 是两条不同轴：14B 能延续 value scaling
并稍微改善迁移，但 0.6B--8B 的直接 decision 训练没有 scaling，而且严重过拟合。

接下来的优先级：

1. Decision 训练至少再跑一个 seed，并分别报告 draft test（343 条）和 improve test（617 条），
   同时保留 merged 指标。
2. 把直接 decision 训练缩短到最多 1 epoch，并基于 validation loss/accuracy 明确 early-stop
   规则；当前 2 epochs 已证明过长。
3. 补直接 decision 的 14B，并扩展到 27B。但所有规模应使用相同有效 batch、epoch 和 checkpoint
   选择规则，不能只比较各自挑出的 Best。
4. 保留 TF-IDF、static LR/GBM 作为每版数据的最低基线。14B 迁移只领先 TF-IDF 0.73 个百分点，
   如果不能跨 seed 保持，就不应视为已经稳定胜出。
5. 构造 global-task 与 within-experiment 的 matched 对照，隔离数据范围、gap filter 和采样变化，
   确认 value scaling 到底来自哪项改动。
6. 继续尝试 RL，把目标接到真实搜索收益。Pairwise RM 可以作为初始化、proposal reranker 或
   auxiliary loss，但最终应以固定计算预算下的 MLEBench agent 表现判断价值。

当前证据足以说明 value pairwise ranking 不是完全不可学，也出现了预期的容量 scaling；但直接
decision 训练仍不稳定，距离“critic 能够稳定改善 AIRA 的真实分支决策”还有明显差距。
