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

## 输出格式

输出不再是把所有 Card 打平的 JSONL，而是一个 JSON 大字典：

```json
{
  "run_id_1__2026-07-28": [
    {"id": "task__root", "plan": "", "code": "", "label": null},
    {"id": "task__node_1", "plan": "...", "code": "...", "label": {}}
  ],
  "run_id_2__2026-07-29": [
    {"id": "task__root", "plan": "", "code": "", "label": null}
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
