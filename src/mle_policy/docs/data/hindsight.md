# Hindsight：从搜索经验生成训练回答

一次完整的 GPU allocation 中完成重写，再接现有的数据处理和训练流程。
模型先从历史轨迹提炼文字经验（hint），然后带着这些经验重新回答原问题。
训练样本保存原始输入和这次生成的完整回答，包括思考、计划和代码。

代码阅读顺序见 `hindsight_impl.md`；少量案例的执行对照见 `hindsight_eval.md`；
方案演变见 `hindsight_history.md`。

## 1. 重写哪些轨迹

一个 episode 指一次 draft/improve 提案，加上随后连续的 debug 节点；
第一个跑通的节点是这段轨迹的终点。

- **debug 重写**：提案经过 debug 才跑通，把调试经验带回该提案的原始输入，重新完整作答。
- **improve 重写**：一个跑通提案的直接后继 improve 提案取得更好 CV，把后继经验带回前一个提案的原始输入。

CV 是 agent 自己产生的交叉验证分数。方案优劣按原节点的 `metric_maximize`
决定方向，要求严格提升。hint 提炼读取计划、执行输出、分析和来源终点代码。
超过当前字符阈值的长轨迹先逐步提炼，再合成为一个 hint。

`--mode debug` 选择第一类；`--mode debug-improve` 选择两类，默认用后者。
一个以 improve 开头、经过 debug 才跑通的 episode 也属于 debug 重写的对象。
`--hint-code omit` 让重新作答只看文字经验；`include` 额外给来源终点代码。

## 2. 输入和输出目录

`--input` 是包含多个 dojo run 的树；每个 run 的相对路径保持不变。

```text
<input>/batch/task/run/
  dojo_config.json
  env_variables.json                 # 存在时复制
  json/JOURNAL.jsonl                  # 原始大 journal

<output>/batch/task/run/
  dojo_config.json
  env_variables.json
  json/JOURNAL.jsonl                  # 重写后的大 journal
  checkpoint/journal.jsonl            # 同一批节点的小 journal
```

大 journal 每行是 `{timestamp, step, data}`，`data` 内为节点；
小 journal 每行直接是节点，`metric_info/...` 字段还原成嵌套的 `metric_info`。
输出树只包含新回答和连接其原父节点所需的祖先。祖先保留树关系和来源引用，
`code` 为空，`operators_used`、`operators_metrics` 为空。

新回答节点的主要字段：

| 字段 | 内容 |
|---|---|
| `parents` | 原提案的父节点 step；保留训练分组关系 |
| `operators_metrics[0].prompt_messages` | 原始输入 |
| `operators_metrics[0].completion_text` | 新生成的完整思考、计划、代码 |
| `code` / `plan` | 从新回答解析出的程序和计划 |
| `metric` / `metric_maximize` | 继承的来源 CV 与方向 |
| `is_buggy` / `exec_time` / `exit_code` | `null`，新代码尚待执行 |
| `hindsight.prompt_source` | 原始输入所在节点的 step 和 id |
| `hindsight.target_trajectory` / `donor_trajectory` | 目标轨迹和经验来源轨迹的节点引用 |
| `hindsight.metric_source` | 继承 CV 的来源终点 |
| `hindsight.generation` / `generation_model` | 重新作答的采样参数和模型 |
| `hindsight.hint_includes_code` | 是否附带来源终点代码 |

生成阶段的 metric 表示经验来源的质量。新程序的实测表现来自单独的执行对照。
每个新回答独自结束 episode；祖先链用于索引原搜索上下文。

## 3. 接入现有训练数据流程

从仓库根目录执行。下面的四步分别产生原数据、重写树、合成训练行和合并训练行。

```bash
conda activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"
RAW=data/augmented_mle_critic/raw_journal/wh/1112
TREE=data/augmented_mle_critic/raw_journal/wh/1112_hindsight
ORIGINAL=data/mle_policy/wh/1112/original
SYNTHETIC=data/mle_policy/wh/1112/synthetic
MERGED=data/mle_policy/wh/1112/merged
```

### 第一步：准备原数据与切分

```bash
bash src/mle_policy/scripts/data/build_all_batches_bigjournal.sh "$RAW" "$ORIGINAL"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$ORIGINAL"
bash src/mle_policy/scripts/data/assign_splits.sh "$ORIGINAL" run 0.1
bash src/mle_policy/scripts/data/to_grpo_metric.sh "$ORIGINAL"
```

已有中间数据和切分时从对应步骤继续。原始数据只有小 journal 时使用
`build_all_batches.sh`。需要按 CV 训练原数据时使用 `to_grpo_metric.sh`。

### 第二步：完成整批重写

模型、服务地址沿用每个输入 run 的目标 operator 的 `llm.client` 配置。
密钥从现有 `.env` 的 `PRIMARY_KEY_<MODEL>` 或 `PRIMARY_KEY` 读取；模型专用密钥优先，
`<MODEL>` 为 model_id 转大写并将 `-`、`.` 替换成 `_`。先启动对应服务，再运行：

```bash
bash src/mle_policy/scripts/data/hindsight/generate.sh \
  --input "$RAW" --output "$TREE" \
  --mode debug-improve --hint-code omit \
  --concurrency 16 --journal-workers 4
```

`--concurrency` 限制全部 journal 合计同时发出的模型请求数；
`--journal-workers` 限制同时处理的 journal 数。二者按服务吞吐和 allocation 调整。
每次运行从头生成，直接写入目标目录；请求重试沿用 dojo 的 LiteLLM backend，最终异常直接抛出。
控制台只打印完成的 journal 及输入、输出节点数量。

可选的离线格式检查只读两棵树，在终端打印结果：

```bash
bash src/mle_policy/scripts/data/hindsight/verify.sh \
  --input "$RAW" --output "$TREE" --mode debug-improve
```

### 第三步：单独计算合成数据的 advantage

```bash
bash src/mle_policy/scripts/data/build_all_batches_bigjournal.sh "$TREE" "$SYNTHETIC"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$SYNTHETIC"
bash src/mle_policy/scripts/data/hindsight/align_splits.sh \
  --original "$ORIGINAL/thinking" --hindsight "$SYNTHETIC/thinking"
bash src/mle_policy/scripts/data/to_grpo_metric.sh "$SYNTHETIC" thinking
bash src/mle_policy/scripts/data/hindsight/filter_positive.sh \
  --input "$SYNTHETIC/thinking/grpo.jsonl" --output "$SYNTHETIC/thinking/positive.jsonl"
```

合成数据按继承的 CV 单独组内比较，计算 advantage（组内相对奖励），然后保留
`advantage > 0` 的行。切分通过原数据的 group_id 对齐。单候选组和全同分组由共享
GRPO 流程跳过。thinking 之外的数据桶按同样步骤处理。

### 第四步：合并后进入训练

```bash
bash src/mle_policy/scripts/data/hindsight/merge.sh \
  --original "$ORIGINAL/thinking/grpo.jsonl" \
  --hindsight "$SYNTHETIC/thinking/positive.jsonl" \
  --output "$MERGED/thinking/grpo.jsonl"
```

输出沿用普通训练行格式和 split，后续走已有的长度过滤、训练格式转换和训练入口。
来源引用保留在重写树；需要追溯时用 sample_id 对照中间样本的 node id/step。

## 4. 少量人工检查

`experiment.py` 对指定案例共享一个 hint，分别生成纯文字经验和附代码两个版本。
每个版本只写 `metadata.json`、`trace.json`、`nodes.json`；完整操作及后续 GPU
执行见 `hindsight_eval.md`。这是独立的案例检查流程。
