# policy SFT 到 E2E 评估（截至 10 月 9 日）

这份报告记这周 `src/mle_policy` 上的三件事：

1. **SFT 训练到端到端（E2E）评估的整条流水线跑通了**，第一次能拿训出来的 adapter 去跑
   MLEBench 的端到端评估。
2. **拿训出来的 adapter 在 8 个任务上跑了一批 E2E 对照**，和原模型、第一版数据对比。初步结论：
   第一版数据训出来的比原模型弱，第二版数据训出来的比原模型强。
3. **离线 GRPO 已经跑起来了**，E2E 评估流水线后面会继续用；但下一步的改进重点不在算法，
   而在"定什么目标、按这个目标造什么数据"。

---

## 1. 流水线跑通：SFT 训练 → 导出 adapter → 起 vLLM → E2E 评估

这周把四步串起来了，每一步的脚本都在仓库里：

| 步骤 | 干什么 |
| --- | --- |
| 造数据 | 把历史 dojo run 的 journal 按 prompt 分组，每组挑一条最好的 episode，导出成 verl 的 parquet |
| SFT | `Qwen/Qwen3.5-9B` + LoRA，64K 上下文，2 卡 PRO6000 |
| 导出 | FSDP 分片合并成 HF 目录，顺手写出 `lora_adapter/`；再剪掉 vision tower 的 LoRA（vLLM 不认） |
| 评估 | vLLM 上同时挂 base 和 adapter（同一端口两个 model id），adapter 用 `+_exp=mlebench/aira_mcts_qwen_minimal_lora` 关掉记忆跑 |

第一次跑通用的评估配置（`src/dojo/configs/_exp/mlebench/aira_mcts_qwen_minimal_lora.yaml`）是故意
贴近训练设置的：**no_memory**、**`reasoning_effort = minimal`**、solver 用 `mlebench/mcts`。

训练曲线在：

<https://forge.coreweave.com/wandb/zizhechen-the-chinese-university-of-hong-kong/verl-mle-policy/reports/sft---VmlldzoxODA4MjU2OQ?accessToken=tcvb8eauzborp84naethegugnj5tphvy93o6ui6o5zw9i8s0rt54xn79sfj2gtjf>

**一切正常**：训练正常收敛、没有 NaN、导出的 adapter 起 vLLM 能正常回答，E2E 也能跑完并打出
官方分数。

---

## 2. E2E 对照：原模型 vs 第一版数据 vs 第二版数据

### 2.1 四个 arm

所有 arm 的 solver 都是 `mlebench/mcts`、`num_children=2`、
`execution_timeout=7200`（单个解最多跑 2 小时）、`time_limit_secs=86400`（整个 run 最多 24 小时）。

| 目录名 | 生成模型 | 训练数据 | 步数 |
| --- | --- | --- | ---: |
| `mcts`| `Qwen/Qwen3.5-9B` **原模型**，不挂 adapter | — | 基线 |
| `v1-step250-lora` | 原模型 + 第一版 adapter | 第一版数据：**全部 provider** 的 run | 250 |
| `v2-step200-lora` | 原模型 + 第二版 adapter | 第二版数据：只留 glm / kimi / minimax / luna / ox-alpha / hy / mimo | 200 |
| `v2-step665-lora` | 原模型 + 第二版 adapter | 同第二版数据 | 665 |

几点说明：

- "第一版 / 第二版数据"的区别就是 **provider 有没有筛**。第一版把历史上所有 run（含
  OpenRouter 上的一些弱模型）都算进去了；第二版只保留上面那几个 provider
  （`data/mle_policy/dataset/non_thinking/manifest.json` 里的 `filters.client`）。换算成行数：
  第一版约 32k 行（train 32,059 / val 3,367），第二版约 19k 行（train 17,032 / val 2,015），
  一批 128 行，所以 250 步≈1 个 epoch，200 步≈1.5 个 epoch，665 步≈5 个 epoch。
- 每个任务跑的 arm 不齐（有的任务只跑了其中两三个），下面表里缺的就是没跑或没数据。

### 2.2 指标怎么算

MLEBench 每个节点跑完会拿到一个**官方分**，存在 `checkpoint/journal.jsonl` 的
`metric_info.score` 里；节点自己 n-fold CV（自己写的代码在自己划的验证集上打分）打出来的分是
`metric`（内部验证指标），solver 就是按 `metric` 挑节点提交的。表里三个口径：

- **`avg_selected_score`（主指标）**：每个 run 挑它内部指标最高的那个节点，报这个节点的官方分，
  再在 run 之间平均。
- **`max_score`**：所有 run 里见到过的最好官方分。看"有没有搜到过好东西"。
- **`avg_max_metric`**：每个 run 内部指标的最高值，再在 run 之间平均。它和 `avg_selected_score`
  是同一批节点上的两个数（同一个 run 的"最高内部指标"和"这个节点的官方分"），并排看就能看出
  内部指标和官方分差多远。

这三个都是 `src/dojo/analysis_utils/journal_to_fig.py` 的口径，取六条曲线的**最后一个点**
（和前几周的 E2E 报告同一口径）。RMSE / log loss 这类"越小越好"的任务已经取了负号，所以
**表里一律越大越好**。

### 2.3 主表

`run 数` 写成"有 checkpoint journal 的 run / 目录里的 run"。

| 任务（方向） | arm | run 数 | avg_selected_score | max_score | avg_max_metric |
| --- | --- | ---: | ---: | ---: | ---: |
| AI4Code（越大越好） | `mcts`（原模型） | 1/4 | 0.0634 | 0.0634 | 0.0270 |
| AI4Code | `v2-step200-lora` | 4/4 | **0.3977** | **0.4314** | 0.6625 |
| chaii（越大越好） | `mcts`（原模型） | 4/4 | 0.0296 | 0.0566 | 0.3844 |
| chaii | `v1-step250-lora` | 4/4 | 0.0215 | 0.0446 | 0.3987 |
| chaii | `v2-step200-lora` | 8/8 | **0.1328** | **0.5534** | 0.2089 |
| champs（RMSE，越小越好） | `mcts`（原模型） | 4/4 | **-1.7635** | **-1.2008** | 1.1375 |
| champs | `v2-step200-lora` | 4/4 | -2.8485 | -1.6200 | 0.7195 |
| champs | `v2-step665-lora` | 3/4 | -2.6156 | -1.5325 | 1.8081 |
| dog-breed（log loss，越小越好） | `mcts`（原模型） | 6/6 | -3.1775 | -0.6852 | -4.0681 |
| dog-breed | `v2-step200-lora` | 0/6 | — | — | — |
| dog-breed | `v2-step665-lora` | 5/8 | **-2.2767** | -0.7037 | -0.7621 |
| osic（越大越好，分是负的） | `mcts`（原模型） | 2/2 | — | -8.4721 | 9.6985 |
| osic | `v2-lora-step200` | 2/2 | — | **-6.8578** | -4.6765 |
| osic | `v2-lora-step665` | 2/2 | -7.6521 | -7.5610 | 821.5516 |
| random-acts-of-pizza（越大越好） | `no_lora`（原模型） | 4/4 | 0.5475 | 0.7686 | 1.0000 |
| random-acts-of-pizza | `v1-step250-lora` | 4/5 | 0.5810 | 0.7791 | 0.9376 |
| random-acts-of-pizza | `v2-step200-lora` | 7/8 | **0.6035** | **0.7863** | 0.8856 |
| spooky（log loss，越小越好） | `mcts`（原模型） | 6/6 | -0.6137 | -0.4187 | -0.4653 |
| spooky | `v2-step200-lora` | 6/6 | **-0.5055** | **-0.3100** | -0.5727 |
| tgs-salt（越大越好） | `mcts`（原模型） | 4/4 | 0.2881 | 0.4550 | 0.2641 |
| tgs-salt | `v1-step250-lora` | 7/7 | 0.0000 | 0.0529 | 0.2611 |
| tgs-salt | `v2-step200-lora` | 5/5 | 0.3481 | 0.5221 | 0.1981 |
| tgs-salt | `v2-step665-lora` | 8/8 | **0.5221** | **0.5221** | 0.6933 |

osic 三个 arm 最后交出去的提交都没跑通（官方分 `NaN`），按最差算 —— 并列垫底，这个任务这周
没有区分度。表里给的是 journal 里能读到的数（搜索过程中确实有节点评出过分数），但它们都没
转化成一次成功的提交。这是 9B 这种小模型的通病：代码稍复杂就出 bug。

### 2.4 结论

**1. 第二版数据比原模型强——6:1。**
除 osic（三个 arm 全 NaN，没有可比性）之外，有 v2 对照的 7 个任务里 v2 赢 6 个
（括号里是 `avg_selected_score`，"原模型 → v2"）：
AI4Code（0.0634 → 0.3977，step200）、chaii（0.0296 → 0.1328，step200）、
dog-breed（-3.1775 → -2.2767，step665；step200 没有 journal，算不了）、
pizza（0.5475 → 0.6035，step200）、spooky（-0.6137 → -0.5055，step200）、
tgs-salt（0.2881 → 0.5221，step665）。唯一输的是 **champs**：原模型 -1.7635，v2 的
step200 / step665 分别是 -2.8485 / -2.6156，明显更差。

**2. 第一版数据反而比原模型弱。**
跑过 v1 的三个任务里两个输给原模型：tgs-salt（0.0000 对 0.2881，差得最多）和 chaii
（0.0215 对 0.0296）。pizza 上 v1（0.5810）略高于原模型（0.5475），但差距在噪声量级里。
这和之前的判断一致——混了弱 provider 的第一版数据把模型带偏了。

**3. 两个口径方向一致，所以上面的排序不是挑口径挑出来的。**
`avg_selected_score` 和 `max_score` 在 7 个任务里 6 个给出同一个赢家，只有 dog-breed 是原模型在
`max_score` 上略高（-0.6852 对 v2 的 -0.7037）。`max_score` 只看每个臂最好的那一个 run，本来就
比 `avg_selected_score` 抖，这个不一致先放着。

**4. tgs-salt 上"步数越多越好"，但证据很薄。**
`v1` 0.0000 → `v2-step200` 0.3481 → `v2-step665` 0.5221，方向清楚；但 v1 和 step665 这两个
数各自只有 **1 个 run** 写出了官方分（见 2.5 第 1 条），所以只能说是一个待复核的信号。

### 2.5 这轮结果里必须一起看的坑

1. **arm 覆盖率差很多，很多格子只有 1–2 个 run 撑着。** 比如 tgs-salt 的 `mcts` 有 4 个 run，
   但只有 1 个节点写出了官方分，`avg_selected_score` 就是这 1 个 run 的数；AI4Code 的 `mcts`
   4 个 run 里只有 1 个写出了 journal。所以表里的数值当**方向**看，不要当精确数字看。
2. **osic 三个 arm 都交了挂掉的 submission。** 最后那份 submission 的官方分是 `NaN`，按最差
   并列，所以这个任务这周分不出 arm 的差别（原因见 2.3 下面那段）。
3. **原模型和 adapter 的 solver 配置不完全一样。** 原模型臂用 `simple_memory`（prompt 里带
   搜索记忆），adapter 臂用 `no_memory`。这是必然的——adapter 训练的时候就把"PREVIOUSLY
   EXPLORED ..."那段记忆删掉了，只能 no_memory 评估——但严格说这不是纯模型对比，原模型臂多了
   一份提示信息。想把这件事摘干净，得用 `no_memory` 把原模型臂重跑一遍。
4. **这套 SFT 设置本身有"背题"和"背高分 solution"的嫌疑。** 训练数据就是从这些竞赛的历史 run
   里捞出来的"某个任务上拿到高分的解 + 当时喂进去的 prompt"，评估用的任务就在里面出现过，
   所以 2.4 那些提升里有多少是真会做题、有多少是靠记住这个竞赛该交什么，现在分不开。不过这个
   方向仍然比之前那套 critic 设置强：critic 是让模型判断"两条 solution 哪条分数高"，连"把题目
   背下来"这一步都没走通（proxy 准确率一直卡在 0.65 上下，接进搜索也没优势）。至少现在换成了
   直接训 policy，"把任务和好解记住"这件事本身是有确定收益的。

### 2.6 一个附带的观察：原模型的内部指标刷得很高，官方分很低

每个节点都存两个分数：**内部指标**（`metric`，模型自己写的代码在自己划的 validation 集上跑出来
的分）和**官方分**（`metric_info.score`）。solver 是按内部指标挑节点的，所以内部指标"虚高"会
直接让搜索把好节点挑丢。这周看下来，**原模型（以及第一版数据的 adapter）经常把内部指标刷到
接近满分，但那个节点的官方分很低**：

| 任务 | arm | 内部指标最高值 | 该节点的官方分 | 这个 arm 见过的最好官方分 |
| --- | --- | ---: | ---: | ---: |
| chaii | `mcts`（原模型） | **1.0000** | 0.0336 | 0.0566 |
| chaii | `v1-step250-lora` | **1.0000** | 0.0000 | 0.0446 |
| chaii | `v2-step200-lora` | 0.9237 | 0.5408 | 0.5534 |
| spooky | `mcts`（原模型） | **-0.1872** | -0.7658 | -0.4187 |
| spooky | `v2-step200-lora` | -0.2036 | -0.5030 | -0.3100 |
| random-acts-of-pizza | `no_lora`（原模型） | 1.0000 | 0.5815 | 0.7686 |
| random-acts-of-pizza | `v2-step200-lora` | 1.0000 | 0.5000 | 0.7863 |

最好看的两个例子：

- **chaii**：原模型的内部指标直接刷到 **1.0000**（满分），但那个节点交出去只有 **0.0336** ——
  "自己觉得完美、官方分垫底"。换成第二版 adapter 后内部指标反而降到 0.92，官方分却是它的
  **16 倍**（0.5408，和它见过的最好值 0.5534 基本贴住）。
- **spooky**：原模型内部指标最高的那个节点官方分 **-0.7658**，比它自己见过的最好值
  **-0.4187** 差了 0.35。也就是说搜索按自建指标挑节点，把已经搜到的好东西挑丢了。

这条不是所有任务都成立（tgs-salt、dog-breed 上原模型的内部指标和官方分基本同步，champs 上三个
arm 的内部指标都虚高），所以先当一个"值得继续追"的现象：**原模型自己划的 validation 集和选解
这一步很不可靠**（大概率是它写的验证代码本身就有 bug / 泄漏），而训练数据筛干净之后，内部指标
和官方分明显对得更齐了。

---

## 3. 离线 GRPO 已经跑起来

离线 GRPO 的思路和实现：用同一批历史
搜索数据，只是给每条样本额外带上"它所属 episode 的组内相对 advantage"，训练时直接读这个数，
verl 里"采样 → 算 reward → 算 advantage"三步全部省掉（这些动作本来就是别的模型产出的，
在线采样拿不到）。

- **已经在跑了**：数据、训练脚本、离线 trainer 都通了（`Qwen/Qwen3.5-9B` + LoRA，和非 thinking
  的 SFT 用同一桶数据、同一套分词模板，好让两边口径一致）。
- 后续会继续接 E2E 评估流水线——每次改动都用第 2 节这套对照量一遍，而不是只看训练 loss。
- **但重点不在算法**。GRPO、sft 这些目标函数本身已经够用，现在卡住的是"什么算好动作、
  reward 怎么定、以及目标是什么，该造什么数据"。换句话说，先想清楚要模型学会什么，再决定
  用哪种训练方式去逼近它。
