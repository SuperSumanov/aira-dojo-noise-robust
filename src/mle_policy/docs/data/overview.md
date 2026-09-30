# 从 dojo journal 构建 policy 训练数据

代码在 `src/mle_policy/src/data/`，流程脚本在 `src/mle_policy/scripts/data/`，
默认把结果写到 `data/mle_policy/dataset/`。

拿这份数据去训练见另一篇：`src/mle_policy/docs/train/SFT_TRAINING.md`。

## 0. 这套东西要解决什么

这个仓库原来做的是 critic（看两条 solution 判断哪条分数高），那条线停了，改成
**直接训练 policy**，也就是训练 dojo 里真正写代码的那个模型。训练 policy 需要的是
"动作"数据：当时喂给模型的 prompt、模型输出了什么、这个输出最后拿到多少分。
历史实验里这些都存着，散在 1600 多个 `journal.jsonl` 里，而且没有按 prompt 归过类。

整条流水线分四步，每步一个程序：

```text
journal.jsonl
   │  1. build_batch_groups.py   按 episode 的 root 输入分组（batch = 一组实验）
   ▼
<out>/batches/<bucket>/<batch>/          每个 batch 一个中间件目录
   │  2. aggregate_groups.py     把 batch 归总成一份（不再产生新分组）
   ▼
<out>/<bucket>/{samples,groups,manifest}.jsonl
   │  3. assign_splits.py        归总之后再决定 train/val
   ▼
<out>/<bucket>/splits.jsonl
   │  4. to_sft.py / to_grpo.py
   ▼
<out>/<bucket>/{sft,grpo}.jsonl + parquet
```

`scripts/data/build_all_batches.sh` 负责第 1 步的循环和分桶。后面的归总、切分、
SFT、GRPO 各有独立脚本，可以从任意一步重新运行：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
OUT_ROOT=data/mle_policy/dataset
bash src/mle_policy/scripts/data/build_all_batches.sh data/augmented_mle_critic/raw_journal "$OUT_ROOT"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/assign_splits.sh "$OUT_ROOT" run 0.1
bash src/mle_policy/scripts/data/to_sft.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/to_grpo.sh "$OUT_ROOT"
```

除了批次构建，后五个脚本只读已有的上游结果。比如只改验证集划分，重新运行
`assign_splits.sh`，然后只运行需要更新的格式导出脚本；不用重新读 journal 或归总 batch。
`assign_splits.sh` 的参数是 `OUT_ROOT [SPLIT_BY] [VAL_FRACTION] [BUCKET]`，
`SPLIT_BY` 默认 `task`，`VAL_FRACTION` 默认 `0.1`。其他四个脚本是
`OUT_ROOT [BUCKET]`。`BUCKET` 可选，填 `thinking`、`non_thinking` 或 `other`
时只处理这一桶；不填就处理所有已有桶。归总之后如果重建了 batch，需重新归总、
切分，再导出受影响的格式。

## 1. 数据源：`journal.jsonl`

一个 run 的目录：

```text
<run_dir>/
├── dojo_config.json          # 任务名、模型、超时、算子配置
├── env_variables.json        # 含 HARDWARE
└── checkpoint/
    ├── journal.jsonl         # 搜索树每个节点一行（下面的流程只用这个）
    └── journal_for_unselected.jsonl   # 只有部分实验有，见第 10 节
```

节点字段：

| 字段 | 含义 |
| --- | --- |
| `step` | 这次搜索里的第几步 |
| `id` | 节点 id |
| `plan` / `code` | 模型写的方案 / 抠出来的可执行代码 |
| `metric` | **内部验证指标**，代码自己 5-fold CV 打出来的分 |
| `metric_info` | 官方评测结果，里面 `score` 才是**官方分数** |
| `is_buggy` | 这份代码没跑出有效提交 |
| `parents` / `children` | 树结构，**里面存的是 step 号，不是节点 id** |
| `operators_metrics` | 每一次 LLM 调用的原始记录 |
| `exit_code` / `term_out` | 退出码和标准输出 |

`operators_metrics` 和 `operators_used` 一一对应：`operators_used = ["debug", "analysis"]`
就表示这个节点先调了一次 `debug`、又调了一次 `analysis`，`operators_metrics[0]`
是 debug 那次的记录。每条记录里我们要的是：

| 键 | 含义 |
| --- | --- |
| `prompt_messages` | 那次调用实际发出去的完整 chat prompt |
| `completion_text` | 模型实际返回的文本 |
| `usage` | token 数、耗时 |

`prompt_messages` 有两种形态：自建模型是"一条短 system + 一条渲染好的 user"，
走 openai 协议的 API 只有"一条 system（里面就是整个渲染好的模板）"。
分组按 role + content 列表算哈希，先排序随机顺序的包列表，再从用于计算哈希的文本中
去掉 `# PREVIOUSLY EXPLORED IMPROVEMENT IDEAS` 到 `# DATA OVERVIEW` 之间的搜索记忆。
两种消息形态仍不会互相合并；`samples.jsonl` 保留原始 prompt。

### 1.1 三个踩过的坑

**`parents` / `children` 是 step 号。** 一开始按 id 去解析，结果所有 buggy 节点看起来
都没有子节点。实测 200 个 journal、8011 个节点：7811 个父引用全部能在 step 集合里找到，
没有一个能在 id 集合里找到；每个节点最多一个父节点，是一棵树。

**`is_buggy` 节点的官方分数是脏的。** 评测打的是工作目录里的 `submission.csv`，
节点挂掉、没写新提交时，打的是上一个节点留下的文件。实测：

| step | is_buggy | metric（内部 CV） | metric_info.score（官方） |
| ---: | :---: | ---: | ---: |
| 2 | True | None | 0.39416 |
| 3 | False | 0.34353 | 0.39416 |
| 5 | True | None | 0.31536 |
| 6 | False | 0.277815 | 0.32476 |

step 2 挂掉了，却记着和 step 3 一模一样的分数。所以官方分数只在 `is_buggy == False`
时才采信（代码里的 `node_score`），挂掉的节点 `node_score` 一律是 `null`。

**包列表顺序是随机的。** `draft` / `debug` / `improve` / `crossover` 渲染 prompt 之前都会
`random.shuffle(cfg.available_packages)`，所以同一个决策点两次调用拿到的 prompt 只差包列表顺序。
实测 120 个 journal、7018 次调用：逐字匹配只有 6 个多成员组，先把包列表排序再匹配有 132 个。
所以分组前做一次包列表排序（`--no-package-normalisation` 可关）。

## 2. debug 过程当成一个整体（episode）

这是这套数据和 critic 那套最重要的区别。

dojo 里一个候选解跑挂了，solver 会立刻开始 debug，所以**一个"提案"真正的结果往往在好几步之后才出现**。
实测：buggy 节点里 68.7% 最终能走到一个能跑的节点，debug 链长度 1～17 步。

因此每个节点有一个 **episode**：

> 从一个非 `debug` 的节点（`draft` / `improve` / `crossover`，下称提案）出发，
> 沿着它唯一的 `debug` 子节点往前走，直到走到第一个能跑的节点为止。

实测每个 buggy 节点最多只有一个 `debug` 子节点，所以这条链不用搜索，是直的。
链走不到能跑的节点（挂了没救回来）时，整个 episode 没有结果。

于是有三个 outcome 字段：

* **`node_score`**：节点自己的官方分数（挂掉就是 null）；
* **`episode_score`**：这个节点所在 debug 过程的结局分数；
* **`episode_reward`**：`episode_score` 归一化之后的 reward，**训练用的就是它**。

一个 episode 里所有节点共享同一个 `episode_reward`——这就是"以最后得到的可运行
solution 的 score 决定整个过程的好坏"，也就是 MDP 里的 return。
到转训练数据那一步（第 6 节）再把这个过程拆回一条条输入输出。

一个直接推论：**能跑的节点，`node_score` 和 `episode_score` 是同一个值**（它的 episode 就是它自己）。
两者只在挂掉的节点上不同。

## 3. batch：只在一组同环境的实验内分组

跨环境的问题是：不同实验的运行时间、超时、硬件、模型都不一样，prompt 看起来像但不是同一个问题。
所以先把实验切成 **batch**，分组只在 batch 内部做。

**batch 怎么划：run 目录的父目录。**

```text
raw_journal/0726/<issue>/<seed>/                                   -> batch = <issue>
raw_journal/comparison/<date>/<task>/<limit>/<model>/<solver>/<seed>/  -> batch = <solver>
```

这条规则对两种目录结构都成立，`build_all_batches.sh ... --print` 可以先把 batch 列出来看一眼。
所以 `BATCH_ROOT` 给到 `raw_journal` 就行。

除了 batch 隔离，分组 key 里还带了**环境指纹**（`env_signature`）：

```text
env_signature = hash(task, hardware, time_limit_secs, execution_timeout, num_children, clients)
group_id      = hash(batch, env_signature, prompt)
```

也就是一个 group = "同一批实验里、同一套环境下、root step 输入相同的所有 episode"。
一个 episode 是 group 的最小成员：episode 里的 draft、improve、debug、analysis 等 call
不会被拆到不同 group。
万一一个 batch 里混了不同环境（stage 1 的 manifest 会写 `environment_mixed: true` 并打警告），
分组也会自动把它们分开。

## 4. thinking 和 non-thinking 分开

数据里的事实：

| provider | 模型 | completion 长什么样 | run 数 |
| --- | --- | --- | ---: |
| `selfhosted` | `qwen3.8-27b` | 先一大段推理，再给方案和代码 | 184 |
| `openai` | deepseek / minimax / glm / gpt / kimi…… | 直接给方案和代码 | 1665 |

实测（抽 60 个 journal 的 draft 调用）：`selfhosted` 12/12 条在第一个代码块之前有超过
500 字符的推理前言；`openai` 只有 8/125 条是那样。

这两类 completion 不能混在一个训练文件里，所以**分桶放在 shell 里**
（`build_all_batches.sh`），不塞进 python 的数据逻辑：

```bash
THINKING_PROVIDERS=selfhosted NON_THINKING_PROVIDERS=openai   # 默认值，可覆盖
```

每个 batch 跑完 stage 1 之后，脚本读它 manifest 里的 `providers`，把整个 batch 目录挪到
`batches/thinking/` 或 `batches/non_thinking/`（都不是就进 `batches/other/`）。
后面的归总、切分、转格式**每个桶各跑一遍**，最后得到
`<out>/thinking/` 和 `<out>/non_thinking/` 两套互不相干的数据。

## 5. 中间件：一份 group 数据

stage 1 和 stage 2 产出同一个格式的"dataset 目录"（`groupdata.py` 定义）：

| 文件 | 内容 |
| --- | --- |
| `samples.jsonl` | 每一次 LLM 调用一行：prompt（原样）、completion、node 结果、episode 结果 |
| `groups.jsonl` | 每个 group 一行：`group_id`、`batch`、`task`、`size`、episode 成员摘要 |
| `manifest.json` | 配置、环境指纹、数量、直方图 |
| `splits.jsonl` | 第 3 步写的 `group_id -> train/val`（没跑切分就没有） |

`groups.jsonl` **故意不放 prompt**：prompt 占全部体积的 ~83%，而且组里任意一条成员的
prompt 做一次包排序就能得到。要看完整内容就看 `samples.jsonl`。

`samples.jsonl` 一行：

| 字段 | 说明 |
| --- | --- |
| `sample_id` | `blake2b(run_id, node_id, 调用序号)`，稳定且不依赖数据目录位置 |
| `group_id` / `prompt_key` | `group_id` 按 episode root 输入生成；`prompt_key` 是当前 call 的 prompt 哈希 |
| `prompt` / `completion` | 原样记录的那次输入输出 |
| `batch` / `env_signature` | 来自哪个 batch、哪套环境 |
| `task` / `run_id` / `run_dir` / `seed` | 归属信息 |
| `clients` / `providers` | 这批实验用的模型和 provider |
| `node_id` / `node_step` / `node_operator` / `operator` / `operator_index` | 节点和这次调用属于哪个算子 |
| `is_code_operator` | 是不是 draft/debug/improve/crossover |
| `prompt_tokens` / `completion_tokens` | 那次调用的 token 数，用来按长度过滤 |
| `node_has_result` / `node_is_buggy` / `exit_code` | 节点执行结果 |
| `node_score` / `node_reward` | 节点自己的官方分数和它的 reward（挂掉是 null） |
| `episode_id` / `episode_root_step` / `episode_terminal_step` / `steps_to_terminal` | episode 归属和结局位置；同一 episode 的所有 call 共用一个 `group_id` |
| `episode_score` / `episode_reward` | **训练用的 reward** |
| `is_lower_better` / `above_median` / `any_medal` | `metric_info` 里的原始字段 |
| `source_path` | 来自哪个 journal 文件 |

`groups.jsonl` 的成员是一整个 episode，包含 `root_sample_id` 和 `sample_ids`，以及 root
动作和 episode 的结果摘要。GRPO 按 `root_sample_id` 找到完整的 `sample_ids` 序列；SFT
和 GRPO 都不会把 episode 内的 debug/analysis call 当成独立候选。

## 6. 两种训练视角

两个程序各自读同一份中间件，各自写自己的输出。共同的选择逻辑在 `selection.py`：
成员按 `episode_reward` 排序，没走通的排在最后。

### 6.1 `to_sft.py`

每个 group 先挑 episode reward 最高的 episode，然后将整个episode内所有operation写成一系列
`[system, user, assistant]`。输出 `sft.jsonl` + `sft_{train,val}.parquet`
（只有一列 `messages`，可以直接喂 `src/verl` 的 `multiturn_sft_dataset`）。

**root step的system和user prompt改成该组内最早一步的system和user prompt** 我们将后续加入的
memory视作一种扰动，目的是为了让模型输出不一样的代码。而这里训练的目的是让模型一开始就找到更好的代码
所以将后续episode的root step的prompt改成group内最早的一步的prompt。

### 6.3 `to_grpo.py`

每个 group 一行，只出"组内至少两个 episode 走通"的组。公共 `prompt` 使用 group 内
最早 episode 的 root prompt；每个 `responses` 成员保存完整 episode：root completion
之后依次放入后续 operation 的 prompt 和 completion，按 episode reward 从高到低排列。
输出 `grpo.jsonl` + `grpo_{train,val}.parquet`。

**说清楚一件事：这不是 `src/verl` 现成的 GRPO 输入格式。** verl 的 `RLHFDataset` 只吃
prompt + 一个 reward function，回答是训练时在线 rollout 出来的；把已经采好的回答喂进去
得自己写 dataset 或者自己算 advantage。这个文件的价值是把"同一个 prompt 的一组回答 +
各自的 reward"这个结构先固定下来，在线/离线两边都能从这里取。

## 7. reward 怎么算

分数不能直接用：不同竞赛量纲差太远（AUC 0.9、RMSE 17、log loss 0.3），而且有些任务越低越好。
用竞赛自己的门槛归一化：

```text
reward = (score - median_threshold) / (gold_threshold - median_threshold)
```

两个门槛都来自 `metric_info`（MLEBench 自己算的 Kaggle 分位数）。
`0` = 公开榜中位数，`1` = 金牌线，负数 = 比中位数还差。分子分母同时乘一个符号，
越低越好的任务不用特判（这一点有单独的测试盯着）。

什么时候是 `null`：

* 节点没跑出结果（`node_reward`），或者 episode 没走通（`episode_reward`）；
* `metric_info` 里缺 `median_threshold` / `gold_threshold`；
* 两个门槛相等（分母是 0）。

原始分数没丢：`samples.jsonl` 里 `node_score` / `episode_score` 都在，
想换成按任务 z-score 或者别的归一化，下游重算就行，不用重跑流水线。

## 8. 切分（归总之后再切）

`assign_splits.py` 是独立一步，在归总之后跑，因为它是对**整个数据集**的决定，
不该让单个 batch 去定。切分单位由 `--split-by` 决定：

| `--split-by` | 含义 |
| --- | --- |
| `task`（默认） | 按竞赛切，val 是训练里完全没见过的竞赛 |
| `group` | 按 group 切，val 的 prompt 没见过但竞赛见过 |
| `run` | 按 run 目录切；注意跨 run 的 group 会被记在它第一个 run 那一边 |

实现是"按种子哈希排序，取最小的那一撮当 val"，不是"哈希小于阈值就算 val"——
后者在任务数少的时候会切出空 val（实测 22 个任务时一个都没落下，概率约 10%）。

## 9. 跑全量的实测数字

命令见开头的分步示例（`BATCH_ROOT=data/augmented_mle_critic/raw_journal`）。
以下是 2026-09-28 去掉搜索记忆后重跑的结果；旧版按完整 prompt 分组时，
`non_thinking` / `thinking` 分别有 116,364 / 6,925 个 group。

### 9.1 分桶结果

`build_all_batches.sh` 一共认出 **398 个 batch**，按 provider 分到两个桶：

| 桶 | journal | 样本（LLM 调用） | group | 环境数 | episode（走通的） |
| --- | ---: | ---: | ---: | ---: | ---: |
| `non_thinking` | 1504 | 120,434 | 12,519 | 395 | 29,617（25,792） |
| `thinking` | 156 | 7,451 | 677 | 22 | 1,557（1,556） |
| `other` | 0 | — | — | — | — |

（`raw_journal` 下带 `dojo_config.json` 的 run 目录一共 1838 个，其中 1660 个写了
`checkpoint/journal.jsonl`；剩下的是被 kill 之前没写出 checkpoint 的，按约定不读。）

### 9.2 三种视角

| 视角 | `non_thinking` | `thinking` |
| --- | ---: | ---: |
| `sft.jsonl`（每组一条） | 13,543（train 12,205 / val 1,338） | 751（train 693 / val 58） |
| `grpo.jsonl`（每组一行，组内 ≥2 条走通） | 10,612 组 / 25,900 条回复 | 669 组 / 1,571 条回复 |

单成员 group 共 44 个（`non_thinking` 44，`thinking` 0）；其余 13,152 个
都有至少两个 episode。GRPO 可用组由旧版的 758 个增至 11,281 个。这里同时用了
第 2 节的 episode 结局奖励和新的搜索记忆忽略规则。

### 9.3 时间和体积

* 本次输出约 **25 GB**：`batches/` 8.7 GB（每个 batch 一份）、两个桶的
  `samples.jsonl` 合计约 9 GB、`sft.jsonl`、Parquet 文件和其他文件若干。
  `samples.jsonl` 占大头是因为 prompt 被重复存了很多次
  （同一个竞赛的每个样本都带一份任务描述），实测 prompt 占全部字符的 ~83%
  —— 这也是 `groups.jsonl` 里不放 prompt 的原因。

## 10. 已知问题

1. **合并后的候选实际看到的搜索记忆不同。** `prompt_key` 忽略搜索记忆，
   但 `samples.jsonl` 和 SFT/GRPO 导出的 prompt 仍保留它。
3. **`journal_for_unselected.jsonl` 没有收。** 那是 ForeTS 被 critic 淘汰、根本没执行的候选，
   正好是"同一个 prompt 的多个回答"，而且一组候选的生成条件完全一致，对 GRPO 的价值可能
   比 `journal.jsonl` 还高。但它们的 `score` 一律为空，需要单独的 reward 设计。
   把 `--journal-glob` 改成 `**/journal_for_unselected.jsonl` 就能读进来。
4. **batch 划分是目录规则。** 同一个任务在不同日期、不同目录跑的实验会被当成不同 batch，
   即使环境一样也不会合并。这是有意的保守做法；想合并就把 `BATCH_ROOT` 往上提一层，
   但那样一个 batch 里会出现多种环境（仍然靠 `env_signature` 隔离，只是会影响分桶判断）。
5. **reward 是 episode 级的。** 一次 debug 让代码从跑不通变成跑得通，这个动作本身没有单独的
   reward，只有它所属 episode 的结局有；同一个 episode 里的每一步共享同一个 return。
