# MLE policy 的 SFT 训练（verl）

数据怎么来的见 `src/mle_policy/docs/data/README.md`；这篇只讲拿它去训练。

**先看结论**：数据、转换脚本、训练脚本都跑通了，**但 Qwen3.5 在
`verl.trainer.sft_trainer` 这条路上会崩**（第 5 节，有证据），所以现在真正跑起来的
基线用的是 `Qwen/Qwen3-8B-Base`。换回 Qwen3.5 只要改一个环境变量，
前提是先把第 5 节的坑填掉。

## 1. 训练的是什么

* **数据**：`data/mle_policy/dataset/<bucket>/sft.jsonl`
  —— 每个 prompt group 里挑一条最好的解（rejection sampling），见数据文档 6.1 节。
* **模型**：`Qwen/Qwen3-8B-Base`（原计划 `Qwen/Qwen3.5-9B`，见第 5 节）
* **框架**：`src/verl` 的 `verl.trainer.sft_trainer`（纯 FSDP，不起 Ray）
* **机器**：projgpu39，2× RTX PRO 6000（每张 98 GB）

## 2. 数据转换：jsonl → verl parquet

脚本：`src/verl/my_recipes/dataset/mlepolicy_sft.py`

```bash
python src/verl/my_recipes/dataset/mlepolicy_sft.py \
  --input  data/mle_policy/dataset/non_thinking/sft.jsonl \
  --output-dir src/verl/data/mle_policy_sft/non_thinking \
  --model-path Qwen/Qwen3.5-9B \
  --max-length 16384
```

输出 `train.parquet` / `val.parquet`（一列 `messages`，就是 `MultiTurnSFTDataset`
要的格式）和 `conversion_report.json`。转换里做了三件必须做的事：

1. **按真实 chat template 量长度并丢掉超长样本。** 训练侧用 `data.truncation=error`，
   超长会直接报错；而截断一个解，要么切掉 prompt 要么切掉代码。
2. **`[system, assistant]` → `[user, assistant]`。** 走 openai 协议的实验把整段
   渲染好的 prompt 塞在一条 system 消息里，Qwen 的 chat template 需要 user 轮，
   否则直接抛 `No user query found in messages`。实测 25,833 行里有 19,481 行要改。
3. 把 token 长度直方图写进报告，换 `--max-length` 不用重新猜。

**一个坑**：`tokenizer.apply_chat_template(..., tokenize=True)` 在新版 transformers 里
返回 `BatchEncoding`，`len()` 拿到的是**键的个数（2）**而不是 token 数。第一版转换
因此把每一行都当成 2 个 token，等于没过滤。现在用 verl 自己的
`normalize_token_ids()` 归一化。

## 3. 训练脚本和启动方式

只有一个文件：`src/verl/my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_sft_fsdp.sh`。
它是自包含的：

* 训练部分：`torchrun -m verl.trainer.sft_trainer`，参数按含义分成
  `DATA` / `MODEL` / `ENGINE` / `OPTIM` / `TRAINER` 几个数组；
* 环境部分：脚本自己 `export` 训练需要的环境变量（`HF_TOKEN` / `WANDB_API_KEY`、
  `HF_HOME` / `TORCH_HOME` / `TRITON_HOME` / `VLLM_CACHE_ROOT` 等 cache、
  `WANDB_MODE`、`CUDA_VISIBLE_DEVICES` 等），值抄自 `src/verl/reminder`；
  token 是脚本运行时从 `<repo>/src/verl/reminder` 里 grep 出来的，不写死在脚本里。

先按 `src/verl/reminder` 在宿主机上起一个交互式 `singularity shell`，进容器后：

```bash
cd <repo>/src/verl          # 容器里就是 /workspace/verl/src/verl
bash my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_sft_fsdp.sh
```

**工作目录必须是 `src/verl`**，因为 `data.custom_cls.path` 写的是
`pkg://my_recipes.dataset.mlepolicy_sft_dataset`，要靠在当前目录下找到 `my_recipes`
这个包。

进容器那条命令里的 `PATH` / `LD_LIBRARY_PATH` / `PYTHONUSERBASE` **不在训练脚本里**
（它们只在进容器那一刻有意义，脚本里挂相对路径会解析错），必须照抄 reminder。

可用环境变量（都有默认值）：`GENERATION_BUCKET`、`MODEL_PATH`、`MAX_LENGTH`、
`TRAIN_BATCH_SIZE`、`MICRO_BATCH_SIZE_PER_GPU`、`LR`、`TOTAL_EPOCHS`、
`SAVE_FREQ`、`TEST_FREQ`、`SP_SIZE`、`NPROC_PER_NODE`、`CUDA_VISIBLE_DEVICES`。
多余的参数原样当 hydra override 传下去，例如
`... run_qwen3_5_9b_sft_fsdp.sh data.train_max_samples=64 trainer.test_freq=5`。
日志默认写到 `<repo>/logs/mle_policy/sft-qwen3_5-9b-<bucket>-<时间戳>.log`。

## 4. 关键配置和理由

| 配置 | 值 | 为什么 |
| --- | --- | --- |
| `GENERATION_BUCKET` | `non_thinking` | 见第 6 节 |
| `MAX_LENGTH` | 转换时 16384，8B 那次训练 32768 | 见第 6 节的长度实测 |
| `MICRO_BATCH_SIZE_PER_GPU` | 1 | 变长序列不 padding、不跨样本打包 |
| `TRAIN_BATCH_SIZE` | 16 | 全局 batch，2 卡 = 8 次梯度累积 |
| `LR` / warmup / 衰减 | 1e-5 / 3% / cosine | 全参 SFT 的常规量级 |
| `engine.strategy` | `fsdp2` | 仓库里 PPO 的 recipe 也用 fsdp2 |
| `engine.model_dtype` | `bfloat16` | 见下面「显存」 |
| `engine.use_torch_compile` | False | 默认是 True，在 Qwen3.5 上直接崩，所以关掉 |
| `engine.ulysses_sequence_parallel_size` | 1 | 2 卡拿来做数据并行，显存够 |
| `save_freq` / `test_freq` | 100 | 约每一小时存一次 ckpt、跑一次 val |

**显存。** 8B 全参训练实测：`train_batch_size=16`、单条最长 16k token 时，
单卡 allocated **52 GB**、reserved **92 GB**（卡是 98 GB）。优化器状态是大头：

* `model_dtype=bfloat16`：参数 16 GB + 梯度 16 GB + AdamW 两份状态 33 GB ≈ 65 GB；
* `model_dtype=fp32`（verl 默认）：上面三项全部翻倍 ≈ 130 GB，单卡放不下。

所以显式设了 `engine.model_dtype=bfloat16`。代价是优化器里的参数也是 bf16；
如果后面发现 loss 不稳，可以换回 fp32 并把 `MAX_LENGTH` 降下来。

## 5. Qwen3.5 在这套环境里跑不起来（这次的主要发现）

目标模型 `Qwen/Qwen3.5-9B` 一进第一个训练步就崩，两张卡同时报同一个错：

```text
CUDA error: an illegal memory access was encountered
```

加上 `CUDA_LAUNCH_BLOCKING=1` 之后拿到了内核级堆栈，崩在这一行：

```text
File ".../flash_attn/flash_attn_interface.py", line 165, in _flash_attn_varlen_forward
    out, softmax_lse, S_dmask, rng_state = flash_attn_gpu.varlen_fwd(...)
```

调用链：
`verl/workers/engine/fsdp/transformer_impl.py forward_step`
→ `verl/models/transformers/qwen3_5.py forward_with_normal_backend`
→ transformers 的 Qwen3.5 解码层
→ `verl/models/transformers/monkey_patch.py::_ulysses_flash_attention_forward`
→ `flash_attn_varlen_func`。

### 排除了什么

| 排查 | 结果 |
| --- | --- |
| 两张卡之间的 NCCL | 正常（all_reduce 通过） |
| flash-attn 本身 | 正常。单独跑 `flash_attn_varlen_func`：head_dim 64/128/256、GQA、causal、9000 token 都通过 |
| 模型本身能不能单卡前向反向 | 正常。单卡 Qwen3.5-9B + 梯度检查点，loss 4.32，峰值 36 GB |
| FSDP2 换 FSDP1 | 一样崩 |
| 关掉 `use_remove_padding` | 一样崩（而且这个引擎只支持 `pad_mode=no_padding`，关掉 remove_padding 反而是非法组合） |
| 关掉 `torch.compile` | 一样崩 |
| 临时跳过 verl 对 `Qwen3_5Model.forward` / `Qwen3_5ForConditionalGeneration.forward` 的替换（改用 transformers 原生 forward） | 一样崩；说明不是那个 patch 的锅。**实验后 `monkey_patch.py` 已还原，verl 干净** |
| `Qwen/Qwen3-0.6B-Base` | **正常训练**（loss 0.16 → 0.28） |
| `Qwen/Qwen3.5-2B` | **一样崩** |
| `Qwen/Qwen3-8B-Base` | **正常训练**（就是现在跑着的这个） |

结论：**不是这台机器、不是容器、不是 flash-attn、也不是 FSDP 的问题，
而是 Qwen3.5（`qwen3_5` 这个 model_type）在 verl 的 SFT 路径上水土不服。**

### 找到的可疑点

1. **Qwen3.5 会被当成多模态模型加载。** `Qwen/Qwen3.5-9B` 的 config 是
   `Qwen3_5ForConditionalGeneration`，verl 的 `get_hf_auto_model_class()` 走
   `AutoModelForImageTextToText`，加载的是**含 vision tower 的 9.41B**
   （纯文本的 `Qwen3_5ForCausalLM` 只有 8.95B）。而且 verl 的
   `qwen3_5_base_forward` 每次都拿占位像素跑一遍视觉塔
   （`_get_input_embeds` 里那段 `pixel_values = torch.zeros(...)`）。
2. **processor 会把 position_ids 变成多模态的四行。** Qwen3.5 的
   `Qwen3VLProcessor.image_processor` 类名是 `Qwen2VLImageProcessorFast`，
   `MultiTurnSFTDataset` 里那句
   `if "Qwen2VLImageProcessor" in self.processor.image_processor.__class__.__name__`
   正好命中，`position_ids` 从 `(seq_len,)` 变成 `(4, seq_len)` 的 mRoPE。
   packed 路径要把 `position_ids` 展平后交给 flash-attn 反推 `cu_seqlens`，
   四行布局会让它算出错的 `cu_seqlens`——正是 `varlen_fwd` 崩掉的典型原因。
   我为此加了 `my_recipes/dataset/mlepolicy_sft_dataset.py`（把 position_ids
   强制回一维），**但它没有解决问题**，说明还不是全部原因，先留在仓库里备查。
3. Qwen3.5 的线性注意力在容器里没有 `flash-linear-attention` / `causal-conv1d`，
   走 torch 兜底实现（日志里的 `The fast path is not available ...`）。
   仓库里 `my_scripts/train/3090/README.md` 也写了 "gradient update is 10 times
   slower than Qwen3 with same number of parameters"。

### 下一步可以怎么修（本次没做）

* 先试 **在 PPO/GRPO 那条路上跑 Qwen3.5**（`my_scripts/train/3090/Qwen3.5-*`
  那批脚本，仓库说他们跑过），判断是 SFT trainer 独有还是整个 qwen3_5 patch 的问题。
* 或者给 `verl/models/transformers/monkey_patch.py` 加开关，跳过
  `Qwen3_5Model.forward` 的替换，直接用 transformers 原生 forward。
* 或者干脆在容器里装 `flash-linear-attention` + `causal-conv1d`，既提速也改变
  Qwen3.5 的算子路径，有可能顺带绕开这个问题。
* 想省事就用 Qwen3-8B-Base（现在的基线）；数据管线与模型无关，随时能换回来。

### 容器本身的两个注意点

* 必须带 `LD_LIBRARY_PATH=/usr/local/cuda/compat`，否则 torch 报
  `The NVIDIA driver on your system is too old (found version 12080)`，
  连设备都拿不到。它挂在 reminder 里那条 `singularity shell` 命令上（见第 3 节），
  不在训练脚本里。
* `python script.py` 不会把当前目录放进 `sys.path`，所以在容器里直接按路径跑脚本
  （比如 converter）要显式给 `PYTHONPATH=/workspace/verl/src/verl`；
  训练走的是 `-m`，不受影响。

## 6. 为什么先训 non_thinking，以及 8B 那次为什么用 32k

数据分两个桶（见数据文档第 4 节）：

| 桶 | run 数 | SFT 行数 | completion 长什么样 |
| --- | ---: | ---: | --- |
| `non_thinking` | 1504 | 25,833 | 直接给方案和代码（API 模型） |
| `thinking` | 156 | 1,484 | 先一大段推理再给方案（自建 qwen3.8-27b） |

先训 non_thinking：样本多一个数量级，completion 格式就是 dojo 要 policy 输出的
"方案 + 代码"。thinking 桶样本太少，而且单条 completion 经常几万 token。

**长度实测**（用 Qwen3.5-9B 的 tokenizer 量 non_thinking 的 25,833 行）：

| 分位 | train（22,054 行） | val（3,779 行） |
| --- | ---: | ---: |
| 中位数 | 20,030 | 23,361 |
| p90 | 57,607 | 130,625 |
| p99 | 230,062 | 182,906 |
| 最大 | 299,788 | 203,150 |

这条数据**非常长**，比预想的长得多（debug 节点的 prompt 里带着整段代码和 stdout，
improve 节点的 prompt 里带着历史记忆）。16k 只留下 34%：

```text
--max-length 16384  →  保留 train 7,498 / val 1,271，其余按长度丢掉
```

所以 8B 那次训练把训练侧的 `MAX_LENGTH` 提到 **32768**：转换是按 Qwen3.5 tokenizer
在 16384 处过滤的，而 Qwen3 的词表更小、同样文本会切出更多 token，32k 的上限
保证不会因为 tokenizer 差异踩到 `truncation=error`。想真正利用长样本，
应该用目标模型的 tokenizer 重新转换一遍。

## 7. Validation

切分沿用数据侧的 `--split-by task`：68 个竞赛里 7 个进 val
（`billion-word-imputation`、`jigsaw-toxic-comment-classification-challenge`、
`siim-isic-melanoma-classification`、`spooky-author-identification`、
`tabular-playground-series-dec-2021`、`tensorflow-speech-recognition-challenge`、
`tensorflow2-question-answering`）。val loss 衡量的是"在没见过的竞赛上，
模仿搜索里最好的解有多准"，不等于最终 MLEBench 分数——那是端到端评测的事。

**一个小坑：只跑 1~2 步的冒烟测试里 `val/loss` 是 `nan`。** 0.6B / 2B / 8B 都这样，
所以不是模型问题。正式跑起来（每 100 步一次 val、val 有 1271 条）就是正常数字
（见第 8 节），所以没再深挖；真要查可以从
`verl/workers/utils/losses.py::sft_loss` 里的 `batch_num_tokens` 和 `log_prob` 入手，
多半是冒烟配置下某个微批被除零。

## 8. 实际跑起来的那次

```bash
cd <repo>/src/verl
MODEL_PATH=Qwen/Qwen3-8B-Base MAX_LENGTH=32768 TRAIN_BATCH_SIZE=16 \
TOTAL_EPOCHS=2 SAVE_FREQ=100 TEST_FREQ=100 \
bash my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_sft_fsdp.sh \
  engine.use_torch_compile=False \
  trainer.experiment_name=SFT-Qwen3-8B-Base-non_thinking-len32768
```

* 模型：`Qwen3ForCausalLM`，8.19B 参数，全参 + FSDP2 + bf16
* 数据：`data/mle_policy/verl_sft/non_thinking/{train,val}.parquet`（16k 过滤版）
* 训练集 7,498 行，`train_batch_size=16` → 468 步/epoch，计划 2 epoch
* **跑完 2 epoch = 936 步，耗时约 10.7 小时**（平均 ~41 秒/步，
  约 19 万 token/步，两张卡合计 ~4.6k token/s）
* 显存：单卡 allocated 53 GB、reserved 94 GB（98 GB 卡）
* checkpoint：`data/mle_policy/checkpoints/SFT-mle-policy/SFT-Qwen3-8B-Base-non_thinking-len32768/`
  （`global_step_900`、`global_step_936`）
* 日志：`logs/mle_policy/sft-qwen3_5-9b-non_thinking-<时间戳>.log`

训练结果（train loss 和 val loss 都是交叉熵，越低越好）：

| step | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 936 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| val loss | 0.2228 | 0.2145 | 0.2110 | 0.2091 | 0.2080 | 0.2077 | 0.2075 | 0.2075 | 0.2075 | 0.2075 |

train loss 末段在 0.13~0.15，grad_norm 0.5~0.9，LR 按 cosine 从 1e-5 退到 0。
**val loss 从第 700 步起就基本趴平了**（0.20747 → 0.20750），说明这一版
7,498 条 × 16k 的数据已经吃到头，继续多加 epoch 意义不大；下一步应该换更多更长
的数据（见第 9 节）。

### 8.1 第二个 run：把丢掉的那 66% 数据捡回来

上面那版被 16k 的长度上限砍掉了 66% 的数据（见第 6 节的长度实测），所以紧接着
又做了一个 run：**用训练模型自己的 tokenizer（Qwen3-8B-Base）在 32768 处重新
转换**，再训 1 epoch。转换结果：

```text
--model-path Qwen/Qwen3-8B-Base --max-length 32768
  → 保留 train 17,195 / val 2,376（16k 那版只有 7,498 / 1,271）
  → train 长度：中位数 18,998，p90 55,650，最大 294,561
```

```bash
cd <repo>/src/verl
MODEL_PATH=Qwen/Qwen3-8B-Base MAX_LENGTH=32768 TRAIN_BATCH_SIZE=16 \
TOTAL_EPOCHS=1 SAVE_FREQ=100 TEST_FREQ=100 \
VERL_DATA_DIR=<repo>/data/mle_policy/verl_sft/non_thinking_qwen3_32k \
CKPTS_DIR=<repo>/data/mle_policy/checkpoints/SFT-mle-policy/SFT-Qwen3-8B-Base-non_thinking-32k \
bash my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_sft_fsdp.sh \
  engine.use_torch_compile=False \
  trainer.experiment_name=SFT-Qwen3-8B-Base-non_thinking-32k
```

* 1,074 步/epoch，实测 **~55 秒/步**（约 29 万 token/步），1 epoch 约 16~19 小时
* 显存：单卡 allocated 63 GB、reserved 92 GB
* 这个 run 是在写文档时刚起来的，loss 还在下降（前 3 步 0.166 / 0.190 / 0.153），
  后面回来看日志即可

（脚本名里还留着 `qwen3_5` 是因为它本来是给目标模型写的；模型路径是环境变量，
换回 Qwen3.5 不用改脚本。）

## 9. 还没做的事

1. **Qwen3.5 的问题没修**，只做了定位（第 5 节）。
2. **冒烟配置下的 `val/loss=nan` 没深挖**，正式跑没这个问题。
3. **没做端到端评测**：训完的 policy 要接回 dojo 跑 MLEBench 才知道有没有用，
   val loss 只能说明"模仿得像不像"。
4. 数据里 p90 五万 token 的长样本（debug/improve 的历史上下文）现在还是被丢掉，
   如果要用，要么上更长的上下文，要么在数据侧把 prompt 里的历史记忆截断。
5. `thinking` 桶（1,484 条）还没训过。
