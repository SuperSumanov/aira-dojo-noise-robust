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

### 实测（2026-10-08，用已有 batches 重跑归总和导出）

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
├── src/data/build_grpo_parquet.py      # grpo.jsonl -> train/val parquet（分词）
├── src/data/grpo_dataset.py            # dataset + collate：一行一个 operation
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

### parquet 转换

```bash
# 在 src/verl 下、用训练环境（singularity 镜像）
python my_recipes/mle_policy/src/data/build_grpo_parquet.py \
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

先做便宜的自检（都不需要 GPU，除了最后一条）：

```bash
# 1) 只解析配置
python -m my_recipes.mle_policy.main_offline_ppo --cfg job > /tmp/cfg.txt

# 2) 数据通路：dataset -> collate -> _build_batch 的形状/mask/advantage
PYTHONPATH=. python -m pytest my_recipes/mle_policy/tests -q

# 3) 两卡 2B 跑两步（含一次 validation），约 5 分钟
#    （先在 /tmp 造一份小数据：build_grpo_parquet.py --limit-per-split 8）
MODEL_PATH=Qwen/Qwen3.5-2B LORA_RANK=128 TRAIN_BATCH_SIZE=8 VAL_BATCH_SIZE=8 \
PPO_MINI_BATCH_SIZE=8 TOTAL_EPOCHS=2 TEST_FREQ=2 SAVE_FREQ=-1 \
bash my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_grpo_offline_fsdp_lora.sh \
  trainer.total_training_steps=2 trainer.logger='["console"]'
```

跑通的样子（2B、LoRA、8 行/步）：`critic/advantages/mean` 等于数据里的 advantage
均值，`val/log_prob/mean` / `val/reward/mean` 正常输出，日志里**不该出现**
"The fast path is not available ... Falling back to torch implementation"——
出现这句就说明 `flash-linear-attention` 没加载上，别继续往下跑。

## 4. 已知的坑

1. **`flash-linear-attention` / `causal_conv1d` 必须能 import。** 它们装在
   `src/verl/verl_env`（PYTHONUSERBASE 指的那个 user site），所以容器启动时
   PYTHONUSERBASE 必须指对（见第 3 节）。缺了它们 Qwen3.5 的 linear attention 走
   纯 torch 兜底，`use_remove_padding=True` 会在训练中途 CUDA illegal memory access；
   就算关掉 remove_padding 改走 padding 布局，显存也会被
   `logits = micro-batch token 数 × 词表` 顶爆（2B、8 行 7.5 万 token 一步就 92GB），
   64k 上下文根本放不下。
2. **`MAX_TOKEN_LEN_PER_GPU` 不能小于数据里最长的一行**，否则动态切分直接 assert。
   转换时 `--max-length` 给多少，这里就得 ≥ 多少。
3. **rollout 相关的东西还有残余**：worker 本身还是会按角色名建一个 rollout
   对象（`rollout.name=vllm` 是必填配置项），只是驱动进程不再起 LLM server。
4. **debug / analysis 这些 operation 也进了 GRPO**，每条都带它 episode 的 advantage。
   如果发现某个 operator 在捣乱（比如 analysis 的目标不是写代码），
   `to_grpo.py --operators draft,debug,improve,crossover` 可以不要它。
5. **正例里 38% 的 episode root 本身跑不通**（SFT 挑的是整个 debug 过程最后跑通的
   episode）。这是 episode 级 return 的固有取舍，`overview.md` 第 10 节第 5 条也写了；
   要换口径就改 `to_grpo.py` 里 reward 的定义。
6. `data/mle_policy/dataset/*/{sft,grpo}_{train,val}.parquet` 是旧的流水线留下的
   残留（现在只在 verl 侧转 parquet），可以删。
