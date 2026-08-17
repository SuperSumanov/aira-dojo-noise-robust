# 16K Context Qwen3 Critic 实验与失败原因分析

## 结论摘要

这批实验没有改变 0812 的总体判断。

1. 在 decision pairs 上训练、仍在 decision pairs 上评估时，Qwen3 0.6B--8B 的 final accuracy 均值为 **50.97%**；在 value pairs 上训练、转到 decision pairs 上评估时，均值为 **51.35%**。两种训练数据只差 **0.38 个百分点**，都没有稳定高于随机，也没有模型规模效应。因此没有继续评估按预算拆开的 b0/b1/b2 decision 集。
2. 在 value pairs 上训练和评估时，准确率稳定高于随机，seed 7 的 final 均值为 **59.48%**，但从 0.6B 增大到 8B 没有单调收益。所有运行中最高的单次 validation accuracy 为 4B 的 **62.38%**，仍低于学生此前 run-clean 1.5B RM 的 **64.93%**。把 context 扩到 16,384 token、换成 Qwen3 系列都没有带来预期改善。
3. 一个合理但尚未被直接验证的解释是：旧 value-pair 任务允许 critic 利用策略模型的输出风格、代码习惯或搜索阶段等捷径。不同策略模型在相同任务和近似预算下的得牌率可以相差几十个百分点；字符 n-gram 加回归也能在 value pairs 上取得不错结果，与这个解释一致。
4. decision pairs 更接近真实搜索中的同父兄弟选择，两端代码更相似，且约一半 b0 测试对的原始分差小于 `1e-2`。静态代码很可能本来就不足以稳定区分这些近平局。
5. 下一步倾向转向直接围绕下游搜索收益优化的 RL。RL 不保证自动消除 shortcut，但它至少不再把一个容易被表面特征拟合的静态 pair 标签当作最终目标。

## 可复现版本与实验口径

本文整理时的仓库 commit 为：`d9d0678c5dd8fdc7b77ae6bd248a00e559235074`，但基建已有更改。但训练运行的commit为`ba81b102282f252e3d7f8a1374ff55b73fd740ce`。

仓库内需要的主要输入和入口如下：

- `data/mle_critic/decision_pairs_runsplit.jsonl`：5,281 条 train、2,087 条 test；混合 budget 的 decision pairs。
- `data/mle_critic/value_pairs_runsplit.jsonl`：13,745 条 train、2,536 条 test；run-split value pairs。
- `data/mle_critic/decision_clean_b0.jsonl`
- `data/mle_critic/decision_clean_b1.jsonl`
- `data/mle_critic/decision_clean_b2.jsonl`
- `data/mle_critic/cards_current.jsonl`
- `src/mle_critic/scripts/train/pro6000/train_decision.sh`
- `src/mle_critic/scripts/train/pro6000/train_lookahead.sh`
- `src/mle_critic/src/train/bradley_terry.py`
- `src/mle_critic/recipes/zero3.yaml`

统一训练配置为：

- Qwen3 Base 0.6B、1.7B、4B、8B，全参数微调；
- 2 张 96 GB GPU，bf16、DeepSpeed ZeRO-3；
- `max_len=16384`，保留代码头部 25% 和尾部 75%；
- learning rate `1e-5`，cosine scheduler，warmup ratio `0.03`；
- 每个规模的有效 pair batch 都是 128；
- 每 10 个 optimizer step 评估一次；
- decision 训练 2 epochs，并启用 task/budget conditioning；
- value 训练 1 epoch，启用 task conditioning，不输入 budget；
- 主 seed 为 7；value→value 另补了 seed 6 的 0.6B、1.7B 和部分 4B 运行。

指标为训练过程中记录的 `eval_pair_accuracy`。本文同时报告：

- **Best**：该运行所有已记录 validation 中的最高 accuracy；
- **Final record**：日志中最后一次 validation accuracy，不一定恰好位于 epoch 结束处。

4B 的部分运行和 8B 的部分 value 运行没有完成，表中保留最后一条有效记录并明确标注。Best 是多次查看 validation 后的最大值，会有选择偏差；主要结论应优先看 final 和跨模型均值。

## 1. Decision pairs 训练，decision pairs 评估

训练和评估都使用 `decision_pairs_runsplit.jsonl`，共 5,281 条训练 pair 和 2,087 条测试 pair。模型输入包含 task、code 和 budget。

| 模型 | Best | Final record | 最后记录 epoch | 状态 |
| --- | ---: | ---: | ---: | --- |
| Qwen3-0.6B-Base | 52.66% | 50.22% | 1.92 | 完成训练 |
| Qwen3-1.7B-Base | 50.84% | 50.31% | 1.92 | 完成训练 |
| Qwen3-4B-Base | 52.18% | 51.75% | 1.68 | 中断 |
| Qwen3-8B-Base | 52.04% | 51.61% | 1.92 | 完成训练 |
| **均值** | **51.93%** | **50.97%** | | |

所有 final 结果都在 50%--52% 附近。0.6B 的 best 比 final 高 2.44 个百分点，说明偶然挑一个 validation checkpoint 会让结果看起来稍好，但这种收益没有跨模型保持。模型从 0.6B 增大到 8B 也没有形成上升趋势。

基于这组结果，没有继续在 `decision_clean_b0.jsonl`、`decision_clean_b1.jsonl` 和 `decision_clean_b2.jsonl` 上做不同剩余预算的细分评估。当前模型连混合 decision 测试集都没有稳定信号，进一步拆小测试集不会改变主结论。

## 2. Value pairs 训练，decision pairs 评估

这一组用 13,745 条 value train pairs 训练，但 validation 换成同一份 2,087 条 decision test pairs。它直接检查在较容易的全局 value 任务上学到的信号能否迁移到真实局部选择。

| 模型 | Best | Final record | 最后记录 epoch | 状态 |
| --- | ---: | ---: | ---: | --- |
| Qwen3-0.6B-Base | 53.28% | 51.89% | 0.56 | 中断 |
| Qwen3-1.7B-Base | 52.42% | 50.74% | 0.93 | 完成训练 |
| Qwen3-4B-Base | 51.37% | 51.37% | 0.56 | 中断 |
| Qwen3-8B-Base | 51.65% | 51.41% | 0.37 | 中断 |
| **均值** | **52.18%** | **51.35%** | | |

这组 final 均值只比 decision→decision 高 **0.38 个百分点**，best 均值只高 **0.25 个百分点**。差异小于单次运行和 checkpoint 之间的普通波动，不能解释为 value supervision 带来了可迁移能力。

因此也没有继续做 b0/b1/b2 分预算测试。到这里可以把问题说得更具体：**value-pair benchmark 上可学习的信号，没有自然迁移到同父兄弟 decision。**

## 3. Value pairs 训练，value pairs 评估

这一组训练和 validation 都使用 run-split value pairs。与 decision 结果不同，所有模型都明显高于随机，但没有规模效应。

| Seed | 模型 | Best | Final record | 最后记录 epoch | 状态 |
| ---: | --- | ---: | ---: | ---: | --- |
| 7 | Qwen3-0.6B-Base | 60.37% | 59.90% | 0.93 | 完成训练 |
| 7 | Qwen3-1.7B-Base | 59.42% | 58.08% | 0.93 | 完成训练 |
| 7 | Qwen3-4B-Base | 62.38% | 59.78% | 0.56 | 中断 |
| 7 | Qwen3-8B-Base | 60.73% | 60.17% | 0.47 | 中断 |
| | **Seed 7 均值** | **60.73%** | **59.48%** | | |
| 6 | Qwen3-0.6B-Base | 61.67% | 59.86% | 0.93 | 完成训练 |
| 6 | Qwen3-1.7B-Base | 60.57% | 60.02% | 0.93 | 完成训练 |
| 6 | Qwen3-4B-Base | 61.20% | 55.32% | 0.65 | 中断 |

几个观察：

1. 0.6B 与 1.7B 在两个 seed 上的 final 均值分别为 **59.88%** 和 **59.05%**；更大的模型没有稳定更好。
2. 单次最高 best 是 4B seed 7 的 **62.38%**，但另一个 seed 的 4B 在中断前 final 只有 **55.32%**，不能把最高 checkpoint 当成规模效应。
3. 8B seed 7 的 final 为 **60.17%**，与 0.6B 相当。
4. 学生此前在相同 run-clean 问题上报告的 1.5B RM accuracy 为 **64.93%**。当前实验把 context 从学生配置的 2,048 扩到 16,384，并换用 Qwen3 0.6B--8B，仍没有超过该结果。

所以更准确的结论不是“critic 完全学不到东西”，而是：**它能在全局 value pairs 上学到某种排序信号，但该信号不随模型规模和 context 稳定增强，也没有迁移到真正需要的局部 decision。**

## 4. 为什么 value pairs 可能存在策略模型捷径

### 4.1 策略模型本身会大幅改变轨迹质量

我们用 card 得牌率作为粗略 proxy，比较了不同时间段和不同策略模型产生的运行。得牌率不是最终 agent-level 成绩，也不是独立同分布样本，但差异大到不能忽略。

在相同 RTX 3090、相同约一天总时限和 2--6 小时单次执行上限下，旧版与新版 DeepSeek Flash 在共同任务上的 card 得牌率包括：

| 任务 | 旧版 | 新版 | 变化 |
| --- | ---: | ---: | ---: |
| denoising-dirty-documents | 21.29% | 62.44% | +41.15 pp |
| nomad2018-predict-transparent-conductors | 12.16% | 42.67% | +30.51 pp |
| tabular-playground-series-may-2022 | 0.00% | 0.00% | 0.00 pp |

放宽硬件限制、看更多共同任务，方向仍一致。例如：

- `mlsp-2013-birds`：7.74% → 45.54%；
- `google-quest-challenge`：29.87% → 56.94%；
- `kuzushiji-recognition`：2.08% → 28.57%；
- `spooky-author-identification`：8.87% → 33.52%；
- `nomad2018-predict-transparent-conductors`：14.57% → 39.46%。

半天总时限、约一小时执行上限的其他模型也有类似差异。比如同一个 essay scoring 任务，Mimo、MiniMax 和 Hunyuan 系列样本的得牌率分别约为 2.27%、18.00% 和 0%；俄语 text normalization 上，Mimo、GLM 和 Qwen Flash 样本分别约为 13.78%、9.78% 和 0%。这些不是严格配对实验，但足以说明“由哪个策略模型生成”与轨迹质量高度相关。

这部分统计依赖原始运行记录，未纳入本文的仓库内可复现核心；表中的数字用于提出假设，不用于因果证明。

### 4.2 Critic 可能学了什么

value pairs 可以比较同一任务中相距较远的节点。不同策略模型、不同搜索阶段或不同质量层级的代码，往往同时带有可识别的表面差异，例如：

- 常用库、模型家族和超参数模板；
- validation、ensemble、submission 等代码结构；
- 注释、变量名和错误处理习惯；
- 代码长度以及一个方案看起来处于探索早期还是收尾阶段。

如果某个策略模型整体得分更高，critic 只要识别出它的输出习惯，就能在 value pairs 上取得高于随机的 accuracy，而不必真正判断两段代码在当前数据集上谁会泛化得更好。这是一个很便宜的局部解。

字符 n-gram + 回归曾在全局 value pairs 上取得约 0.67，也与这个解释一致：便宜的文本统计特征已经能吃到不少信号。但这仍不是直接证据。要确认该假设，最便宜的诊断是按策略模型做 held-out split、只比较同策略模型产生的 pair，或先去除明显风格特征再评估。如果准确率明显下降，才能更有把握地说 critic 依赖了策略身份。

## 5. 为什么 decision pairs 更难

decision pairs 来自同一个 parent 的兄弟节点，更接近 AIRA 搜索时真正要做的局部选择。两段代码通常只差一次局部修改，因此策略模型身份、总体代码框架和搜索阶段大多相同，value pairs 中可用的捷径自然被削弱。

此外，当前 `decision_clean_b0.jsonl` 的 test split 约一半 pair 的 `gap_raw < 1e-2`。学生冻结版本的审计也得到近似结论：真实 sibling b0 中约一半是这种小分差 pair。对这些样本，标签虽然可以按外部 grade 排出 better/worse，但静态代码未必包含足够信息，让任何 critic 稳定预测微小的最终分差。

这能同时解释两个现象：

1. RM、TF-IDF、手工静态特征和 LLM judge 到真实 sibling decision 上都接近随机；
2. value→decision 与 decision→decision 几乎没有差别，因为前者学到的全局表面信号在同父兄弟之间基本被控制掉了。

精制 decision 数据是一条可行路线，例如去掉近平局、提高标签重复测量质量、只保留后果差异明确的操作，或按 gap 加权。但这会把主要精力投入到数据筛选规则，而且筛出来的 benchmark 可能再次偏离真实搜索分布。

## 6. 下一步：把优化目标接到真实搜索回报

下一步优先考虑 RL，而不是继续扩大静态 pairwise critic。核心动机RL的泛化性

https://arxiv.org/abs/2509.04259

不过 RL 不是自动泛化器。它仍可能利用 reward loophole，也会带来更高方差、更多执行成本和 off-policy 数据问题。第一版应尽量小：固定少量任务和预算，以真实搜索收益为主指标，并保留不参与训练的策略模型或任务作为泛化测试。只有这样才能判断 RL 是否真的解决了当前的拟合目标问题，而不是换了一种 shortcut。

## 总体判断

16K context、Qwen3 模型系列和更大参数量都没有救活静态 decision critic。value-pair accuracy 确实高于随机，但它更像一个容易利用全局分布差异的离线排序任务；一旦转到同父兄弟的真实局部选择，这些信号基本消失。
