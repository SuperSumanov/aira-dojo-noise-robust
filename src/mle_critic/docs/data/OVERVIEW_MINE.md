# 当前 augmented 数据流水线

本文只记录当前仓库实际使用的流程。主线数据是 data/augmented_mle_critic/，目标是从
AIRA-Dojo journal 生成 run-preserving Cards，再生成 value/reward pairs，过滤掉分差太小的
样本，最后按 frozen physical-run split 标记 train/test。

当前主线不再使用旧的扁平 Card JSONL、学生版 L1/L2 混合构建脚本，也不在 pair builder 内部
重新随机切 train/test。

## 1. 原始 journal 和 Card

每个 run 的输入结构是：

```text
<run_dir>/
├── dojo_config.json
├── env_variables.json
└── checkpoint/journal.jsonl
```

build_cards 只扫描小写的 checkpoint/journal.jsonl。每个 journal 节点都保留，包括根节点、
空代码、无 grade 和执行失败节点。Card 的主要输入字段是任务名、当前代码、计划、运行结果、
父子 lineage、外部 grade，以及以下 run 级采样信息：

| Card 字段 | 来源 |
| --- | --- |
| time_limit | dojo_config.json["solver"]["time_limit_secs"] |
| execution_timeout | dojo_config.json["solver"]["execution_timeout"] |
| client | dojo_config.json["solver"]["operators"]["draft"]["llm"]["client"]["model_id"] |
| hardware | env_variables.json["HARDWARE"] |

run key 是：

```text
dojo_config.json["id"] + "__" + date(dojo_config.json["metadata"]["launch_time"])
```

输出是 run-grouped JSON，而不是旧的扁平 JSONL：

```json
{
  "physical_run_id__2026-07-28": [
    {"id": "task__node", "task": {"name": "task"}, "code": "..."}
  ]
}
```

全量 Cards 的构建命令：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.build_cards \
  data/augmented_mle_critic/raw_journal \
  data/augmented_mle_critic/augmented_cards_next.json
```

也可以在这一步按整个 physical run 过滤；过滤发生在打开 journal 之前：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.build_cards \
  data/augmented_mle_critic/raw_journal \
  data/augmented_mle_critic/augmented_cards_next.json \
  --time-limit 70000 90000 \
  --execution-timeout 6000 8000 \
  --client deepseek-v4-flash \
  --date 2026-07-26 2026-07-30
```

成功后再替换 current 文件：

```bash
mv data/augmented_mle_critic/augmented_cards_next.json \
   data/augmented_mle_critic/augmented_cards_current.json
```

build_cards 会对配置缺失、非法 launch date、run key 冲突等情况直接报错，不静默覆盖旧
数据。save_cards()/load_cards() 和当前训练数据读取器都使用这种 grouped JSON 格式。

## 2. 按 batch 构建 Cards

全量 grouped Cards 作为训练数据底座；当前 augmented reward 主线把每个同超参数的
搜索树目录单独当作一个 batch。脚本：

```text
src/mle_critic/scripts/preprocess/build_batch_cards.sh
src/mle_critic/scripts/preprocess/build_batch_cards_all.sh
```

build_batch_cards.sh DIRECTORY 只遍历 DIRECTORY 的直接子目录，对每个子目录运行
src.preprocess.download_and_resolve.build_cards，并在该子目录写：

```text
<batch_dir>/batch_cards.json
```

批量处理当前 raw journal 日期目录：

```bash
bash src/mle_critic/scripts/preprocess/build_batch_cards_all.sh
```

这一步不是把 Card 打平，也不是删除无 grade 节点；它只是把同一 batch 的 run 单独保存，供
下一步在 batch 内计算 pair。

## 3. Value pair 构建流程概述

入口：

```text
src/mle_critic/src/preprocess/build_bt_pairs/build_subtree_pairs.py
```

对于节点 `n`，在 Cards 中沿 `parent_id -> children` 遍历完整可见子树。默认 value 是：

```text
V(n) = n 自己和所有可见后代中的最佳有限 graded score
```

higher-is-better 任务取最大值，lower-is-better 任务取最小值。`NaN` 和 `Inf` 被当作缺失
grade，不参与比较。当前 augmented corpus 中确实存在少量 `NaN` grade，因此不能直接把所有
非 null label 都送入 `min/max`。

一个节点只有在以下条件都满足时才能参加 value pair：

- 节点自己有有限 grade；
- budget 范围内至少有一个带有限 grade 的后代。

无 grade 节点仍保留在树中，也计入路径距离、累计 runtime 和子树展开量；它只是不贡献
grade。默认 `budget_steps=0`、`budget_secs=0` 表示使用完整子树。设置 budget 时，后代必须
同时满足最大边数和路径累计执行时间限制。

候选节点按任务分组，同一任务中所有 `V(n)` 不相等的节点都可以组成 pair，不要求同父，也
不要求来自同一个 run。每个任务随机打乱后最多保留 `--cap` 条。raw 输出中的
`intask_split` 固定为 `unassigned`，随后统一应用 frozen run split。

主要输出字段：

```json
{
  "task": "task-name",
  "better": "按 V(n) 判断更好的 Card ID",
  "worse": "按 V(n) 判断更差的 Card ID",
  "agrees_with_quality": false,
  "gap_raw": 0.12,
  "subtree_sizes": [12, 7],
  "steps_to_best": [3, 0],
  "intask_split": "unassigned",
  "src": "value"
}
```

`subtree_sizes` 和 `steps_to_best` 均严格按 `[better, worse]` 排列。
`agrees_with_quality` 比较的是节点当前 grade 排序与子树 value 排序；当前 grade 打平时为
`null`。

## 4. Decision pair 构建流程概述

入口：

```text
src/mle_critic/src/preprocess/build_bt_pairs/build_decision_pairs.py
```

一个 decision set 是同一父节点的全部直接孩子。只有至少有两个孩子时才可能生成 pair。
对于预算 `K`，先将某个孩子的全部后代按 journal `lineage.step` 排序，然后定义：

```text
V_K(child) = child 自己和最早 K 个可见后代中的最佳有限 graded score
```

这里 `K` 表示实际记录到的 descendant expansion 数量：

- `K=0` 只看 child 自己；
- 后代没有 grade 时仍消耗一次 expansion；
- 少于 K 个可见后代时，这个 child 在该 K 下的 value 未定义；
- child 和前 K 个后代全部没有有限 grade 时，value 也未定义。

在每个 decision set 和每个 K 下，对所有 value 已定义且不相等的 sibling 组合生成 pair。
指标方向直接来自 graded Card 的 `task.higher_is_better`，不再维护额外的
`task_orientation.json`。

Decision siblings 一定属于同一个 physical run，因此应用 run split 后不会出现跨界 pair；
但仍统一经过 `build_bt_pairs/apply_runsplit.py`，保证所有 pair 文件只信任同一份 frozen split。

主要输出字段：

```json
{
  "task": "task-name",
  "better": "better-child-id",
  "worse": "worse-child-id",
  "budget": 2,
  "parent": "parent-card-id",
  "set_size": 3,
  "gap_raw": 0.08,
  "intask_split": "unassigned",
  "src": "decision"
}
```


## 5. 构建 batch value/reward pairs

脚本：

```text
src/mle_critic/scripts/preprocess/build_batch_value_pairs.sh
```

运行：

```bash
bash src/mle_critic/scripts/preprocess/build_batch_value_pairs.sh \
  data/augmented_mle_critic/raw_journal
```

它递归查找所有 batch_cards.json，对每个文件运行：

```bash
python -m src.preprocess.build_bt_pairs.build_subtree_pairs \
  <batch_dir>/batch_value_pairs.jsonl \
  <batch_dir>/batch_cards.json \
  --cap 200 \
  --seed 7 \
  --budget-steps -1
```

--cap、--seed、--budget-steps 可以覆盖脚本默认值：

```bash
bash src/mle_critic/scripts/preprocess/build_batch_value_pairs.sh \
  data/augmented_mle_critic/raw_journal \
  --cap 200 --seed 7 --budget-steps -1
```

每个 batch 保留自己的 batch_value_pairs.jsonl，同时按路径排序把所有 batch 拼接成：

```text
data/augmented_mle_critic/raw_journal/batch_value_pairs.jsonl
```

当前 -1 是 wrapper 使用的 reward-pair 设置，实际只比较节点自己的 grade；如果需要完整可见
子树，应显式使用 --budget-steps 0。pair builder 的一般规则是按任务比较节点及其可达 graded 后代的最佳
grade，higher_is_better 决定取最大还是最小，NaN/Inf grade 不参与比较。输出中的
loto_fold 保存任务名，gap_raw 保存两个节点的 value 差，初始 intask_split 为 unassigned。

## 6. Gap filter

gap_filter.json 给每个任务一个最小可分辨 grade gap。过滤脚本按 pair 的 loto_fold 查表，
丢弃：

```text
gap_raw < task_minimum_gap
```

等于阈值的 pair 保留。命令：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.postprocess.gap_filter \
  --value-pairs data/augmented_mle_critic/raw_journal/batch_value_pairs.jsonl \
  --gap-filter data/augmented_mle_critic/gap_filter.json \
  --output data/augmented_mle_critic/raw_journal/batch_value_pairs_filtered.jsonl
```

脚本会校验每条记录的 loto_fold 和有限数值 gap_raw，缺少任务阈值时直接失败，不会默默
放行。输出仍是 JSONL，字段不改。

## 7. Frozen physical-run split

split 文件格式：

```json
{
  "hold": ["作为 test 的 physical run ID"],
  "all": ["已经分配过身份的全部 physical run ID"]
}
```

创建或增量更新 split：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.build_runsplit \
  data/augmented_mle_critic/augmented_cards_current.json \
  data/augmented_mle_critic/runsplit_holdruns.json \
  --seed 7
```

第一次运行按任务对当前 run 做约 80/20 holdout；之后只给不在 all 中的新 run 分配身份，旧
run 永不漂移。不要每天删除并重建这个文件，否则历史实验的 test 集会改变。

将 gap-filtered raw pairs 标成 train/test：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.build_bt_pairs.apply_runsplit \
  data/augmented_mle_critic/augmented_cards_current.json \
  data/augmented_mle_critic/runsplit_holdruns.json \
  data/augmented_mle_critic/raw_journal/batch_value_pairs_filtered.jsonl \
  data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl
```

只有两端都在非 hold run 的 pair 才标为 train，两端都在 hold run 的 pair 才标为 test；
跨边界 pair 丢弃。未知 Card、未分配 run、重复 Card ID 和非法 split 都直接报错。

## 8. 当前推荐的完整顺序

```text
raw journal
  -> augmented_cards_current.json             # 全量 run grouped Cards
  -> 每个 batch 的 batch_cards.json
  -> 每个 batch 的 batch_value_pairs.jsonl
  -> raw_journal/batch_value_pairs.jsonl       # 聚合
  -> raw_journal/batch_value_pairs_filtered.jsonl
  -> batch_value_pairs_filtered_runsplit.jsonl # train/test
  -> context length 检查
  -> augmented reward model / light predictor
```

完整命令可直接参考 tmp/reminder_train。增量更新时不要把新 pair 直接 append 到旧 raw
pair：新 Cards 可能改变祖先的 value，应该从当前 batch/cards 重建，再重新过滤和应用 split。

## 9. 训练前长度检查和轻量基线

训练前用 tokenizer 走 Bradley-Terry 的 CardEncoder -> PairDataset -> pair_collate 流程：

```bash
python -m src.mle_critic.src.postprocess.measure_context \
  --model Qwen/Qwen3-0.6B-Base \
  --pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
  --cards data/augmented_mle_critic/augmented_cards_current.json \
  --context-length 16384
```

它会报告 train/test 的平均 token 长度、最大长度和超出 context 的 sequence/pair 比例；测量
时暂时把 encoder max_len 设得很大，避免把自身截断当成真实统计。

不依赖大模型的对照基线：

```bash
PYTHONPATH=. python -m src.mle_critic.src.train.light_predictor.train \
  --pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
  --cards data/augmented_mle_critic/augmented_cards_current.json \
  --output tmp/light_predictor_results.json
```

它支持 tfidf_lr、static_lr、static_gbm 三个 sklearn pairwise predictor，并默认将 train/test
分别限制为 24,000/6,000 条。

## 10. 不再作为当前主线的内容

旧文档中关于学生版 L1/L2 混合数据、train_l2_budget.sh、rescue、旧 minimal_gap.json、
扁平 cards_current.jsonl 和在 pair builder 内随机切分的说明不适用于当前 augmented reward
流程，已从本文删除。相关旧代码即使仍在历史提交中，也不能当作当前数据产物或复现实验的入口。
