# Agentic RL、少量任务 critic 与 E2E 对照（截至 9 月 25 日）

## 这版报告回答什么

这份报告承接 0918 版，记录三件事：

1. **agentic RL 对单轮 RL**。结论和曲线都在 wandb 报告里，这里只放一句话版；
2. **呼应 0918 的下一步：用少量任务训 critic**。在 10 个任务、8331 条 pair 上反复调参，最好的
   BT（Bradley–Terry，就是让模型判断"两条 submission 哪条分数更高"的那个判别模型）只到
   **0.6539**，14B 在同一份验证集上是 0.6490，没有规模优势；
3. **一批端到端对照**：`qwen`（xhigh 思考预算）对 `qwen-medium`（medium），`mcts` 对 `forets` 对
   `forets-selected`，以及 `qwen-medium` 下"加 critic"对"不加 critic"。

三节的结论都是负面的：agentic RL 训到一半就掉下去；少量任务没有把 critic 的准确率抬起来；
critic 接进搜索流程之后同样没有稳定优势。

### 结果的定位

- 第 2 节的准确率是 **proxy 指标**：给同一个任务、同一次实验里的两条 submission，模型能不能挑出
  实际分数更高的那条。它只说明数据里有可学信号，不说明 critic 有用。
- 第 3 节是端到端结果，口径和 0918 一致：用 `src/dojo/analysis_utils/journal_to_fig.py` 从每个
  run 的 `checkpoint/journal.jsonl` 聚合。`max_score` 是这次搜索见到过的最好官方分数；
  `avg_selected_score` 是"按内部验证指标挑出来的那个节点（也就是 solver 停下时会提交的节点）的
  官方分数，再在 run 之间求平均"。后者才是判断 critic 有没有用的主指标——`max_score` 只看运气
  最好的那一次，`avg_selected_score` 看的是每个 run 真的会交出去什么。
- 下表里的分数都按"越大越好"的方向归一过了（官方指标是 log loss / RMSE 的任务取了负号），所以
  petfinder、spooky、dog-breed 那几行是负数，越接近 0 越好。

## 1. Agentic RL：初步看来一般

完整报告（含曲线和 trace 例子）：
<https://wandb.ai/zizhechen-the-chinese-university-of-hong-kong/mle-critic-verl/reports/Agentic-RL---VmlldzoxODAwNDI3MQ>

设置：用 H200 节点上的底层 syscall 搭了一个单核、无内存限制、无网络、看不到 GPU 的沙盒，只给
`bash` / `view` / `edit` 三个工具；数据就是第 2 节那份 10 任务的 pairwise 数据。为了保证约
1 小时/step，batch size 压到 256，每个 batch 拆成 4 个 minibatch 做 4 次梯度更新。作为对照，
同一份数据又跑了一次单轮 RL（batch 512）。

三条结论：

1. **agentic RL 第 20 步到 0.61 验证准确率之后一路跌到 0.5 以下**，40 步附近看着像训崩了，但
   ppo_kl、clipfrac、entropy 这些指标都还在正常范围。单轮 RL 则是平稳升到 0.7，后面因为没卡
   被打断。
2. **行为上模型基本在debug**。大多数情况下模型都在写测试代码验证solution中可能的bug。
3. 单轮 RL 训完以后回答风格从"比较长的分析"变成"短的枚举"，response length 也在下降，但回答准确率却在持续提高。

所以目前的假设是：**MLE 任务里真正有用的 feedback 是任务执行完的结果；SWE 式的代码调试
feedback 不太值钱，而且把调试放进 policy 之后还会被进一步稀释。**

## 2. 少量任务训 critic（呼应 0918 的计划）

0918 提的计划是：从 68 个任务里挑 8–10 个，每个任务采到 300–400 条 pair，训一个 BT，看准确率
能不能从 0.58 左右回到 0.60+。

这版数据（`data/augmented_mle_critic/batch_value_pairs_selected_filtered_runsplit.jsonl`）就是
照着这个挑的：**10 个任务、9644 条 pair**（train 8616 / test 1028；训练脚本加载去重后是
8331 / 1017）。这 10 个任务是 spooky / dog-breed / tgs-salt / petfinder / whale / pizza /
google-quest / chaii / AI4Code / tweet——和第 3 节端到端对照用的任务基本是同一批（只差
essay-scoring）。

训练 log 在 `logs/augmented_mle_critic/0916/seleceted_scale_reward/`，`shorter` 是 1 个 epoch，
`longer` 是 2 个 epoch。把每次调参的最好成绩列出来：

| run（相对 `seleceted_scale_reward/`） | 训练/验证 pair | 学习率 | 最好 eval acc |
| --- | ---: | ---: | ---: |
| `shorter/lower_lr/Qwen3-8B_reward_seed7-1` | 8331 / 1017 | 5e-6 | **0.6539** |
| `shorter/lower_lr/Qwen3-8B_reward_seed7-2` | 8616 / 1028 | 5e-6 | 0.6508 |
| `longer/Qwen3-14B_reward_seed6` | 8331 / 1017 | 1e-5 | 0.6490 |
| `longer/Qwen3-8B_reward_seed6` | 8331 / 1017 | 1e-5 | 0.6431 |
| `longer/Qwen3-8B_reward_seed7` | 8331 / 1017 | 1e-5 | 0.6431 |
| `shorter/Qwen3-8B_reward_seed7` | 8331 / 1017 | 1e-5 | 0.6411 |
| `longer/Qwen3-4B_reward_seed7` | 8331 / 1017 | 1e-5 | 0.6391 |
| `shorter/lower_lr/further_lower/Qwen3-14B_reward_seed7` | 8331 / 1017 | 3e-6 | 0.6332 |
| `longer/Qwen3-1.7B_reward_seed7` | 8331 / 1017 | 1e-5 | 0.6273 |

结论：

1. **天花板就是 0.65 附近。** 调了半天，唯一过 0.65 的是 8B + 1 epoch + 5e-6 学习率这一组
   （0.6539），比 1e-5 那组高 1 个点。2 个 epoch 没有帮助。
2. **14B 没有优势。** 同一份 8331/1017 上，14B 最好 0.6490，比 8B 的 0.6431 高不到 1 个点；
   把学习率再降一半到 3e-6，14B 反而掉到 0.6332。三个 14B run 里没有一个是明确赢过 8B 的。
3. **和全量 68 任务的数据对比，也看不出"任务少、每任务样本多"带来了质变。** 全量那版
   （`logs/augmented_mle_critic/0916/scale_reward`，10547 / 1407）8B 最好 0.5899、14B 最好
   0.6020。数字上从 0.59 涨到 0.64 看着像进步，但
   **两个验证集不是同一份**：少任务版只有 1017 条、且只来自 10 个任务，本身就更"同分布"、更
   好刷。所以这个涨幅不足以支持 0918 里"任务太多、每任务样本太少"这个解释，只能说 0.6x 这个
   量级没被突破。

### 这组实验里几个需要注意的地方

- **`lower_lr` 的两个 repeat 用的输入也不一样**：`-1` 是 8331/1017，`-2` 是 8616/1028（原始划分，
  没去重）。原因是换了一个饱和的任务，两者差了 1 个点以内的 0.6539 / 0.6508。

## 3. 端到端对照：critic 接进搜索流程

### 3.1 设置

9 个任务 × 7200s 执行预算，`time_limit_secs = 86400`，`execution_timeout = 7200`。

| arm | 每个节点生成几个候选 | critic 打分后保留几个 | 实际执行几个 |
| --- | ---: | ---: | ---: |
| `mcts` | 2 | — | 2 |
| `forets` | 6 | top-3 | 从 top-3 里随机抽 2 |
| `forets-selected` | 6 | top-3 | 从 top-3 里随机抽 2 |

三个 arm 的区别在 critic：

- `forets` 用的是 **68 任务全量数据**训出来的 Qwen3-8B BT；
- `forets-selected` 用的是第 2 节**少量任务**训出来的 Qwen3-8B BT。

生成模型两档：`qwen` 是 xhigh 思考预算，`qwen-medium` 是 medium。两种预算下的任务不完全一样：
`qwen` 有 chaii / dog-breed / google-quest / essay-scoring / petfinder / tweet / whale，
`qwen-medium` 有 chaii / pizza / spooky / whale。

### 3.2 主表

每个 run 六条曲线的最后一个点；`run 数`写成"有 journal 的 run / 目录里的 run"。

| 任务 | 思考预算 | arm | run 数 | max_score | avg_max_score | avg_selected_score |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| chaii（越大越好） | qwen | mcts | 6/6 | 0.1431 | 0.1102 | **0.0974** |
| chaii | qwen | forets | 4/5 | **0.1457** | 0.0952 | 0.0444 |
| chaii | qwen-medium | mcts | 5/6 | 0.6070 | 0.5490 | 0.4708 |
| chaii | qwen-medium | forets | 5/5 | **0.6838** | **0.6202** | **0.5984** |
| dog-breed（log loss，越小越好） | qwen | mcts | 5/6 | **-0.3058** | **-0.3545** | -0.4080 |
| dog-breed | qwen | forets | 4/5 | -0.3293 | -0.4044 | -0.4078 |
| google-quest（越大越好） | qwen | mcts | 4/4 | 0.4110 | 0.3982 | 0.3943 |
| google-quest | qwen | forets | 3/3 | 0.4108 | **0.4034** | **0.3962** |
| essay-scoring（越大越好） | qwen | mcts | 4/4 | 0.8373 | 0.8328 | 0.7976 |
| essay-scoring | qwen | forets | 3/3 | **0.8404** | **0.8350** | **0.8295** |
| petfinder（RMSE，越小越好） | qwen | mcts | 5/8 | -17.0376 | -17.2916 | -26.8558 |
| petfinder | qwen | forets | 5/6 | **-16.9561** | -17.4299 | **-17.4601** |
| pizza（越大越好） | qwen-medium | mcts | 8/8 | 0.7788 | 0.7042 | 0.6739 |
| pizza | qwen-medium | forets | 6/8 | 0.8008 | **0.7726** | **0.7549** |
| pizza | qwen-medium | forets-selected | 5/8 | **0.8048** | 0.7478 | 0.6874 |
| spooky（log loss，越小越好） | qwen-medium | mcts | 6/6 | **-0.2221** | **-0.2639** | **-0.2707** |
| spooky | qwen-medium | forets | 7/8 | -0.2639 | -0.3165 | -0.3177 |
| tweet（越大越好） | qwen | mcts | 6/6 | **0.6940** | **0.6813** | **0.6798** |
| tweet | qwen | forets | 5/5 | 0.6721 | 0.6534 | 0.6533 |
| whale（越大越好） | qwen | mcts | 4/4 | 0.4028 | 0.3461 | **0.3161** |
| whale | qwen | forets | 3/3 | 0.3323 | 0.3207 | 0.2318 |
| whale | qwen | forets-selected | 3/3 | **0.4212** | **0.3576** | 0.2266 |
| whale | qwen-medium | mcts | 4/4 | **0.5200** | 0.4621 | 0.4131 |
| whale | qwen-medium | forets-selected | 3/3 | 0.4804 | 0.4615 | **0.4580** |

### 3.3 qwen（xhigh）对 qwen-medium

两边都跑过的配对只有 4 组，**medium 全胜，而且是碾压**：

| 任务 / arm | qwen（xhigh） | qwen-medium | 差 |
| --- | ---: | ---: | ---: |
| chaii / mcts | 0.0974 | 0.4708 | +0.373 |
| chaii / forets | 0.0444 | 0.5984 | +0.554 |
| whale / mcts | 0.3161 | 0.4131 | +0.097 |
| whale / forets-selected | 0.2266 | 0.4580 | +0.231 |

chaii 上 xhigh 两个 arm 的分数都只有 0.1 上下，已经不是"差一点"，而是基本没跑出能用的
solution。**但这里有一个混淆项**：xhigh 每次生成更慢，同样 24 小时里执行的节点数大约只有
medium 的六成（chaii / mcts：平均 22.3 个对 36.4 个；whale / forets-selected：19.3 个对 39.7 个）。
所以这个差距里混了"想得多但做得少"，不能全算成质量下降。

### 3.4 mcts 对 forets 对 forets-selected

用 `avg_selected_score` 做配对（同一个任务、同一个思考预算）：

| 任务 | 预算 | mcts | forets | forets-selected | 谁赢 |
| --- | --- | ---: | ---: | ---: | --- |
| chaii | qwen | **0.0974** | 0.0444 | — | mcts（+0.053） |
| chaii | qwen-medium | 0.4708 | **0.5984** | — | forets（+0.128） |
| dog-breed（越小越好） | qwen | -0.4080 | **-0.4078** | — | 平（0.0002） |
| google-quest | qwen | 0.3943 | **0.3962** | — | 平（+0.002） |
| essay-scoring | qwen | 0.7976 | **0.8295** | — | forets（+0.032） |
| petfinder（越小越好） | qwen | -26.8558 | **-17.4601** | — | forets（+9.40） |
| pizza | qwen-medium | 0.6739 | **0.7549** | 0.6874 | forets（+0.081） |
| spooky（越小越好） | qwen-medium | **-0.2707** | -0.3177 | — | mcts（+0.047） |
| tweet | qwen | **0.6798** | 0.6533 | — | mcts（+0.027） |
| whale | qwen | **0.3161** | 0.2318 | 0.2266 | mcts（+0.084） |
| whale | qwen-medium | 0.4131 | — | **0.4580** | forets-selected（+0.045） |

**这个结果和 0918 那一轮不一样。** 0918 是"9 组里 mcts 赢 8 组，差距 1.7–13.2 个点，而且是
稳的"；这一轮 10 组 mcts-vs-forets 配对里 mcts 赢 4 组、forets 赢 4 组、2 组基本打平，除
petfinder 之外所有差距都在 ±0.13 以内。所以 0918 的"mcts 稳定领先"没有复现，这轮更像是
**两边都差不多、谁赢取决于任务**。换成 `avg_max_score` 看也是 5:4，没有方向性。

两个数字特别大、需要单独解释的：

- **petfinder 的 +9.4 不是 forets 的功劳，是 mcts 自己翻车。** mcts 的 seed 1 用内部指标挑中
  的节点官方 RMSE 是 **65.0**（它自己跑出过 17.19），一个 run 就把平均值从 -17.3 拖到 -26.9。
  换成 `avg_max_score` 看，反而是 mcts 略高（-17.29 对 -17.43）。
- **chaii 的 +0.128 是在 xhigh→medium 换过思考预算之后出现的**，而且 forets 的 run 只有 5 个、
  时长也不完全对齐，先当一个待复核的信号。

`forets-selected` 只在 pizza 和 whale / qwen-medium 上跑了完整对照：

- **pizza 上它比 forets 差 0.068**（0.6874 对 0.7549）。也就是说"用任务内数据专门训过的 critic"
  反而更差；
- whale / qwen 上它和 forets 用的是**同一批 seed 目录**，可以直接配对：seed1 0.2454 对 0.2713、
  seed2 0.2724 对 0.1222、seed3 0.1618 对 0.3020，互有胜负；平均 0.2266 对 0.2318，等于打平。

### 3.5 qwen-medium 下"加 critic"对"不加 critic"

只看 `qwen-medium`（同一批任务、同一个思考预算），加 critic 的配对只有 4 组：

| 任务 | mcts | + forets | + forets-selected | 结果 |
| --- | ---: | ---: | ---: | --- |
| chaii | 0.4708 | **0.5984** | — | 加 critic 赢 |
| pizza | 0.6739 | **0.7549** | 0.6874 | forets 赢，但 forets-selected 输 |
| spooky | **-0.2707** | -0.3177 | — | 不加 critic 赢 |
| whale | 0.4131 | — | **0.4580** | forets-selected 略赢 |

2:2，而且每一个方向都只有一个任务支持。**从"要不要把 critic 接进搜索"这个决策角度看，这轮
是一点优势都没有**：加 critic 意味着每个节点多生成 4 个候选，换来的是 ±0.03–0.13 这种量级的
抖动，无法判断哪一组是真的。

### 3.6 这轮能确定什么、还缺什么

能确定的：**proxy 上的 0.65 没有转化成端到端的收益。** 而且在 9 个任务里 8 个任务的训练 pair
都在 critic 的训练集里，这种"in-distribution 也没优势"比 0918 的结论更硬——之前还可以说
"critic 在这些任务上只有 0.54–0.78，打平是正常的"，现在换成一个在这些任务上专门训过的 critic，
依然打平。

几个必须一起看的坑（会直接影响上面的结论强度）：

1. **各 arm 丢弃的 run 数不一样。** 目录里的 run 数和真正写出 `checkpoint/journal.jsonl` 的 run
   数对不上：pizza 的 `mcts` 是 8/8，但 `forets` 是 6/8、`forets-selected` 是 5/8；chaii / qwen 的
   `forets` 是 4/5、`mcts` 是 6/6；petfinder 的 `mcts` 是 5/8。没写出 journal 的 run（大多是没跑完
   就被 kill）被直接丢掉了，如果一个 arm 丢的正好是跑得最差的那些，平均分就会虚高。
2. **每个 arm 实际执行的节点数差很多**（pizza 的 forets 是 [12,16,18,27,35,82]，mcts 是
   [7,9,29,37,38,48,57,61]），而且 mcts 那几个 7–9 节点的 run 本身就没什么东西可比。
3. **critic 挑最终提交节点这一步依然不可靠。** 最明显的是 petfinder 的 mcts 选了个 RMSE 65 的
   节点。这是 0918 已经指出过的老问题：只要内部指标和官方分数错位，`avg_selected_score` 就会
   被单个 run 带跑。
4. **"同一个节点采 6 个候选，质量差多少"这个前提仍然没有大规模验证过。** 没被选中的候选我们从来没
   执行过，所以现在无法区分"6 个候选本来就差不多（critic 没得挑）"和"候选差很多但 critic 挑不
   准"。把 `checkpoint/journal_for_unselected.jsonl` 里那些候选离线跑一遍，就能把这两件事分开，
   这也是判断这条路有没有上限最便宜的实验——如果候选本来就没差异，问题就不在 critic 头上。

## 4. 结论和下一步

1. **agentic RL 暂时不值得继续投入**，除非能长期稳定拿到卡把 batch size 加上去再测一次。它
   的成本比单轮 RL 高很多，而单轮 RL 在同一份数据上是平稳升到 0.7 的。
2. **critic 这条路，proxy 上的天花板是 0.65 左右**，14B 没有规模优势，多任务/少任务、1 epoch/
   2 epoch、三个学习率都试过了。再加上 e2e 上加了 critic 和不加没有区别，这个方向基本可以
   收口。
3. 后面转向**直接训练 policy 模型**。
