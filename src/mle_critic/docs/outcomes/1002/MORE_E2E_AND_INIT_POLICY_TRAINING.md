# E2E 对比补充 + policy 训练起步（截至 10 月 2 日）

## 这份报告补什么

承接 `0925/AGENTIC_AND_E2E.md`，只记两件事：

1. **端到端（E2E）对比扩了一批数据**：多跑 3 个任务的完整四臂对照（`google-quest` /
   `petfinder` / `tweet`，都在 `qwen-medium` 这一档思考预算下），并新增两条**故意不做任何
   智能判断**的基线 `random` 和 `short`，用来回答"critic 到底比乱选强多少"。
2. **policy（就是 dojo 里真正写代码那个模型）训练起步**：数据流水线初步跑通，SFT 训练脚本
   改成了 LoRA + fused kernel 跑 64K 上下文，刚跑通第一版，为了压榨硬件踩了大量的坑。

---

## 1. E2E 对比：补 3 个任务 + 2 条"傻基线"

### 1.1 新增了什么

`0925` 的对照里只有 `mcts` / `forets` / `forets-selected` 三种选节点的策略，缺一个"不做选择、
纯碰运气"的参照物。这周补齐了，定义如下（前三行和 `0925` 完全一致）：

| arm | 每个节点生成几个候选 | 用什么给候选排序 | 排序后保留几个 | 实际执行几个 |
| --- | ---: | --- | ---: | --- |
| `mcts` | 2 | 内部验证指标 + UCT 搜索 | — | 2 |
| `forets` | 6 | 全量 68 任务数据训出来的 critic | top-3 | 从 top-3 里随机抽 2 |
| `forets-selected` | 6 | 10 个任务的数据训出来的 critic | top-3 | 从 top-3 里随机抽 2 |
| `random` | 6 | **随机数**（`random.random()`） | top-3 | 从 top-3 里随机抽 2 |
| `short` | 6 | **负的代码长度**（`-len(code)/1000`） | top-3 | 从 top-3 里随机抽 2 |

实现就在一个函数里，三种"critic"只是换了个打分函数：
`src/dojo/solvers/fore_ts/fore_ts.py:122`。

两个细节，避免误读：

- `random` 的效果约等于"从 6 个候选里等概率抽 2 个执行"（先随机排 top-3，再抽 2 个，
  每个候选被选中的概率是 2/6）。所以它衡量的是**完全不要 critic 时的期望水平**。
- `short` 不是"选最短的"，而是"偏好短的"：先留最短的 3 个，再随机抽 2 个，仍然带随机性。

新增三个任务的目录（全部是 `qwen-medium`，和 `0918` 里同一任务的 `qwen`/xhigh 不能直接配对）：

```
data/augmented_mle_critic/raw_journal/comparison/0930/google-quest-challenge/7200/qwen-medium/
data/augmented_mle_critic/raw_journal/comparison/0930/petfinder-pawpularity-score/7200/qwen-medium/
data/augmented_mle_critic/raw_journal/comparison/0930/tweet-sentiment-extraction/7200/qwen-medium/
```

`0930/spooky-author-identification` 里**只有 `random` / `short` 两条新基线**，是对
`0918/spooky-author-identification/7200/qwen-medium` 的补充，第 1.4 节单独看。

代价数字没有变：`execution_timeout = 7200`，`time_limit_secs = 86400`。

### 1.2 主表

口径和 `0925` 完全一致：用 `src/dojo/analysis_utils/journal_to_fig.py` 聚合每个 run 的
`checkpoint/journal.jsonl`，取 7200s 处的点；`run 数`写成"有 journal 的 run / 目录里的 run"。
分数一律按"越大越好"归一过（RMSE / log loss 取了负号），所以 petfinder 和 spooky 那几行是负数，
越接近 0 越好。**主指标是 `avg_selected_score`**：按内部验证指标挑出来的提交节点（也就是 solver
真的会交出去的那个解）的官方分数，再在 run 之间平均。

| 任务 | 预算 | arm | run 数 | avg_selected_score | avg_max_score | max_score |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| google-quest（越大越好） | qwen-medium | `forets-selected` | 3/3 | **0.4075** | 0.4075 | 0.4138 |
| google-quest | qwen-medium | `short` | 4/4 | 0.4074 | **0.4087** | 0.4155 |
| google-quest | qwen-medium | `random` | 4/4 | 0.3972 | 0.4023 | 0.4099 |
| google-quest | qwen-medium | `mcts` | 4/4 | 0.3203 | 0.4200 | **0.4371** |
| petfinder（RMSE，越小越好） | qwen-medium | `random` | 4/7 | **-17.2203** | **-17.2203** | **-17.0252** |
| petfinder | qwen-medium | `short` | 6/6 | -17.3886 | -17.3454 | -17.0306 |
| petfinder | qwen-medium | `mcts` | 6/6 | -18.0041 | -17.5226 | -17.0447 |
| petfinder | qwen-medium | `forets-selected` | 2/5 | -18.0709 | -18.0709 | -17.6177 |
| tweet（越大越好） | qwen-medium | `short` | 5/6 | **0.6830** | **0.6897** | **0.7104** |
| tweet | qwen-medium | `forets-selected` | 4/5 | 0.6776 | 0.6778 | 0.7037 |
| tweet | qwen-medium | `random` | 5/7 | 0.6501 | 0.6812 | 0.7069 |
| tweet | qwen-medium | `mcts` | **0/8** | — | — | — |

三个任务的结论：

1. **`short` / `random` 这两条完全不做判断的基线，在 3 个新任务里都打平或打赢了 critic 臂。**
   这是比 `0925` 更干脆的负面信号：`0925` 是"critic 臂和 mcts 互有胜负"，这周是"critic 臂还不如
   按代码长度排"。
2. **petfinder 上 `random` 是全场最好。** `random` 的 `avg_selected_score` 是 -17.22，比
   `mcts`(-18.00) 和 `forets-selected`(-18.07) 都好；而且 `avg_max_score` 也更好，不是被单个 run
   带跑的，是整体就更好。
3. **google-quest 上 `mcts` 是"见过的最好、交出去的最差"的典型。** 它的 `max_score` 0.4371 是
   四个臂里最高的，`max_metric`（内部指标最好值）0.4172 也很高，但 `avg_selected_score` 只有
   0.3203，差 `short`/`forets-selected` 近 0.09。还是老问题：内部验证指标和官方分数错位，
   挑节点这步把好节点挑丢了。
4. **`tweet` 的 `mcts` 整臂是空的**：8 个 run 目录一个 `checkpoint/` 都没写出来，直接被 kill，
   这一格现在没有数据。所以 tweet 上"mcts 到底行不行"这周没有结论。

### 1.3 spooky 的补充对照

`0930` 只给 spooky 补了 `random` / `short`，和 `0918` 的 `mcts` / `forets` 拼起来看
（同任务、同 `qwen-medium`、同超时）：

| arm | 来源 | run 数 | avg_selected_score | avg_max_score | max_score |
| --- | --- | ---: | ---: | ---: | ---: |
| `mcts` | 0918 | 6/6 | **-0.2706** | **-0.2641** | **-0.2232** |
| `forets` | 0918 | 7/8 | -0.3177 | -0.3165 | -0.2639 |
| `random` | 0930 | 5/6 | -0.3759 | -0.3759 | -0.3204 |
| `short` | 0930 | 6/6 | -0.3998 | -0.3979 | -0.3235 |

**spooky 是这轮唯一一个 critic 臂明确赢过傻基线的任务**，而且三个指标方向一致（不是只赢一个）。
但要注意两点：一是 `mcts` / `forets` 是 9 月 18 日跑的，`random` / `short` 是 9 月 30 日跑的，
中间生成模型的 serving 有没有换过不确定；二是 spooky 本身是 log loss 任务，几个数都挤在
-0.27 到 -0.40 之间，绝对差距不大。所以这里更像"值得复核的信号"，而不是定论。

### 1.4 这轮结果里必须一起看的坑

1. **run 流失仍然不齐。** petfinder 的 `forets-selected` 只有 2/5 个 run 写出 journal，`random`
   是 4/7；tweet 的 `mcts` 是 0/8。没写 journal 的 run 大多是没跑完就被 kill，直接丢掉，
   哪个臂丢的正好是差的 run，均分就会虚高或虚低。
2. **每臂实际执行节点数差很多**（journal 行数）：petfinder 的 `forets-selected` 两个 run 各只有
   10、8 个节点，`short` 里有一个 run 只执行了 4 个节点；而 tweet 的 `forets-selected` 是
   45/42/26/47。执行得少的 run 本来就没多少东西可比，混在同一份平均里会放大噪声。
3. **`avg_selected_score` 依然会被单个 run 带跑。** google-quest 的 `mcts` 就是例子
   （`max_score` 最高、`avg_selected` 最低）。这是 `0918`、`0925` 已经反复出现的问题。

---

## 2. policy 训练的数据流水线（初步实现）

这一节讲 `src/mle_policy`：把历史 dojo 实验里"模型当时看到什么 prompt、输出什么、最后拿了
多少分"整理成能直接训 policy 的数据。文档在 `src/mle_policy/docs/data/overview.md`。

### 2.1 整条流水线分四步

```text
data/augmented_mle_critic/raw_journal/**/journal.jsonl   （1600+ 个 run 的历史记录）
   │  1. build_batch_groups.py     按"实验批次"把 run 分桶，再按 root prompt 分组
   ▼  data/mle_policy/dataset/batches/<bucket>/<batch>/
   │  2. aggregate_groups.py       把每个 batch 归总，不再产生新分组
   ▼  data/mle_policy/dataset/<bucket>/{samples,groups,manifest}.jsonl
   │  3. assign_splits.py          归总之后统一决定 train/val
   ▼  data/mle_policy/dataset/<bucket>/splits.jsonl
   │  4. to_sft.py / to_grpo.py    导出两种训练视角
   ▼  data/mle_policy/dataset/<bucket>/{sft,grpo}.jsonl + parquet
```

脚本都在 `src/mle_policy/scripts/data/`，每一步都能单独重跑（比如只改验证集划分，就只需重跑
第 3、4 步，不用重读 journal）。

### 2.2 几个必须先解释的概念

- **batch（批次）**：直接按 run 目录的父目录切，目的是把不同环境（不同硬件、超时、模型）的
  实验隔开，分组只在 batch 内部做。同一任务在不同日期/目录跑的会被当成不同 batch，这是有意
  的保守做法。
- **group（组）**：一个组 = "同一批实验里、同一套环境下、root step 输入相同的所有回答"。
  分组 key 是 `hash(batch, env_signature, prompt)`。它是后面 rejection sampling / GRPO 的基本单位。
- **episode**：dojo 里一个候选解跑挂了，solver 会马上开始 debug，所以"一个提案真正的好坏"
  往往要好几步之后才知道（实测 68.7% 的挂掉节点最终能救回来，debug 链长 1～17 步）。
  于是定义：**从一个提案节点出发，沿它唯一的 debug 子节点一路走到第一个能跑的节点，这一整条链
  算一个 episode**。
- **reward**：用每个竞赛自己的"MLEBench 中位数线/金牌线"归一化
  `reward = (score - median) / (gold - median)`，这样 AUC、RMSE、log loss 放在一起可比，
  越低越好的任务也不用特判。**reward 是 episode 级的**：一个 episode 里所有节点（包括中间的
  debug、analysis）共享同一个结局 reward。

### 2.3 目前跑出来的规模

2026-09-28 跑的一版（按 provider 分两个桶，永远不混）：

| 桶 | journal 数 | LLM 调用（样本） | group 数 | episode（走通的） |
| --- | ---: | ---: | ---: | ---: |
| `non_thinking` | 1504 | 120,434 | 12,519 | 29,617（25,792） |
| `thinking` | 156 | 7,451 | 677 | 1,557（1,556） |

导出结果：`non_thinking` 的 `sft.jsonl` 是 35,433 行（train 32,066 / val 3,367），`grpo.jsonl`
是 10,612 组；`thinking` 对应 2,897 / 669 组。整份输出约 25 GB，`samples.jsonl` 占大头（同一个
任务的 prompt 在每个样本里重复存了一份）。

### 2.4 需要注意的地方

1. **`to_sft.py` 做了三件改变训练分布的事，必须心里有数：**
   - 每个 group **只留 reward 最高的那一条 episode**（rejection sampling），所以数据里全是
     "好结局"，没有失败样本；
   - 把 group 内 root step 的 system/user prompt **统一换成该组最早一步的 prompt**——理由是
     后续加进去的 memory 只是扰动，训练目标是让模型一开始就找到更好的代码；
   - `draft`/`improve`/`crossover` 的 prompt 里 **"PREVIOUSLY EXPLORED ..." 那段搜索记忆被删掉**，
     想把这部分选择直接训进参数；`debug`/`analysis` 带的是代码和报错，不动。
2. **reward 只有 episode 级，没有 step 级。** "一次 debug 把代码从跑不通改到跑通"这个动作本身
   没有单独的奖励，它和同 episode 的其他步共享同一个 return。想做 credit assignment 得自己再拆。
3. **GRPO 的输出不是 verl 现成的输入格式。** `grpo.jsonl` 固定了"同 prompt 一组回答 + 各自 reward"
   的结构，但 verl 的 `RLHFDataset` 要的是 prompt + reward function、回答在线 rollout，接进去
   还得自己写 dataset 或自己算 advantage。

---

## 3. policy SFT：H200 没了之后，LoRA + fused kernel 跑 64K

### 3.1 现在的设置

H200 节点没了，换到 PRO 6000 机器和学校集群的H200机器，2-4 卡跑。为了在 64K 上下文下还能有
像样的速度，`src/verl/my_scripts/train/mle_policy/` 下的脚本普遍改成：

| 项 | 值 | 说明 |
| --- | --- | --- |
| 模型 | `Qwen/Qwen3.5-9B` | 另一份 `4xh200` 脚本是 `Qwen/Qwen3.8-27B` |
| 数据 | `non_thinking` 桶，`--max-length 65536` | train 32,059 / val 3,367，只丢 7 条超长 |
| 精度/并行 | bf16 + FSDP2，2 卡 | `engine.fsdp_size=1`，序列并行关 |
| LoRA | rank 64 / alpha 128 / `target_modules=all-linear` | 为了省显存和算力 |
| fused kernel | `model.use_fused_kernels=True`，`impl_backend=triton`，另开 Liger | 降cross entropy loss时的峰值显存 |
| batch | 全局 128，micro 1，dynamic bsz，`max_token_len_per_gpu=80000` | |
| 优化 | lr 1e-5，cosine，20% warmup，clip 1.0，2 epoch | 每 epoch 250 步，共 500 步 |

把我们过去两个月采的数据完整训两遍只需要两天。

---

## 4. 结论和下一步

1. **critic 这条路的负面证据更硬了**：新增的 `random` / `short` 两条傻基线，在 3 个新任务上
   都不输给 critic 臂；petfinder 上 `random` 直接是最好。加上 `0925` 的结论，这个方向可以正式收口。
2. **spooky 是唯一反例**，值得用一批新 run 复核一次（最好和 `random`/`short` 同源、同日期跑），
   确认不是服务端/时间差异。
3. **policy 数据流水线已经能出数据**，但 `journal_for_unselected.jsonl` 没收、GRPO 还没有原生
   dataset，这两块是下一批要补的。SFT 的操作符配比也要重新讨论。
4. **SFT 的 训练已经正常**，接下来等 lr warmup 走完看 loss 走向；训完后上e2e评估。
