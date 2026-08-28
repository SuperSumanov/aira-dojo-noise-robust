# Augmented pairwise critic：gap 分层、混合数据扩展与 RL 初步结果

## 这版报告回答什么

本报告记录截至 8 月 26 日已经完成的实验，不试图替代后续的总体研究判断。重点是把数据从哪里来、每个实验实际测了什么、结果是否可比较，以及目前证据能支持到哪一步说清楚。

### 结果的定位

本文所有 accuracy、loss、gap 分层和训练曲线都是 **proxy 指标**。它们只用于探索：数据构造是否留下可学习信号、不同训练目标是否有区别、模型规模是否值得继续投入，以及哪些设置明显有问题。它们不是 critic 最终是否有用的证明。

最终评价仍然是固定计算预算下，在 MLEBench/AIRA agent 上做 end-to-end 测试，看 critic 是否能改善真实搜索过程和最终任务成绩。在 end-to-end 测试完成前，本报告中的“提升”“scaling”都应理解为 proxy 实验中的现象，而不是 MLEBench 能力结论。

相对 0820 版，主要新增三件事：

1. 用 `gap_filter.py` 把旧数据的测试 pair 按两个 solution 的外部得分差距分成四档；
2. 把截至 0819 的 value、decision 和硬件/时间一致的 value 数据混合，探索 decision 训练是否能随模型规模扩展；
3. 为 instruction 模型准备 RL judger 数据，并比较 RL 与 Bradley–Terry（BT）监督训练的初步结果。

## 1. 数据与评估口径

### 1.1 Gap filter 分层

`src/mle_critic/src/postprocess/gap_filter.py` 按任务配置的单位 gap，把测试 pair 分为 `1–2`、`2–4`、`4–8` 和 `8+` 四档。这里的 gap 是两端已有 external grade 的差，不是模型预测的分差。

在截止 0815 的数据上，固定的 Qwen3-14B Base checkpoint 在四档上的结果如下。两个 seed 使用 checkpoint-80/90；它们的绝对数值略有不同，但形状一致：没有随 gap 单调上升。

| gap 档位 | pair 数 | seed 6 | seed 7 |
| --- | ---: | ---: | ---: |
| 1–2 | 339 | 62.24% | 62.24% |
| 2–4 | 368 | 66.85% | 66.03% |
| 4–8 | 373 | 64.34% | 62.73% |
| 8+ | 493 | 70.18% | 68.15% |

同一 checkpoint 在当时的 decision pairs 上，seed 6 为 `59.05%, 60.50%, 57.65%, 59.04%`（四档顺序相同；每档 232、200、196、332 条）。该曲线同样不单调。seed 7 目录中没有对应的 decision 分层文件，因此这里不补写一个不存在的 seed 7 结果。decision 侧的平坦/非单调形状进一步说明，不能把高 gap 档的 value 准确率简单解释成“gap 决定难度”。

这不是“差距越大越容易”的曲线：中间两档反而回落，最高档虽然较高，但不能据此排除任务/样本组成差异。更稳妥的解释是，gap filter 确实主要删掉了标签接近、很难从静态 solution 判断的 pair；它没有把整个测试集简单地按难度从低到高排序。四档的样本仍共享 Card endpoint，不能按独立样本做过强的显著性推断。

### 1.2 0819 数据集

截至 0819 的几个输入文件及当前记录数：

| 文件 | train | test | 合计 | 含义 |
| --- | ---: | ---: | ---: | --- |
| `batch_value_pairs_filtered_runsplit.jsonl` | 14,206 | 1,998 | 16,204 | experiment 内构建、gap filter、run split 后的 value pairs |
| `merged_decision_pairs_filtered_runsplit.jsonl` | 6,484 | 1,160 | 7,644 | draft + improve decision pairs |
| `value_pairs_hardware_timelimit_gap_filtered_runsplit.jsonl` | 7,703 | 895 | 8,598 | 两端硬件、时间限制、execution timeout 同 bucket 的 value pairs |
| `decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl` | 14,715 | 1,160 | 15,875 | 本轮混合数据，保留 decision test |

混合脚本 `build_decision_augment_pairs.py` 从三个来源按 **8:1:1**、目标 15,000 条训练池采样：

- experiment 切分的 value pairs；
- merged decision pairs；
- 全局构建、再经过硬件/时间分类过滤的 value pairs。

混合的动机是避免 value 分布离 decision 太远，同时避免 decision pair 因“同一 parent”而过于单一。脚本会去重，并移除与保留 test 重复的 pair，所以最终不是严格的 15,000 train，而是 14,715 train + 1,160 decision test。这里的 8:1:1 是采样权重，不等于最终文件中三类数据的精确占比；记录本身没有写入来源字段，后续无法仅凭输出文件恢复每条 pair 来自哪个池。

本轮大模型日志中的验证集正是 `train=14,715, validation=1,160`。因此它们与 0820 的 960 条 decision test 不是同一测试集，不能直接把两个报告的百分点差当成模型进步。

## 2. Qwen3 Base：混合数据上的模型规模

实验目录：`logs/augmented_mle_critic/0819/scale_decision/seed6` 和 `seed7`。下面的数值是日志中 validation accuracy 的最高值（若只记录到 epoch 0.96，则按最后一次记录）；`inst` 文件不在此表。

| 模型 | seed 6 best | seed 7 best | seed 6 final | seed 7 final |
| --- | ---: | ---: | ---: | ---: |
| Qwen3-0.6B Base | — | 56.38% | — | 55.69% |
| Qwen3-1.7B Base | 58.45% | 58.53% | 58.45% | 58.53% |
| Qwen3-4B Base | 57.84% | 59.66% | 57.84% | 58.53% |
| Qwen3-8B Base | 59.14% | 60.52% | 58.19% | 59.48% |
| Qwen3-14B Base | 57.84% | **62.76%** | 57.84% | 62.76% |

0.6B seed 6 的日志没有出现在目录中，不能把 seed 7 的结果伪装成两 seed 结论。Seed 7 从 1.7B 到 14B 有较明显的台阶式提升；seed 6 的 1.7B、4B、8B、14B 则没有同样趋势，14B 甚至低于 1.7B。8B seed 6 的最高值为 epoch 0.52，之后回落；14B seed 7 的最高值为 epoch 0.78，后期基本平台。

因此当前最具体的说法是：**这套混合数据在 seed 7 上出现了可见的规模效应，但 seed 6 没有复现。** 这支持“decision pair 测试集/训练分布的方差很大”这一怀疑，但还不能证明唯一原因就是 decision pair 的同 parent 结构。还可能包括 task/experiment 比例、重复 endpoint、两类 pair 的标签噪声，以及不同规模在相同优化配置下的过拟合差异。

轻量基线（同一混合数据、同一 1,160 条 test）为：TF-IDF logistic regression **56.64%**，static logistic regression **54.66%**，static gradient boosting **55.52%**。因此 seed 7 的 14B Base（62.76%）明显超过轻量基线，但 seed 6 的大模型并没有形成同样结论。

## 3. Instruction 模型与 Qwen2.5 对照

Qwen3 没有 14B 以上的 Base checkpoint，因此继续放大时使用 post-training 的 `inst` 模型。结果显示 instruction tuning 本身没有带来稳定收益：

| 模型 | seed 6 best | seed 7 best |
| --- | ---: | ---: |
| Qwen3-14B Base / Inst | 57.84% / **61.55%** | 62.76% / 59.74% |
| Qwen3-32B Inst | 56.81% | 58.19% |

seed 7 中 14B/32B Inst 都低于 14B Base；seed 6 中 14B Inst 反而是该 seed 最好，32B Inst 很差。这个交叉结果进一步说明当前 test variance 足以盖过模型规模和模型家族差异。Inst 模型也改变了模型的行为分布，不能简单视为 Base 的“更大版本”。

Qwen2.5 只跑了 seed 7：3B **59.14%**、7B **59.83%**、14B **61.12%**、32B **61.47%**（均为 best）。有轻微规模趋势，但全线低于 Qwen3 Base 的最好结果；由于只有一个 seed，且预训练起点不同，这个对照不适合用于判断 Qwen3 的规模律是否成立。

## 4. 轻量 decision 基线

`logs/augmented_mle_critic/0819/decision` 使用纯 decision pair；`scale_decision` 使用上面的混合训练集。两者的轻量结果分别是：

| 训练数据 | TF-IDF LR | static LR | static GBM |
| --- | ---: | ---: | ---: |
| 混合（1,160 test） | 56.64% | 54.66% | 55.52% |
| 纯 decision | 59.05% | 54.05% | 55.69% |

纯 decision 对轻量模型更好，而大模型在本轮混合/ value 数据上更好。这说明“更贴近 decision 的分布”对不同模型容量的作用不同，不能把轻量基线的结论直接外推到大模型。纯 decision 的 TF-IDF 仍然是一个需要跨 seed 固定保留的强基线。

## 5. RL judger 数据流水线与初步结果

https://wandb.ai/zizhechen-the-chinese-university-of-hong-kong/mle-critic-rl/reports/MLE-critic-RL---VmlldzoxNzgyMzU1Nw?accessToken=3wv2wd5g3h9fk47lqyojqc8a8fpfrnva7cutmr3vof98edzl541xmartzgrvchzj

流水线位于 `src/mle_critic/src/postprocess/rl`：

1. `rl_system_prompt.py` 从每个任务找到一份 step-1 journal，抽取 competition instructions、data overview 和 constraints，拼成统一 system prompt；
2. `build_judger_messages.py` 读取 pair 和 Card，把两份 solution 放进 user prompt，随机决定 A/B 位置，答案是 `A` 或 `B`；
3. `measure_context.py` 可按目标模型 tokenizer 统计上下文长度，并过滤超长样本。

RL 的 prompt 让模型先分析两份 submission，再在 `\\boxed{A/B}` 中作答；这与 BT 训练中直接从 hidden representation 输出 pairwise score 不是同一种学习目标。RL 结果在另一台机器生成，完整训练配置和奖励曲线待补入；当前仓库日志可确认的对照如下。

### 5.1 在混合 decision test 上

混合训练集、decision test 的 RL 实验没有随训练步数稳定提升；validation accuracy 在训练过程中上下波动，不能据此宣称 RL 学会了可迁移的 decision 判断。该 test 只有 1,160 条 pair，且 draft/improve 混合，结论尤其容易受组成和 endpoint 相关性影响。

### 5.2 在 experiment 切分的 value test 上

在 experiment 切分 value pair 上，RL accuracy 随训练步数有上升迹象，但 Qwen3-14B 的最高准确率约 **0.59**。这说明 RL 目标并非完全不可学，但在当前设置下提升有限，而且不能证明它能迁移到 decision。

### 5.3 BT 对照（`logs/augmented_mle_critic/0819/scale_reward`）

同一 value test 上、seed 7 的 BT 结果为：

| 模型 | Best accuracy |
| --- | ---: |
| Qwen3-0.6B | 60.31% |
| Qwen3-1.7B | 59.56% |
| Qwen3-4B | 60.71% |
| Qwen3-8B | **64.11%** |

RL 的 14B 约 59% 低于 BT 8B 的 64.11%。这不是严格 matched 的模型/训练预算比较，但至少说明“换成 RL 并自然获得更强 scaling”尚未出现；RL 的收益需要在固定 rollout、奖励定义和训练预算后重新比较。

## 6. 目前明确的局限

### 6.1 RL system prompt 存在硬件/时间条件错配

当前 `rl_system_prompt.py` 对每个 task 只读取第一份实验的 step-1 journal，并把其中的 constraints 固化成 task-level prompt。后续实验同一 task 可能使用不同 hardware、time limit 或 execution timeout，因此 pair 两端实际运行条件可能与 prompt 不一致。这是实质性数据问题：模型可能被要求在错误的资源条件下判断 solution，RL 结果应先标记为有条件地可信，不能与修复后的版本直接合并比较。

更安全的改法是按 pair/Card 的实际物理条件生成 prompt，或至少按 `(task, time_limit, execution_timeout, hardware)` bucket 生成并在构建时校验两端一致；不要继续用第一条 journal 作为全局兜底。

### 6.2 测试集规模不等于独立信息量

run split 防止了同一 physical run 的直接泄漏，但 pair 会共享 Card endpoint；decision test 还混合了 draft 与 improve。

### 6.3 混合采样改变了训练分布，却没有保留 provenance

输出文件没有来源字段，无法按 value/decision/hardware-time 三类分别评估训练覆盖，也无法检查去重后实际比例。下一版构建应写入 `source_dataset`、原始 experiment/run、pair 类型（draft/improve）等元数据，并在 test 中固定每一类的数量。

## 7. NEXT

我感觉value或decision pair这两个proxy的上限就是60%到70%这个区间里了，接下来我主要想一下这个能不能转化成MLE的e2e表现，还有怎么转化。

另外，确实有一些工作已经做过MLE分支预测了，这没办法，毕竟这个想法比较intuitive，而且这个方向热度也不低。我仍然认为这个方向是有价值和有空间的，所以这种情况下我们能做的就是继续往前，不必拘泥于这两三个月做的数据采集和训练等一系列工作，完全可以当是初期探索和经验积累。目前我进一步的想法是：

> 之前有个叫self-improvement的方向，大概的做法就是一个LLM作为generator生成，然后另一个LLM+一些heuristic方法作为verifier评估生成的好坏，再用verifier的反馈对generator进行训练。这个方法没有成为主流，我个人的看法是，在完全无label的情况下，generator就是拟合到LLM+heuristic方法构成的分布上，所以强依赖heuristic方法的性能，而heuristic方法，根据“the bitter lesson”，通常都非常局限，所以这种情况的self improvement只能带来少量的提升，无法做到“左脚踩右脚”那样的效果。在有label的情况下，多做一层self improvement的收益通常不如多训一点label。然而MLE是一个夹在中间的情况，有label，但label非常贵而且少，那说不定，在生产label的过程中，加以generator+verifier的反复self improvement，可以用更少的label训练出更好的generator。我应该是没有看到有类似的论文，如果能做成，那我们对比纯训练generator和纯用critic/verifier的工作都有创新。我们目前所做的数据搜集和训练，都可以当作对critic能力的探索和验证。

非常抱歉手上的一些gpu没法直接共享给你，但我会尽量把我所有的实验记录同步到云上。你可能多帮我看一下，防止我有一些忽略的点。其他想要你做的事情还有：

1. 我会给你一个openrouter的api，挑一部分好的reward和decision pair（标准你来决定吧），测一下便宜的强模型，比如ds flash，glm flash，qwen flash，以及免费模型，比如nemotron和其他openrouter免费榜上的模型。不要对输入输出有任何限制，看看准确率多少（之前你做的truncate输入不太合理）。把它们的思维链等数据都保留下来。
    1. api key我微信发给你。
    2. 我限额了50刀，尽量省一点。
2. 看看上面那个想法有没有可能你尝试实现一个demo版的？找两三个特别简单的任务，拿上面的api采一点数据微调一下qwen3 0.6b/qwen3.5 0.8b作为generator，然后critic用tfidf都可以，简单把demo搭一下。
3. wandb上有3个8xh200的RL实验结果，保留了推理轨迹，也看一下它们，比如训练过程中的变化，以及它的推理和上面强模型的推理在表现和思路上有没有不同之类的。

## 相关文件

- `src/mle_critic/src/postprocess/gap_filter.py`
- `src/mle_critic/src/postprocess/hardware_timelimit_filter.py`
- `src/mle_critic/src/postprocess/build_decision_augment_pairs.py`
- `src/mle_critic/src/postprocess/rl/rl_system_prompt.py`
- `src/mle_critic/src/postprocess/rl/build_judger_messages.py`
- `src/mle_critic/src/postprocess/rl/measure_context.py`
- `data/augmented_mle_critic/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl`
- `logs/augmented_mle_critic/0819/scale_decision/`
- `logs/augmented_mle_critic/0819/scale_reward/`

数据文件commit id：61459c0a1248900079dafed7c505afa87e476b40