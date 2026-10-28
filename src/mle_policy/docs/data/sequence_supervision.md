# 第二轮训练数据：以整次运行为单位的序列监督

## 1. 设计目标

端到端评估时，一次运行会产生多个 solution，最终按模型自己报告的验证集 metric
选出最优 solution，再以这个 solution 的测试集 score 作为该次运行的分数。
第二轮将同一个评价规则用于训练标签：整次运行中的所有模型调用，共享最终选中
solution 的奖励。

这版数据从 `data/augmented_mle_critic/raw_journal/seqsup/1027` 开始。
构建代码在 `src/mle_policy/src/data/run_level/`：

- `big_journal.py`：读取 journal、选出 metric 最优节点、为每次模型调用附上整次运行的标签，
  将整次运行视作一个episode

分组，归总、训练集/验证集切分、SFT 和 GRPO 导出继续使用原有程序。

## 2. 与第一轮的区别

这里的 sample 是一次模型调用，包含输入 prompt 和输出 completion；episode 是共享一个
结果标签的调用集合；group 是用来比较多个 episode 的集合，集合中的每个 episode
称为一个 member。batch 是存放同一批实验 run 的目录。

| 项目 | 第一轮：步骤监督 | 第二轮：序列监督 |
| --- | --- | --- |
| 一个 episode | 一次提案及其后续 debug 调用，直到得到可运行结果或停止修复 | 一个 journal 中的全部模型调用 |
| group 的划分 | 同一 batch、同一环境下，episode 初始 prompt 相同 | 同一 batch、同一环境下的 journal 放在一起 |
| score 标签来源 | 该步骤 episode 最后得到的可运行 solution | 整本 journal 中 metric 最优 solution 的 score |
| metric 标签来源 | 该步骤 episode 最后得到的可运行 solution | 整本 journal 中最优的 metric |
| SFT 选择 | 每组奖励最高的步骤 episode | 每组奖励最高的 journal |
| GRPO 奖励分配 | 一个步骤 episode 内的调用共享奖励 | 一个 journal 内的全部调用共享奖励 |

例如，一个 batch 中有三个 seed，且实验环境相同，输出结构为：

```text
batch
└── group
    ├── member / episode：seed 1 的整个 journal → 全部调用 sample
    ├── member / episode：seed 2 的整个 journal → 全部调用 sample
    └── member / episode：seed 3 的整个 journal → 全部调用 sample
```

即一个 group、三个 member。环境指纹仍使用现有定义，包含任务、硬件、时间限制、
执行超时、子节点数和模型等配置；环境指纹不同的 run 分到不同 group。

## 3. 标签如何计算

遍历整本 journal，从非 buggy 且 metric 为有限数的节点中选出最优节点。
`metric_maximize=true` 时取最大 metric，`false` 时取最小 metric；并列时取最先记录的节点，
与 Dojo 的选解规则一致。选解只看 metric。

整本 journal 的每条 sample 都带上相同的 episode 标签：

| 字段 | 含义 |
| --- | --- |
| `episode_score` | metric 最优节点的测试集 score |
| `episode_metric` | 该节点的 metric |
| `episode_reward` | 归一化后的 `episode_score`，用于 score 监督 |
| `episode_metric_reward` | 归一化后的 `episode_metric`，用于 metric 监督 |

两种奖励沿用原有公式，使用所选节点记录的比赛阈值：

```text
reward = (value - median_threshold) / (gold_threshold - median_threshold)
```

没有可选节点的 journal 仍作为一个 member 保留，`episode_resolved=false`，两种奖励为
`null`。选中节点的 score 缺失或非有限时，保留选解结果，`episode_reward` 为 `null`。
阈值缺失、非有限或 gold 与 median 的差过小时，归一化奖励也为 `null`。
下游 GRPO 默认给缺失奖励的 member 使用“组内最低有效奖励减 1”；整组没有有效奖励时跳过。

## 4. 中间文件和下游行为

每个 run 优先读取 `JOURNAL.jsonl` 导出；只有 checkpoint 时读取 `journal.jsonl`。
两种文件同时存在时只读导出文件，一次运行对应一个 episode。

每个 batch 仍输出 `samples.jsonl`、`groups.jsonl` 和 `manifest.json`：

- `samples.jsonl`：每次模型调用一条，保留逐节点的 score、metric 和 reward，同时附上整本
  journal 的 episode 标签。失败调用以及最优 solution 之后的调用也包含在内。
- `groups.jsonl`：每个 member 的 `sample_ids` 引用该 journal 的全部 sample。
- `manifest.json`：记录数量、运行配置和环境信息，并以 `episode_unit=journal` 标明监督单位。

`episode_terminal_step` 记录 metric 最优节点的 step；`steps_to_terminal` 记录从当前节点
到 journal 末尾的节点数，包含当前节点。

SFT 按 `episode_reward` 选出组内最好的 journal，导出其中全部调用。GRPO 按组内奖励计算
优势值，默认公式为 `(reward - 组内均值) / 组内标准差`，然后将同一个 journal 的优势值
赋给其中每次调用。

目前训练损失仍按调用计算，因此调用更多的 journal 会贡献更多训练项。
prompt 导出沿用原有处理：整理包名顺序，默认删除提案 prompt 中的搜索历史。
GRPO 可用 `--keep-search-memory` 保留历史。

metric 奖励使用与 score 相同的比赛阈值。两者优化方向一致时，组内排序一致；量纲差异
仍会影响奖励数值、失败惩罚与有效奖励的间距，以及启用 clipping 时的截断结果。

## 5. 运行方法

在仓库根目录执行。输出单独放在 `data/mle_policy/dataset/seqsup/1027`。

### 5.1 构建每个 batch

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
INPUT_ROOT=data/augmented_mle_critic/raw_journal/seqsup/1027
OUT_ROOT=data/mle_policy/dataset/seqsup/1027

bash src/mle_policy/scripts/data/build_all_batches_run_level.sh "$INPUT_ROOT" "$OUT_ROOT"
```

`build_all_batches_run_level.sh` 让公共的 `src/mle_policy/src/data/build_batch_groups.py` 从
`src/mle_policy/src/data/run_level/big_journal.py` 导入 journal 级的 `iter_episodes`；
输出位于 `$OUT_ROOT/batches/<bucket>/<batch>/`。
可再加 `--print` 仅查看发现的 batch。1027 这批数据归入 `thinking` 桶。

### 5.2 归总和切分

```bash
bash src/mle_policy/scripts/data/aggregate_batches.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/assign_splits.sh "$OUT_ROOT" group 0.1
```

按 group 切分，使同组的三个 journal 一起进入训练集或验证集。
后续只调整切分时，从这一步重新运行，再重新导出所需训练格式。

### 5.3 导出训练 JSONL

```bash
# SFT：按选中 solution 的测试集 score 选择最佳 journal
bash src/mle_policy/scripts/data/to_sft.sh "$OUT_ROOT"

# GRPO：使用 episode_reward，即选中 solution 的测试集 score 奖励
bash src/mle_policy/scripts/data/to_grpo.sh "$OUT_ROOT"

# GRPO：使用 episode_metric_reward，即整次运行的最优 metric 奖励
PYTHONPATH=src/mle_policy python -m src.data.to_grpo \
  --dataset "$OUT_ROOT/thinking" \
  --output-dir "$OUT_ROOT/thinking/grpo_metric" \
  --use-metric-reward
```

SFT 和 score GRPO 分别写到 `$OUT_ROOT/thinking/sft.jsonl`、
`$OUT_ROOT/thinking/grpo.jsonl`；metric GRPO 写到
`$OUT_ROOT/thinking/grpo_metric/grpo.jsonl`。
需要保留搜索历史时，在相应的 `python -m src.data.to_grpo` 命令末尾加
`--keep-search-memory`。JSONL 到训练 Parquet 的转换继续使用训练侧现有流程。