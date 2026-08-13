# 学长 checkpoint 选择方向与 Qwen/K2 语料验收（2026-08-13）

## 裁决

本轮得到两个彼此独立的工程结论。

1. 学长分支 `dojo-reproduce@2cb6f0c57790407cae84070d3eb475da3cbe9597` 的最新
   Bradley–Terry 配置存在确定的 checkpoint 选择方向错误：
   `metric_for_best_model="eval_pair_accuracy"` 与 `greater_is_better=False` 同时出现，且
   `save_strategy="best"`。Transformers 4.49.0 的官方 `Trainer` 实现会在
   `greater_is_better=False` 时使用 `np.less`，所以更低的 validation pair accuracy 会被视为更优并
   触发保存。修复应为将 `greater_is_better` 改为 `True`，或把选择指标恢复为
   `eval_loss` 并保持 `False`；不能只看最终目录名判断保存的是最好 checkpoint。
2. 未进入 v11 的 Qwen Q01–Q08 与 K2a/K2b 共 40 个 manifest run 已按“物理完成”和“标签可用”
   两层门验收。36/40 具有 completed+exit0、非空 state/journal、唯一最终 search export 且三者节点数
   一致；其余 4 个失败/取消。36 个物理完整 run 中另有 7 个没有任何可用 finite 外部分，因此只有
   29 runs / 91 cards / 7 tasks 可进入有监督 exploratory 语料。

这两个结论都不能直接提升论文效果数字：前者是防止错误选模，后者只给 clean decision training 增加
1 个 b0 pair。它们的价值是避免把错误 checkpoint 或“有目录/有 checkpoint”误报成模型与数据收益。

## checkpoint 方向错误的边界

锁定事实：

- 最新配置：`save_strategy="best"`、`metric_for_best_model="eval_pair_accuracy"`、
  `greater_is_better=False`；
- 仓库 requirements 锁定 `transformers==4.49.0`；
- 官方 4.49.0 `Trainer._determine_best_metric` 固定为
  `np.greater if greater_is_better else np.less`，`save_strategy=BEST` 时只有该比较为真才保存；
- 远端可用环境 5.12.1 的实现语义相同，aira 环境为 4.50.1；这两项只是交叉检查，不替代仓库锁定版本。

必须保留的限制：0812 outcome 文档描述的是较早配置，当时记录为以 `eval_loss` 选模且
`greater_is_better=false`，该组合方向正确。因此不能事后声称此前约 0.55 的全部模型规模结果都被这个
新 bug 压低。只有从最新配置启动的 run 才受直接影响；判断具体 run 时必须检查其代码 commit、
`training_args`/`trainer_state` 与保存步，不能按日期猜。

## Qwen/K2 双门验收

源范围固定为 `gen2Q01`—`gen2Q08`、`gen2K2a`、`gen2K2b`。验收不读取任何
`env_variables.json`，只读取 pool manifest、checkpoint state/journal 与最终 search export。

### 物理完整性门

一个 run 只有同时满足以下条件才算物理完整：manifest status=`completed`、exit=0；journal/state
非空且可解析；恰有一个可解析的 `MCTS_search_data.json`；state current step、journal 行数和 search
node 数完全相等。

- 40 个计划 run 中 36 个通过；
- 4 个失败：Q03 Chaii seed 825、Q06 Chaii seed 831、Q08 Chaii seed 835、K2b Leaf seed 853；
- wall-time 后留下 20-step journal 或 state 不等于完成，全部按门排除。

### 有监督标签门

物理完整后还要求至少一个节点有 finite `score` 和完整 medal thresholds。7 个完整 run 零可用标签：
K2a Tweet seed 851、K2b Birds seeds 853/854、Q02 TPS-Dec seed 823、Q07 Spooky seed 834、
Q08 Nomad seed 835、Q08 Chaii seed 836。它们是有效的执行失败/无标签记录，但不能进入 critic
有监督训练。

最终 exploratory extension：

| 项目 | 数量 |
|---|---:|
| 可用 physical runs | 29 |
| cards | 91 |
| tasks | 7 |
| nonfinite quarantine | 0 |
| v11 ID 交集 | 0 |

其中最近的 Q06–Q08 + K2 批次为 17 个物理完整 run、11 个标签可用 run；Q01–Q05 补回 19 个物理
完整 run、18 个标签可用 run。这里的“补回”只表示此前不在 v11，不表示机制冻结后的前瞻数据。

## exploratory v12 与冻结边界

`cards_current_v11.jsonl` 保持不动。新扩展单独写为
`cards_extension_exploratory_v12.jsonl`；内部合并版只在集群 large-data 目录用于可重复构建，v11 的
16,012 行是逐字节前缀。结果为 16,103 cards / 696 runs；程序审计记录为 16,082 finite、21
quarantine。合并版 SHA256 为
`96983abcfc06c16d7b5f63db09aa70c6f5adce3be3d58b01144e73704447259d`，扩展 SHA256 为
`0210d3e45b43a5361f87296ea39b25f0bf6a85aa82c5cabb8296a5e83e78d35e`。

沿用 v11 hold universe 和原始冻结 hold，append-only decision 构建结果：

| budget | train 新增 | extension 新增 | frozen |
|---:|---:|---:|---:|
| b0 | 1 | 0 | 与 v11 逐字节相同（1,498） |
| b1 | 0 | 0 | 与 v11 逐字节相同（323） |
| b2 | 0 | 0 | 与 v11 逐字节相同（265） |

冻结节点进入训练为 0。由于新增 sibling decision 支持几乎为零，该扩展不能用来宣称 critic 获得更多
有效训练数据，也不值得据此立即重训。它主要暴露了“run/card 生产量”和“可用 sibling supervision”
之间的巨大落差，后续数据生产应同时报告二者。

## 复核

不 import 主 builder 的 verifier 从 40 个原始 manifest/run 独立重建接受集合、card IDs、run IDs、
prefix/suffix、decision append-only 与 frozen/train 隔离，输出：

```text
EXPLORATORY_V12_INDEPENDENT_VERIFY_PASS base_cards=16012 extension_cards=91 accepted_runs=29 rejected_runs=11 runs=29 tasks=7 new_pairs={"0": {"extension": 0, "train": 1}, "1": {"extension": 0, "train": 0}, "2": {"extension": 0, "train": 0}} frozen_train_overlap=0
```

第二次从 manifest 全量构建到新临时目录，extension、combined、run map、全部九份 decision JSONL 与
hold manifest 逐字节一致，输出 `EXPLORATORY_V12_DETERMINISTIC_REBUILD_PASS`。

## 下一步

- 将 checkpoint 方向问题告知学长，要求最新 run 修复后再解释容量趋势；旧 0812 结果保持原边界。
- 不因 91 cards 启动 RM 重训；它只新增 1 个 clean b0 decision pair。
- 近期方法实验继续执行最新裁决：先做 schema/probe-first artifact-contract smoke，验证候选特异 probe
  能否在单进程中早于完整模型生成、被 pristine grader 评分且不破坏最终路径；通过后才冻结 2×2 效果实验。
