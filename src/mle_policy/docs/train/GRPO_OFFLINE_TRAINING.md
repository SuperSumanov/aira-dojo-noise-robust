# MLE policy 的离线 GRPO（拿历史搜索数据当 rollout）

数据怎么来的见 `src/mle_policy/docs/data/overview.md`，SFT 怎么训的见
`SFT_TRAINING.md`。这篇讲 GRPO：数据长什么样、训练代码放在哪、怎么跑、有哪些坑。

## 0. 一句话

SFT 是"每个 group 挑一个最好的 episode，把它的每个 operation 当成一条训练样本"。
GRPO 用**完全一样的样本**，只是多带一个数：这条样本所属 episode 的
**group-relative advantage**。advantage 在造数据的时候就算好写进文件，
训练时读出来直接用，verl 里"采样 → 算 reward → 算 advantage"这三步全部省掉，
old logprob / reference logprob / KL / PPO 的 clip 目标 / actor update 一点没改。

## 1. 数据：`to_grpo.py` 产出的 `grpo.jsonl`

一行 = **一次 LLM 调用**（一个 operation），和 `sft.jsonl` 同一粒度：

```json
{"sample_id": "...", "group_id": "...", "episode_id": "...", "task": "...",
 "batch": "...", "split": "train", "operator": "debug",
 "prompt": [{"role": "system", ...}, {"role": "user", ...}],
 "completion": "...", "reward": 0.2457, "advantage": 0.7071,
 "episode_resolved": true, "node_has_result": true}
```

* **prompt / completion**：和 SFT 完全一样的两件事——同样的归一化
  （包列表排序、proposal 去掉 "PREVIOUSLY EXPLORED ..." 搜索记忆、补回算子的
  system message），root operation 用 group 内最早的 root prompt，其余 operation
  用自己的 prompt。
* **reward**：这条 operation 所在 episode 的 episode reward，也就是它那条 debug
  过程最后拿到的可运行解的归一化分数。没跑出可运行解的 episode 没有分数，默认放在
  **同组最差可行解下面一个 gold span**（`--unresolved-reward` 可以钉死）。
* **advantage**：`(reward - 组内均值) / 组内 std`，在**造数据时**对 group 算一遍。
  一个 episode 里所有 operation 共享同一个 advantage——它们本来就是同一条决策链，
  只是被拆成了独立的训练样本。`--no-norm-adv-by-std` 可以去掉除以 std 那步
  （Dr.GRPO 风格，reward 差距大小会进梯度）。

group 的定义没变：**同一套环境下、root prompt 相同的那些 episode**（就是流水线里
的 `group_id`）。没有正负样本之分，直接当一组 GRPO 数据用。

丢掉的 group（都是没信息量的）：

| 情况 | 为什么丢 |
| --- | --- |
| 只有 1 个成员 | 组内均值/方差没意义 |
| 一个都没跑通 | 所有 reward 都是同一个地板值 |
| reward 全相同 | std = 0，advantage 恒为 0 |

### 实测

| 桶 | aggregated group | 出 GRPO 的 group | 训练行数 | 丢掉：单成员 / 全没跑通 / 无落差 |
| --- | ---: | ---: | ---: | --- |
| `non_thinking`（限定 provider 后） | 7,009 | 5,525 | 50,246 | 44 / 1,271 / 169 |
| `thinking`（selfhosted qwen3.8-27b） | 867 | 856 | 10,523 | 0 / 8 / 3 |

对比 SFT：`non_thinking` 的 `sft.jsonl` 是 19,047 行，GRPO 是 50,246 行——
因为 SFT 每组只留一个 episode，GRPO 要组里每个 episode 的每个 operation。

### reward 的长尾（要不要裁）

`reward = (score - 中位数门槛) / (金牌门槛 - 中位数门槛)`，有些竞赛的金牌门槛
紧贴中位数，分母极小，reward 会炸。`non_thinking` 实测：中位数 -2.01、
p90 +1.06，但 **377 行（0.75%）的 |reward| > 100**，最坏的
`smartphone-decimeter-2022` 到 -8.2e6。

advantage 因为是组内标准化的，反而是**有界**的（实测 min -3.01 / max 2.53），
所以这件事对训练影响很小；它主要影响日志里那个 reward 数，以及样本数 >2 的组里
极端值会挤压其它样本的 advantage。想在源头掐掉就加 `--reward-clip -3 3`
（先裁 reward 再算 advantage，地板值不会跟着被裁）。

## 2. 训练代码放在哪

verl 主代码一行没动，全部在 `src/verl/my_recipes/mle_policy/` 下：

```text
my_recipes/mle_policy/
├── main_offline_ppo.py                 # hydra 入口 + TaskRunner
├── config/offline_ppo.yaml             # 继承 verl 的 ppo_trainer，只改离线相关的
├── src/dataset/build_grpo_parquet.py      # grpo.jsonl -> train/val parquet（分词）
├── src/dataset/grpo_dataset.py            # dataset + collate：一行一个 operation
├── src/trainer/ppo/offline_ray_trainer.py   # 继承 RayPPOTrainer
└── tests/test_offline_pipeline.py      # 不需要 GPU 的通路测试
```

### `offline_ray_trainer.MleOfflineRayPPOTrainer`

继承 `verl.trainer.ppo.ray_trainer.RayPPOTrainer`，覆盖三件事：

| 覆盖 | 原来干什么 | 现在干什么 |
| --- | --- | --- |
| `init_workers` | 建 actor、ref、reward loop、LLM server、agent loop、checkpoint engine | 只建 policy 的 worker group（LoRA 时 ref 就是不带 adapter 的 actor）；离线不生成，vLLM 一个进程都不起 |
| `fit` | 用 vLLM 采样 → 算 reward → 估 advantage → actor update | 直接读数据里的 advantage（`_build_batch` 把它广播到该行的 response token 上，形状和 verl 自己算出来的完全一致）→ old logprob → ref logprob → actor update |
| `_validate` | 生成、打分、按数据源统计 | 数据里的 reward 是固定的，报它没意义；改成报**当前策略给这些 val 回答的平均 logprob**、entropy 和平均 reward |

`old_log_prob` / `_compute_ref_log_prob` / `_update_actor` / `_save_checkpoint` /
`_load_checkpoint` / `_balance_batch` 全是父类的方法，没抄。

数据流：

```text
train.parquet（一行一个 operation）
  │ MlePolicyGRPODataset     读一行（token id 还是 arrow 里的 list，取到才展开）
  ▼
DataLoader（普通 shuffle，行之间没有依赖）
  │ offline_collate          右 padding，拼 input_ids/attention_mask/position_ids/
  ▼                          response_mask/rm_scores，带出 reward + advantage 标量
MleOfflineRayPPOTrainer._build_batch
  │ advantage * response_mask；reward 留在 token_level_scores 供日志
  ▼
old logprob → ref logprob → KL → PPO clip → actor update
```

行之间没有"必须同组"的约束（advantage 已经算好），所以 batch 随便切、随便 shuffle。

### PPO 的 ratio / clip 在这份配置下其实是不生效的

循环顺序就是 verl 原来的，一点没改：

```text
一个 train batch (data.train_batch_size 行)
  ├─ _compute_old_log_prob  整个 batch 一次：当前策略给这些动作的 logprob
  ├─ _compute_ref_log_prob  整个 batch 一次：reference 的 logprob（进 KL loss）
  └─ _update_actor          worker 里按 ppo_mini_batch_size 切 mini-batch，
                            跑 ppo_epochs 遍，每遍一个优化器 step
```

三个相关量的定义（都在 `verl/trainer/ppo/core_algos.py::compute_policy_loss_vanilla`）：

* `ratio = exp(logπ_new − logπ_old)`，`logπ_old` 是更新前那一份，在 loss 里当常数；
* `actor/ppo_kl = mean_response_tokens(logπ_old − logπ_new)`，也就是 KL(π_old‖π_new) 的单样本估计；
* `actor/pg_clipfrac` = 被 clip 的 token 比例。

**脚本默认 `TRAIN_BATCH_SIZE == PPO_MINI_BATCH_SIZE`（都是 32）、`ppo_epochs=1`，所以一个数据 batch
只做一次梯度更新**，而这一次更新用的策略和算 `logπ_old` 时是同一个 → `ratio ≡ 1`，
`ppo_kl ≡ 0`、`pg_clipfrac ≡ 0`（20261009 那份 9B log 全程就是这样）。
此时梯度正好是 `−A·∇logπ`（因为 `d ratio/dθ = ratio·∇logπ_new`，ratio=1）：
**`old_log_prob` 不进梯度**，它只是让 loss 的形状和 verl 一致，并顺手提供 entropy / ppo_kl 这两个诊断。

这在这个任务里是合理的选择，不是漏配：这些动作是**别的模型**（glm / kimi / minimax …）生成的，
`π_old` 根本不是行为策略，ratio 在这里不是"重要性纠正"而是纯记账；一个 batch 走一步
= 最干净的 offline policy gradient（等于 RAFT / rejection sampling 再乘 advantage）。

想让 ratio/clip 真的起作用，就让一个数据 batch 出多个梯度步：

```bash
PPO_MINI_BATCH_SIZE=8     # 32 行 → 4 次梯度更新；第 2 次起 ratio ≠ 1
# 或者 actor_rollout_ref.actor.ppo_epochs=2
```

这时 `pg_clipfrac` / `ppo_kl` 才有意义（trust region 在起作用），而且每个 batch 的
old/ref 两次前向（参考 log：约 15s + 13s）会摊到更多次梯度更新上，单步墙钟更快。
但别指望它能修正分布漂移：mini-batch 内的 ratio 只保证"别离更新前的自己太远"，
和"数据是别的模型产的"这件事无关。

### parquet 转换

```bash
# 在 src/verl 下、用训练环境（singularity 镜像）
python my_recipes/mle_policy/src/dataset/build_grpo_parquet.py \
  --input  <repo>/data/mle_policy/dataset/non_thinking/grpo.jsonl \
  --output-dir data/mle_policy_grpo/non_thinking \
  --model-path Qwen/Qwen3.5-9B \
  --max-length 65536
```

输出 `train.parquet` / `val.parquet` / `conversion_report.json`。转换里做两件事：
用真实 chat template 给 prompt/response 分词（response 是从渲染好的 assistant 轮里
切出来的，带上结束 token），以及按 `--max-length` 丢超长行（行之间独立，
一条长的 debug 调用不会连累它所在的 episode）。

`--enable-thinking` 直接传给 chat template。**默认（`default`）就是 SFT 用的那套**：
`non_thinking` 的 SFT parquet 是用模板默认（thinking 开着）转的——那些 completion
本身没有推理，于是被包在一个空的 `<think></think>` 里，这正是 SFT 时模型看到的样子，
GRPO 要和它保持一致（也方便直接从 SFT 的 LoRA 接着训）。要专门做 thinking 实验才显式传值。

实测（`--max-length 65536`，和 SFT 同一档上下文，**不截断**）：
`non_thinking` 44,751 行只丢 20 行（train 44,731 / val 5,495，token 中位数 11.3k /
p90 22.1k / 最大 65.3k）；`thinking` 9,630 行丢 11.7%
（train 8,507 / val 754，token 中位数 11.7k / p90 33.5k / 最大 65.5k，
因为推理链把序列拉长了）。

## 3. 怎么跑

在宿主机起 singularity（和 `SFT_TRAINING.md` 一样），进 `src/verl` 后：

```bash
bash my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_grpo_offline_fsdp_lora.sh
```

关键参数（都可用环境变量覆盖）：

```bash
TRAIN_BATCH_SIZE=32          # 行数（一行一个 operation，不是 group 数）
MAX_TOKEN_LEN_PER_GPU=80000  # 每个 micro-batch 每卡多少 token，不能小于数据里最长行
LORA_RANK=128                # 默认开；9B 跑在 2×Pro6000 上必须开
KL_LOSS_COEF=0.01  LR=1e-6  TOTAL_EPOCHS=3
GENERATION_BUCKET=non_thinking   # 或 thinking
MODEL_PATH=Qwen/Qwen3.5-9B       # thinking 桶的数据来自 27B，换 27B 时记得改
```

引擎设置和 SFT 对齐：`use_remove_padding=True` + `use_fused_kernels=True`
（打包 + 融合 kernel，logits 不会在整条 prompt 上展开，64k 上下文才放得下）。

## 4. 指标怎么看

### 4.0 第一件要记住的事：reward 是数据，不是 performance

离线 GRPO 的 reward 和 advantage 是造数据时算好写进 parquet 的，**训练过程中一个字节都不会变**。
所以下面这些数**上下跳不代表模型变好或变坏**，它们只是"这一步恰好抽到哪些行"：

| 指标 | 实际含义 |
| --- | --- |
| `critic/score/mean`、`/max`、`/min` | 这一步抽到的行在 `grpo.jsonl` 里的 `reward`（就是 episode reward） |
| `critic/rewards/*` | 同上（`token_level_scores` 求和，我们就是原样透传） |
| `critic/advantages/mean`、`/max`、`/min` | 这一步抽到的行的 `advantage`（造数据时按 group 算好的） |
| `critic/returns/*` | 同 advantages（离线没有 critic，returns 只是复制） |
| `val/reward/mean` | val 集的平均 reward，**固定值**（同一个 val 集每步都一样） |
| `response_length/*`、`prompt_length/*` | 这一步数据的长度分布，也是数据属性 |

实测例子：`critic/rewards/mean` 在 step 1 是 -3.39、step 8 是 -2.56e5、step 19 是 -5.48。
这不是退化，是那一步抽到的行里撞上了 reward 长尾（第 1 节「reward 的长尾」说的某些竞赛门槛极窄）。

一个能当**一致性自检**用的小性质：第一步 `ratio ≡ 1`，所以
`actor/pg_loss ≈ -critic/advantages/mean`。这份 log 里 step 1 是
`adv = -0.005113` / `pg_loss = +0.005113`，对上就说明 advantage 是原样喂进去的，
后面两者分叉是因为 ratio 不再等于 1。

### 4.1 真正会动、能说明"在学"的数

GRPO 在做的事情是：**把 advantage 为正的回答抬上去，把 advantage 为负的压下去**。
所以只有"策略给这些记录答案的概率"值得看：

| 指标 | 含义 | 期望方向 |
| --- | --- | --- |
| `val/log_prob/advantage_positive` | 固定 val 集里 A>0 那些行，模型给它们的平均 logprob（每行先按 response token 取平均） | **上升** |
| `val/log_prob/advantage_negative` | A<0 的那些行 | **下降** |
| `val/advantage_weighted_log_prob/mean` | `mean_i(A_i × 该行平均 logprob)`，上面两个合成一个数 | **上升 = 在学** |
| `val/log_prob/mean` | 全部行不分正负的平均值 | 只当量纲参考：正负会互相抵消，一个在学但把负样本压得更狠的策略，这个数可能不升反降 |
| `val/entropy/mean` | 模型在这些回答上的平均 token 熵（nats） | 缓慢下降正常，掉到接近 0 就是开始坍缩 |
| `val/rows` | val 集行数 | 固定，用来确认喂进去的是哪个 val 集 |

训练行上对应的是 `actor/advantage_weighted_log_prob/mean`（每步都打），
意义一样，但**每一步抽的数据不同**，所以噪声很大，只能看长期趋势。

### 4.2 训练步里的每个数（在这份 log 里的实际取值）

| 指标 | 含义 | 怎么读 |
| --- | --- | --- |
| `actor/loss` | `pg_loss + kl_coef × kl_loss`（`use_kl_in_reward=False`，所以没有 reward 侧的 KL） | 逐步噪声大，**不要当 loss 曲线看**；step 1 = 0.0051，step 18 = -0.140 |
| `actor/pg_loss` | PPO 的 clip 目标 `-mean(A_i × ratio_i)` | 第一步 ≈ `-mean(A)`；后面随 batch 内容变。数值卡在 O(mean\|A\|) 就正常 |
| `actor/kl_loss` | 与 reference（开 LoRA 时 = 不带 adapter 的同一模型）的 KL | 第一步必然是 0；这份 log 从 step 3 起涨到 1.6e-4 并稳定在 ~1.8e-4 = 策略还没离开起点 |
| `actor/kl_coef` | 0.01（配置值），乘进 loss | 固定 |
| `actor/pg_clipfrac` / `pg_clipfrac_lower` / `ppo_kl` | 被 clip 的 token 比例 / 正负方向各自的 clip 比例 / 新旧策略的近似 KL | 初始几步 **全程 0**：ratio 一直在 1 附近，也就是每步只挪了一点点。开始出现 0.1+ 说明单步移动过猛 |
| `actor/grad_norm` | 梯度范数 | 稳定在 0.18~0.34 = 健康；突然几十上百或 NaN = 炸了 |
| `actor/lr` | 当前学习率 | step 1 = 4.8e-9，step 19 = 9.1e-8，而目标是 1e-6 → **19 步还在 warmup 头一段**（`lr_warmup_steps_ratio=0.05`）。warmup 结束前不要指望看到变化 |
| `actor/entropy` | response token 的平均熵 | 0.17~0.29 上下晃，没有系统性下降 = 还没坍缩 |
| `actor/advantage_weighted_log_prob/mean` | 见 4.1 | 逐步噪声大，看趋势 |
| `actor/perf/max_memory_allocated_gb` / `max_memory_reserved_gb` / `cpu_memory_used_gb` | 显存/内存峰值 | 逼近上限就调小 `MAX_TOKEN_LEN_PER_GPU` |
| `perf/mfu/*` | MFU | 恒为 0.0 = **没接 profiling，不是性能问题** |
| `global_seqlen/*` | 一步里各数据并行 rank 的 token 数（`balanced_*` 是 `trainer.balance_batch` 重排之后的） | 只反映负载均衡，和训练好坏无关 |
| `response_length/clip_ratio`、`prompt_length/clip_ratio` | **不是被截断的比例**，而是"长度等于本 batch 最长那一行"的行占比 | 0.03125 = 1/32，因为 batch 里总有一行是最长的。数据在转换时已按 65536 过滤，训练里不会有截断 |
| `response/aborted_ratio` | 生成得到空回答的比例 | 离线数据里应该恒为 0 |
| `timing_s/old_log_prob` / `timing_s/ref` / `timing_s/update_actor` / `timing_s/step` / `perf/throughput` | 各段耗时和吞吐 | step ≈ 70~106s，其中 `update_actor` 45~65s、`old_log_prob` 14~17s、`ref` 12~14s；吞吐 ≈ 2200~2500 token/s（2 卡 9B LoRA）。算 pacing 用它 |

### 4.3 一套检查清单

**刚起来（前 1~2 步）**

1. 日志里**不能**出现 `The fast path is not available ... Falling back to torch implementation`
   （出现就是 `flash-linear-attention` 没加载）。
2. `actor/kl_loss = 0`、`actor/pg_loss ≈ -critic/advantages/mean`、`response/aborted_ratio = 0`、
   `actor/grad_norm` 是个 O(0.1~1) 的数。
3. `actor/lr` 很小是正常的（warmup）。

**跑到几十步以后**

4. `actor/lr` 应该按 warmup 往上爬；`actor/kl_loss` 从 0 涨到 1e-4~1e-3；
   `actor/pg_clipfrac` 开始出现小值 —— 说明策略真的在动。
5. 看 val：`val/log_prob/advantage_positive` ↑、`val/log_prob/advantage_negative` ↓、
   `val/advantage_weighted_log_prob/mean` ↑。这是唯一干净的"在学"证据。

**报警信号**

6. `val/entropy/mean` 掉到很低（比如 < 0.05）、`actor/pg_clipfrac` 冲到 0.2+、
   `actor/grad_norm` 暴涨 → 单步移动太猛：调小 `LR` 或 `KL_LOSS_COEF`。
7. `val/log_prob/advantage_negative` 反而上升、`val/advantage_weighted_log_prob/mean` 一路下行
   → 要么 lr 太小（本来就没动），要么 advantage 本身有问题（回第 1 节的「reward 的长尾」小节查 reward）。
8. 显存峰值贴着卡上限 → 调小 `MAX_TOKEN_LEN_PER_GPU`（并把转换时的 `--max-length` 保持一致地放小，
   但那等于砍上下文，所以优先考虑减 `TRAIN_BATCH_SIZE`）。