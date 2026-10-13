# 27B policy 到 E2E 评估（截至 10 月 12 日）

这份报告记录这次把直接训练 policy 从 9B 搬到 27B 后的第一轮对照：同一批 MLEBench 任务上，比较 27B 原模型、SFT adapter 和从原模型直接开始训练的离线 GRPO adapter。

## 1. 这次跑了什么

### 1.1 三个 arm

所有 arm 的 solver 都是 `mlebench/mcts`、`num_children=2`、`execution_timeout=7200`（单个解最多跑 2 小时）、`time_limit_secs=86400`（整个 run 最多 24 小时）。

| 目录名 | 生成模型 | 训练方式 | 步数 |
| --- | --- | --- | ---: |
| `mcts` | `Qwen/Qwen3.8-27B` 原模型，不挂 adapter | — | 基线 |
| `sft-v2-step665-lora` | 原模型 + SFT adapter | 第二版数据：限定 provider 后的数据 | 665 |
| `grpo-v3-step50-lora` | 原模型 + GRPO adapter | 离线 GRPO 数据 | 50 |

这里的 GRPO adapter 是**从 27B 原模型直接开始训练**，不是在 SFT adapter 上继续训练。

这次评估覆盖 5 个任务：`chaii`、`champs`、`dog-breed`、`osic` 和 `tgs-salt`。每个任务的目录在 `data/augmented_mle_critic/raw_journal/comparison/1012` 下。

### 1.2 指标怎么算

本报告全部沿用上一份报告的 journal 口径，不使用 `results/grading_report.json` 记录的最新得分。

每个搜索节点有两个分数：

- **内部指标 `metric`**：模型自己写的代码在自己划出的验证集上算出的分数，搜索按它挑节点；
- **官方分 `metric_info.score`**：这个节点的结果按 MLEBench 官方评测得到的分数。

为便于比较，RMSE / log loss 等越小越好的任务已经取负号，因此下面表里的分数都统一为“越大越好”。

表里的三个数和上一份报告完全相同：

- **`avg_selected_score`（主指标）**：每个 run 按最高内部指标挑出一个节点，取该节点的官方分，再在 run 之间平均；
- **`max_score`**：所有 run 中见过的最高官方分，看搜索过程中有没有找到好解；
- **`avg_max_metric`**：每个 run 的最高内部指标，再在 run 之间平均。

数字用 `src/dojo/analysis_utils/journal_to_fig.py` 的聚合函数重算，时间轴覆盖所有有效节点，取最后一个点。非有限数（如 `NaN`）不参与数值聚合；所选节点没有有效官方分的 run 不进入主指标均值，不补零，也不改选另一个节点。内部指标并列时保留 journal 中先出现的节点。`run 数` 写成“有 checkpoint journal 的 run / 目录里的 run”。

## 2. E2E 主表

| 任务（方向） | arm | run 数 | avg_selected_score | max_score | avg_max_metric |
| --- | --- | ---: | ---: | ---: | ---: |
| chaii（越大越好） | `mcts`（原模型） | 5/8 | 0.2083 | 0.5796 | 0.7375 |
| chaii | `sft-v2-step665-lora` | 5/8 | **0.3792** | 0.5665 | 0.5544 |
| chaii | `grpo-v3-step50-lora` | 6/8 | 0.3777 | **0.5949** | 0.5515 |
| champs（越大越好，分数已取负） | `mcts`（原模型） | 3/4 | -1.8934 | -1.6587 | 0.1964 |
| champs | `sft-v2-step665-lora` | 3/4 | -1.7169 | -1.5282 | 2.5455 |
| champs | `grpo-v3-step50-lora` | 3/4 | **-1.4443** | **-1.1733** | 0.9850 |
| dog-breed（越大越好，分数已取负） | `mcts`（原模型） | 4/8 | -0.6283 | **-0.3435** | -0.6537 |
| dog-breed | `sft-v2-step665-lora` | 2/7 | -1.3802 | -0.5100 | -1.4478 |
| dog-breed | `grpo-v3-step50-lora` | 1/6 | **-0.5398** | -0.5398 | -0.6171 |
| osic（越大越好，官方分本来为负） | `mcts`（原模型） | 2/2 | -18.8823 | -7.3286 | -5.0528 |
| osic | `sft-v2-step665-lora` | 2/2 | **-10.0626** | **-7.2786** | -2.9376 |
| osic | `grpo-v3-step50-lora` | 2/2 | -12.3457 | -7.3021 | -5.2905 |
| tgs-salt（越大越好） | `mcts`（原模型） | 4/4 | 0.3407 | 0.5738 | 0.8319 |
| tgs-salt | `sft-v2-step665-lora` | 4/4 | **0.5795** | 0.7440 | 0.7441 |
| tgs-salt | `grpo-v3-step50-lora` | 4/4 | 0.4625 | **0.7647** | 0.8437 |

## 3. 这轮结果怎么读

### 3.1 27B SFT 相比原模型：主指标 4 个任务更好，1 个任务更差

按 `avg_selected_score`，在 5 个任务中 SFT 赢了 4 个：

- chaii：0.2083 → 0.3792；
- champs：-1.8934 → -1.7169；
- osic：-18.8823 → -10.0626；
- tgs-salt：0.3407 → 0.5795。

唯一变差的是 dog-breed：-0.6283 → -1.3802。不过这个对比只有 4 个基线 run 和 2 个 SFT run，覆盖率很低，不能把这个差异当成稳定结论。

这和 9B 上“筛掉低质量 provider 后直接训 policy 有收益”的方向一致：换成 27B 后，SFT 的收益仍然能在这批 E2E 结果里看到，而且不是只发生在一个任务上。

### 3.2 27B GRPO 相比原模型：表面上 5 个任务都赢，但证据强弱不一样

按 `avg_selected_score`，GRPO 在 5 个任务都高于原模型：

- chaii：0.2083 → 0.3777；
- champs：-1.8934 → -1.4443；
- dog-breed：-0.6283 → -0.5398；
- osic：-18.8823 → -12.3457；
- tgs-salt：0.3407 → 0.4625。

但 dog-breed 的 GRPO 只有 **1/6** 个 run 有 journal，不能据此说 GRPO 在这个任务上已经稳定有效。去掉这个覆盖率极低的格子后，GRPO 在剩下 4 个任务上都是正向的，不过 chaii、champs 也分别只有 6/8、3/4 个 run 有 journal。

### 3.3 SFT 和 GRPO 的直接比较：没有一个方法全面胜出

在 `avg_selected_score` 上：

- SFT 胜 GRPO：chaii（0.3792 vs 0.3777）、osic（-10.0626 vs -12.3457）、tgs-salt（0.5795 vs 0.4625）；
- GRPO 胜 SFT：champs（-1.4443 vs -1.7169）、dog-breed（-0.5398 vs -1.3802）。

所以这轮更稳妥的结论不是“GRPO 取代 SFT”，而是：**从 27B 原模型直接做 policy 优化，两种训练目标都能带来收益；在当前这套数据和 50 步 GRPO 配置下，两者暂时无法排出总体优劣，GRPO 在 champs 上更好，但在 tgs-salt 和 osic 上不如 SFT。**

## 4. 这轮结果里的限制

1. **不同 arm 的 run 覆盖率不一致。** 例如 dog-breed 是基线 4/8、SFT 2/7、GRPO 1/6；很多数字实际只由 1–2 个 run 支撑，应当看方向，不要把小数点后四位当成精确估计。
2. **基线和 adapter 的 prompt 配置不完全相同。** 基线使用 `simple_memory`，adapter 使用 `no_memory`。也就是说基线 prompt 带搜索记忆，而 adapter 训练时没有这段记忆；这不是完全隔离的模型变量。要做严格的纯模型对比，需要用 `no_memory` 重跑 27B 基线。
3. **这是同一批历史竞赛任务上的 E2E 对照。** 训练数据来自历史 dojo run，评估任务也在这些历史数据中，因此结果可能同时包含“学会了更好的通用做法”和“记住了任务/解法”两部分收益，当前实验不能区分。
4. **这里只看 journal。** `results/grading_report.json` 记录的是最新提交的得分，不是本报告采用的搜索过程汇总口径；因此没有拿它替换或校正 journal 数字。

## 5. 结论

这轮 27B 结果支持一个比较明确但仍需扩大样本的判断：**直接优化 policy 在 27B 上仍然有效，SFT 和从原模型起步的离线 GRPO 都比原模型整体强。** SFT 在 5 个任务中 4 个主指标胜出，GRPO 表面上 5 个都胜出，但 dog-breed 的 GRPO 只有一个有效 run，不能算稳定证据。两种方法之间没有全面赢家；当前证据还不足以断言哪种方法更稳定，下一步应先补齐 journal 覆盖率，再验证不同训练步数和更多重复 run。

---

## 6. 补充：有效样本数和选解问题

### 6.1 有 journal 不等于进入均值

上表里的 `run 数` 只表示 journal 覆盖率。champs 基线虽然有 3 个 journal，但 seed 2 的 57 个节点没有有效的内部指标和官方分，因此三个指标实际都只由另外 **2 个 run** 支撑。其余 14 个格子的主指标有效 run 数与 journal 数一致。

不同 arm 的有效 seed 也不完全相同，不是严格的逐 seed 配对比较。最极端的是 dog-breed：GRPO 只有 seed 4，基线有 seed 1/2/6/7，SFT 有 seed 1/7。因此 GRPO 在这个任务的领先尤其不能当作可靠胜负。

### 6.2 搜到好解和按内部指标选到好解，仍然是两回事

补充一个指标 **`avg_max_score`**：每个 run 搜索过程中见过的最高官方分，再在 run 之间平均。它和主指标相比，可以看已经搜到的好解有多少没有被内部指标选中；它只是事后诊断，不是实际可用的选解方式。

| 任务 | arm | avg_max_score | avg_selected_score | 差值（搜到的最好分 − 选中分） |
| --- | --- | ---: | ---: | ---: |
| chaii | 原模型 | 0.4443 | 0.2083 | 0.2359 |
| chaii | SFT | 0.5207 | 0.3792 | 0.1415 |
| chaii | GRPO | 0.4890 | 0.3777 | 0.1113 |
| osic | 原模型 | -7.3840 | -18.8823 | 11.4983 |
| osic | SFT | -7.3378 | -10.0626 | 2.7247 |
| osic | GRPO | -7.4011 | -12.3457 | 4.9446 |
| tgs-salt | 原模型 | 0.5170 | 0.3407 | 0.1764 |
| tgs-salt | SFT | 0.6799 | 0.5795 | 0.1005 |
| tgs-salt | GRPO | 0.5954 | 0.4625 | 0.1329 |

- **osic 的提升主要体现在选中的解更好，而不是搜到的最好解明显更好。** 三个 arm 的 `avg_max_score` 都在 -7.4 附近，但基线选中的节点均分掉到 -18.88，SFT 和 GRPO 分别是 -10.06 和 -12.35。不能只用 `max_score` 的微小差别解释主指标的大幅提升。
- **chaii 和 tgs-salt 同时有两方面收益。** adapter 的每个 run 最好官方分平均更高，选解损失也更小。不过仍有严重反例：chaii 的 GRPO seed 6 内部指标达到 1.0000，所选节点官方分却是 0.0000，该 run 实际搜到过 0.5038。
- **tgs-salt 的 GRPO 搜到过全场最好的单个节点，但平均选解不如 SFT。** GRPO seed 3 搜到 0.7647，按内部指标选中的却是 0.3890；因此“最好官方分最高”不等于“主指标最高”。

这些数字支持继续检查内部验证代码和选解过程，但不能单凭分数差就确定存在什么具体 bug 或数据泄漏。
