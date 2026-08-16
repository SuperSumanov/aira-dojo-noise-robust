# 我的 Card 数据格式

这套流程位于：

```text
src/mle_critic/src/preprocess/download_and_resolve/cards.py
src/mle_critic/src/preprocess/download_and_resolve/build_cards.py
```

它和学生旧流程最主要的区别是：在第一次从 journal 抽取 Card 时就保留物理 run
边界，并且不提前删除任何节点。后续是否按 grade、运行状态或代码是否为空筛选，应由具体的
训练数据构建脚本决定，而不是在原始 Card 抽取阶段决定。

## 输入目录

每个 AIRA-Dojo run 的核心文件结构是：

```text
<run_dir>/
├── dojo_config.json
├── env_variables.json
└── checkpoint/journal.jsonl
```

构建流程只读取小写的 `<run_dir>/checkpoint/journal.jsonl`。`json/JOURNAL.jsonl` 不作为
输入，即使它存在也会被忽略。找到 journal 后，从：

```text
journal_path.parent.parent / "dojo_config.json"
```

读取顶层 `id` 和 `metadata.launch_time`，并只保留 launch time 的日期部分，按以下格式组成
最终大字典的 run key：

```text
<id>__<YYYY-MM-DD>
```

例如 `metadata.launch_time="2026-07-28 14:32:05"` 时，key 使用 `2026-07-28`，不保留具体
时分秒。配置不存在、`id` 为空、launch time 缺失或日期格式非法，或者不同目录最终产生
相同组合 key 时，构建过程直接报错，避免静默丢失或混合数据。

任务名通常从 journal 的 `metric_info.competition_id` 读取。如果一个 run 的所有节点都没有
grade、因此 journal 中完全没有 competition ID，则回退到 `dojo_config.json["task"]["name"]`，
保证这种 run 也不会因为缺少评分记录而被跳过。

每个 run 还会读取以下采样和运行环境信息，并写入该 run 的每一张 Card：

| Card 字段 | 来源 |
| --- | --- |
| `time_limit` | `dojo_config.json["solver"]["time_limit_secs"]` |
| `execution_timeout` | `dojo_config.json["solver"]["execution_timeout"]` |
| `client` | `dojo_config.json["solver"]["operators"]["draft"]["llm"]["client"]["model_id"]` |
| `hardware` | `env_variables.json["HARDWARE"]` |

这里的 `client` 字段实际保存的是 draft LLM client 的 `model_id`。`env_variables.json` 和
`dojo_config.json` 位于同一个 `<run_dir>`。四个字段是当前 Card 格式的必需信息；构建时文件
不存在、字段缺失或类型非法都会直接报错，不会生成缺少采样条件的 Card。

## Journal 节点到 Card

journal 中每一行都生成一张 Card，包括：

- step 0 的根节点；
- `code` 为空的节点；
- 没有正式 grade 的节点；
- 执行失败的节点。

Card 保存以下主要信息：

```json
{
  "id": "spaceship-titanic__node_uuid",
  "task": {"name": "spaceship-titanic"},
  "time_limit": 7200,
  "execution_timeout": 1200,
  "client": "openai/gpt-5",
  "hardware": "slurm/a100",
  "plan": "候选方案的自然语言计划",
  "code": "候选方案代码",
  "obs": {
    "val_at_low": 0.80,
    "runtime_s": 120.0,
    "error": null,
    "stdout_tail": "..."
  },
  "lineage": {
    "parent_id": "spaceship-titanic__parent_uuid",
    "children_ids": [],
    "n_siblings": 0,
    "step": 3,
    "tree_depth": 2
  },
  "label": {
    "graded": 0.81,
    "y_norm": 0.62,
    "medal_bucket": "bronze"
  }
}
```

`plan` 和 `code` 都属于 critic 可以使用的语义信息。`metric_info.validation_score`（若存在）
进入 `obs.val_at_low`；正式外部 `metric_info.score` 进入 `label.graded`。只有 grade 和完整
medal thresholds 都存在时才会生成 `label.y_norm`。没有 grade 的 Card 仍然保留，此时
`label` 为 `null`；只有 grade 但不能归一化时，`label.y_norm` 为 `null`。

这四个 run 级字段也包含在 `Card.view()` 和 `Card.hidden()` 中，因此后续可以分析采样配置和
硬件对 Card 分布、执行结果及 critic 表现的影响。`Card.from_json()` 会直接读取这四个字段；
输入 JSON 缺少任意一个字段时直接报错，不兼容更早的不含这些字段的 Card 文件。

## 输出格式

输出不再是把所有 Card 打平的 JSONL，而是一个 JSON 大字典：

```json
{
  "run_id_1__2026-07-28": [
    {
      "id": "task__root",
      "time_limit": 7200,
      "execution_timeout": 1200,
      "client": "openai/gpt-5",
      "hardware": "slurm/a100",
      "label": null
    }
  ],
  "run_id_2__2026-07-29": [
    {
      "id": "task__root",
      "time_limit": 3600,
      "execution_timeout": 600,
      "client": "openai/gpt-4.1",
      "hardware": "slurm/h100",
      "label": null
    }
  ]
}
```

也就是：

```text
dojo_config.json["id"] + "__" + date(dojo_config.json["metadata"]["launch_time"])
    -> 该 run 按 journal 顺序排列的全部 Cards
```

构建命令：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.build_cards \
  RUNS_ROOT OUTPUT.json
```

写入和读取分别使用 `save_cards()` 与 `load_cards()`；两者都只处理当前的
`run_id -> list[Card]` JSON 大字典格式，不兼容旧的扁平 JSONL Card 文件。

构建结束时除总 Card 数和 run 数外，还会按 `competition_id` 排序输出每个 competition 的
Card 数和 run 数。`--tasks` 排除的 journal 不进入输出，也不进入这些统计。例如：

```text
[build_cards] 12000 cards from 100 runs -> OUTPUT.json
[build_cards] counts by competition_id:
[build_cards]   competition-a: 7000 cards from 60 runs
[build_cards]   competition-b: 5000 cards from 40 runs
```

## Bradley-Terry Pair 构建总览

新版 pair 流程全部位于：

```text
src/mle_critic/src/preprocess/build_bt_pairs/
├── build_subtree_pairs.py   # value pair：比较哪个节点最终通向更好的结果
├── build_decision_pairs.py  # decision pair：比较同一父节点下应该选择哪个孩子
├── pair_filters.py          # 两种 pair builder 共用的 run/Card 元数据过滤
└── build_runsplit.py        # 将 frozen physical-run split 应用到 raw pair
```

run split 的维护和 pair split 的应用是两个不同步骤：

```text
download_and_resolve/build_runsplit.py
    更新 runsplit_holdruns.json，只给新 run 分配 train/test 身份

build_bt_pairs/apply_runsplit.py
    读取已经冻结的 runsplit_holdruns.json，把 raw pair 标成 train/test
```

不要让各个 pair builder 自己重新随机切分。每日增加数据后，如果根据当前全量 run 重新抽
80/20，旧 run 的身份会漂移，历史 checkpoint 的 test set 也会随之变化。

## Frozen physical-run split

split 文件使用：

```json
{
  "hold": ["作为 test 的 physical run ID"],
  "all": ["已经分配过身份的全部 physical run ID"]
}
```

生成和更新入口是：

```text
src/mle_critic/src/preprocess/download_and_resolve/build_runsplit.py
```

规则如下：

1. split 文件不存在时，将当前 Cards 中的所有 run 按任务分组；
2. 每个任务内先按 run ID 排序，再使用固定 seed 打乱；
3. 打乱后最后约 20% 的 run 加入 `hold`，其余 run 是 train；
4. split 文件存在时，`all` 中的旧 run 保持原身份；
5. 只对当前 Cards 中不在 `all` 的新 run 重复上述按任务抽样；
6. 当前 corpus 暂时没有出现的历史 run 仍保留在 split 文件中。

这里的“约 20%”是针对本次需要分配的 run。比如某个任务当天只新增一个 run，当前切片规则
会把这个 run 放进 hold。这样做优先保证旧身份完全不变，而不是强行维持累计数据精确 80/20。

## Pair 构建前的采样条件过滤

`build_decision_pairs()` 和 `build_value_pairs()` 都接受以下五个可选参数：

```python
time_limit: tuple[int, int] | None = None
execution_timeout: tuple[int, int] | None = None
client: str | None = None
hardware: str | None = None
date: tuple[str, str] | None = None
```

过滤规则如下：

- `time_limit=(lower, upper)`：只保留 `lower <= card.time_limit <= upper` 的 Card；
- `execution_timeout=(lower, upper)`：同样使用包含上下界的整数范围；
- `client=substring`：只保留 `card.client` 中包含该字符串的 Card，不要求完全相等；
- `hardware=substring`：对子串做与 `client` 相同的匹配；
- `date=(start, end)`：从 run key 的 `__YYYY-MM-DD` 后缀读取日期，只保留包含起止日期的 run。

字符串匹配区分大小写。所有参数默认是 `None`，即不施加对应过滤。范围长度不为 2、下界大于
上界、日期不是 `YYYY-MM-DD`，或者启用日期过滤后遇到不符合 `<id>__YYYY-MM-DD` 格式的 run
key，都会直接报错。

过滤发生在建立 children index、遍历后代和计算 value 之前。因此被过滤掉的 Card 不仅不会
成为 pair 端点，也不会作为隐藏的后代继续影响保留节点的 lookahead/subtree value。当前这四
项 Card 元数据在一个 physical run 内通常相同，所以实际使用时多数情况会整批保留或排除一个
run；实现仍按 Card 字段逐张判断。

两种命令行入口使用相同参数：

```text
--time-limit MIN MAX
--execution-timeout MIN MAX
--client SUBSTRING
--hardware SUBSTRING
--date START END
```

`--date-range START END` 是 `--date` 的同义写法。

## Value pair

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

## Decision pair

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

## 应用 frozen split

`build_bt_pairs/apply_runsplit.py` 根据 grouped Cards 建立 `card_id -> run_id`，然后读取 frozen
split：

```text
两个端点都属于非 hold run -> train
两个端点都属于 hold run   -> test
一个 train、一个 test       -> 丢弃
```

以下情况直接报错，不会静默跳过：

- pair 引用了 Cards 中不存在的 ID；
- pair 所属 run 尚未写入 frozen split；
- split 中 `hold` 不是 `all` 的子集；
- Cards 中出现重复 Card ID。

因此每日构建时必须先更新 runsplit，再构建和切分 pair。

## 每日数据更新到新版 pair 的完整流程

下面假设原始数据长期保存在：

```text
data/augmented_mle_critic/raw_journal/
```

这个目录必须是累计目录，旧 run 不能每天删掉。`download_journals` 会跳过已存在文件，只下载
共享目录中新出现的文件。所谓“新数据融合旧数据”不是拼接两个 Card JSON，而是让旧、新 raw
run 同时保存在该目录，再从全部 raw run 重建一份完整 Cards JSON。

### 1. 增量同步并解压 journal

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.download_journals

PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.unzip \
  data/augmented_mle_critic/raw_journal
```

### 2. 从旧、新全部 run 重建完整 Cards

先写到临时目标，成功后再替换 current 文件，避免构建失败时破坏上一版：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.build_cards \
  data/augmented_mle_critic/raw_journal \
  data/augmented_mle_critic/augmented_cards_next.json

mv data/augmented_mle_critic/augmented_cards_next.json \
   data/augmented_mle_critic/augmented_cards_current.json
```

`build_cards` 会扫描所有小写 `checkpoint/journal.jsonl`。run key 冲突、配置缺失、同一 key
对应多个目录等情况会直接报错，不会用后来的数据静默覆盖旧数据。

### 3. 更新 frozen run split

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.build_runsplit \
  data/augmented_mle_critic/augmented_cards_current.json \
  data/augmented_mle_critic/runsplit_holdruns.json \
  --seed 7
```

第一次运行时 split 文件不存在，会从当前全量 run 建立。之后每天运行只分配新增 run。不要删除
或重新生成已有 `runsplit_holdruns.json`，除非明确决定废弃全部旧 checkpoint 的可比性。

### 4. 重建 raw value/decision pairs

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.build_bt_pairs.build_subtree_pairs \
  data/augmented_mle_critic/value_pairs_raw.jsonl \
  data/augmented_mle_critic/augmented_cards_current.json \
  --cap 20000 --seed 7

PYTHONPATH=src/mle_critic python \
  -m src.preprocess.build_bt_pairs.build_decision_pairs \
  data/augmented_mle_critic/decision_pairs_raw.jsonl \
  data/augmented_mle_critic/augmented_cards_current.json \
  --budgets 0,1,2
```

例如，只基于指定采样预算、模型、硬件和日期窗口构建 pair：

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.build_bt_pairs.build_subtree_pairs \
  data/augmented_mle_critic/value_pairs_filtered.jsonl \
  data/augmented_mle_critic/augmented_cards_current.json \
  --cap 20000 --seed 7 \
  --time-limit 3600 7200 \
  --execution-timeout 600 1200 \
  --client gpt-5 \
  --hardware a100 \
  --date 2026-01-01 2026-06-30
```

每日应该从当前完整 Cards 重建 raw pair，而不是把当天 pair 直接追加到旧 pair 文件。原因是新
后代会改变祖先的 value，新 sibling 也会改变 decision set；简单 append 会保留过时标签。

### 5. 应用同一份 frozen run split

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.build_bt_pairs.apply_runsplit \
  data/augmented_mle_critic/augmented_cards_current.json \
  data/augmented_mle_critic/runsplit_holdruns.json \
  data/augmented_mle_critic/value_pairs_raw.jsonl \
  data/augmented_mle_critic/value_pairs_runsplit.jsonl

PYTHONPATH=src/mle_critic python \
  -m src.preprocess.build_bt_pairs.apply_runsplit \
  data/augmented_mle_critic/augmented_cards_current.json \
  data/augmented_mle_critic/runsplit_holdruns.json \
  data/augmented_mle_critic/decision_pairs_raw.jsonl \
  data/augmented_mle_critic/decision_pairs_runsplit.jsonl
```

也可以在 Cards 已更新后运行：

```bash
bash src/mle_critic/scripts/build_lookahead_datasets.sh
bash src/mle_critic/scripts/build_decision_datasets.sh
```

两个脚本都会先幂等地更新同一份 runsplit，再构建各自 pair。

### 6. 当前 corpus 的一次验证快照

以下数字来自 2026-08-14 的 `augmented_cards_current.json`，只用于检查流水线量级，后续每日
更新后自然会变化：

| 数据 | raw | train | test | 跨 split 丢弃 |
| --- | ---: | ---: | ---: | ---: |
| value pairs，cap=20,000/task | 316,097 | 206,722 | 15,470 | 93,905 |
| decision pairs，K=0,1,2 | 10,518 | 8,796 | 1,722 | 0 |

当时 Cards 包含 465 个 physical runs，frozen split 中 103 个为 hold。Decision raw pair 按
预算分别为 K=0：5,255，K=1：2,763，K=2：2,500。

需要复现某个已经开始的实验时，至少应保留对应版本的 Cards、runsplit 和最终 pair 文件。
run split 身份虽然冻结，但 raw pair 会随后代增加、pair cap 抽样池变化而变化。
