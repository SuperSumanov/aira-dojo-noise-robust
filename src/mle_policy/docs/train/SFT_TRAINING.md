# MLE policy 的 SFT 训练（verl）

数据怎么来的见 `src/mle_policy/docs/data/README.md`；这篇只讲拿它去训练。

## 1. 训练的是什么

* **数据**：`data/mle_policy/dataset/<bucket>/sft.jsonl`
  —— 每个 prompt group 里挑一条最好的episode（rejection sampling）。
* **模型**：`Qwen/Qwen3.5-9B` 和 `Qwen/Qwen3.8-27B`
* **框架**：`src/verl` 的 `verl.trainer.sft_trainer`（纯 FSDP，不起 Ray）
* **机器**：projgpu39，2× RTX PRO 6000（每张 98 GB）/ `Qwen/Qwen3.8-27B`则使用4xh200
* **环境**：参考`src/mle_critic/docs/train/LOOKAHEAD_REWARD_MODEL_EXPERIMENTS.md`中的verl环境配置

## 2. 数据转换：jsonl → verl parquet

脚本：`src/verl/my_recipes/dataset/mlepolicy_sft.py`

```bash
python src/verl/my_recipes/dataset/mlepolicy_sft.py \
  --input  data/mle_policy/dataset/non_thinking/sft.jsonl \
  --output-dir src/verl/data/mle_policy_sft/non_thinking \
  --model-path Qwen/Qwen3.5-9B \
  --max-length 65536
```

输出 `train.parquet` / `val.parquet`（一列 `messages`，就是 `MultiTurnSFTDataset`
要的格式）和 `conversion_report.json`。转换里做了三件必须做的事：

1. **按真实 chat template 量长度并丢掉超长样本。** 训练侧用 `data.truncation=error`，
   超长会直接报错；而截断一个解，要么切掉 prompt 要么切掉代码。
2. **补回 system 轮。** Qwen3.5 的 SFT 要 `[system, user, assistant]`，而走 openai
   协议的老 run 只记了一条 system 消息（里面其实是渲染好的 user prompt）。
   `to_sft.py` 按 operator 从 `src/dojo/configs/solver/operators/mlebench/` 里读回
   system message（`aira_operators/*.yaml`，`analysis` 在 `aide_operators/analyze.yaml`），
   写成 `[system, user, assistant]`。
3. 把 token 长度直方图写进报告，换 `--max-length` 不用重新猜。

### 2.1 报告里的 per-operator 保留率

`conversion_report.json` 的 `train` / `val` 里各有一份 `operators` 表，按行数排序，
回答"哪个 operator 的数据被 `--max-length` 砍掉了"。`operator` 字段由
`src/mle_policy` 的 `to_sft.py` 写进 `sft.jsonl`（老的 jsonl 没有这个字段，
转换时会提示 `unknown`，重跑一次 `to_sft` 即可）。

`to_sft` 里还有两件直接影响长度的事：draft / improve / crossover 的 prompt 会删掉
"PREVIOUSLY EXPLORED ..." 搜索记忆（这些选择和记忆要训进参数，而不是让模型每步从
prompt 里读别人试过什么；`debug` / `analysis` 带的是代码和报错，不动），以及给只有
一条 system 消息的 run 补回 operator 的 system message。

non_thinking、`--max-length 65536` 的实际效果（train）：

| operator | 行数 | 保留率 | 中位数 | p90 |
| --- | ---: | ---: | ---: | ---: |
| `analysis` | 15,804 | 100.0% | 8,597 | 14,057 |
| `improve` | 9,299 | 99.97% | 15,118 | 24,460 |
| `debug` | 6,578 | 99.94% | 16,493 | 26,968 |
| `draft` | 385 | 100.0% | 8,346 | 12,464 |

整体 train 32,059 / 32,066（99.98%），val 3,367 / 3,367（100%）；丢掉的 7 条是最长的
debug / improve（最大 92k token）。同样这份数据压到 `--max-length 16384` 只有
train 75.4%（`improve` 60.9%、`debug` 49.1%），要长上下文就得按 64k 这批来。

## 3. 训练脚本和启动方式

在宿主机上起一个交互式 `singularity shell`，进容器挂上必要的环境变量后：

```bash
cd <repo>/src/verl          # 容器里就是 /workspace/verl/src/verl
bash my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_sft_fsdp_lora.sh
# Qwen3.8-27B 在4xh200上用 4xh200/run_qwen3_8_27b_sft_fsdp_lora.sh
```

**工作目录必须是 `src/verl`**，因为 `data.custom_cls.path` 写的是
`pkg://my_recipes.dataset.mlepolicy_sft_dataset`（类名 `MlePolicySFTDataset`），
要靠在当前目录下找到 `my_recipes` 这个包。这个类必须用：verl 自带的
`MultiTurnSFTDataset` 会逐条渲染 message，Qwen3.5 上直接崩，见第 2 节。

## 4. 导出lora adapter进行VLLM推理

训练完之后是fsdp的分片格式，需要先导出adapter（在`src/verl`下跑）

```bash
python -m verl.model_merger merge \
  --backend fsdp \
  --local_dir checkpoints/SFT-mle-policy/SFT-Qwen3.5-9B-non_thinking-len65536-bsz128-lr1e-5/global_step_665 \
  --target_dir outputs/sft_mle_policy/qwen3_5_9b_step665_hf
```

`--target_dir`里会同时写出合并后的完整模型和`lora_adapter/`；起vllm只需要后者，
完整模型那几十个GB不用留。

### 4.1 先剪掉vision tower的LoRA

训练脚本里`model.target_modules=all-linear`会把Qwen3.5-9B这个VL模型的**vision tower**
也套上LoRA，所以`lora_adapter`里混着110个`model.visual.*`模块（220个张量）。vllm默认只给
语言模型挂LoRA（tower的LoRA要开`--enable-tower-connector-lora`，还是实验性的），加载时
直接报错：

```
ValueError: While loading .../lora_adapter, expected target modules in
{... 'q_proj', 'in_proj_qkv' ...} but received ['visual.blocks.0.attn.proj', ...]
```

我们的数据全是文本，vision tower的LoRA拿不到梯度，`lora_B`恒等于0，所以剪掉它在数值上
没有任何影响。脚本默认写到旁边的`lora_adapter_vllm/`，只保留248个语言模型模块（496个张量）；
万一tower的`lora_B`不是全0，它会直接报错而不是静默丢权重：

```bash
bash src/mle_policy/scripts/export/prune_lora_adapter_for_vllm.sh \
  outputs/sft_mle_policy/qwen3_5_9b_step665_hf/lora_adapter
```

想让以后的run从源头干净，可以在训练脚本里加`model.exclude_modules='.*visual.*'`；代价是
LoRA初始化的随机流会变，和现有的checkpoint不可比特复现，所以旧的结果不要重训比对。

### 4.2 启动vllm

然后用底模加剪过的adapter来启动vllm

```bash
srun -J vllmserve \
  --ntasks 1 \
  --gres=gpu:2 \
  --cpus-per-task=6 \
  -o tmp/vllm_%j.log \
  -e tmp/vllm_%j.err \
  singularity exec --nv --cleanenv \
    --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_CACHE_ROOT=/research/d2/gds/zzchen2/vllm_cache \
    --env TRITON_HOME=/research/d2/gds/zzchen2/triton_home \
    --env TORCH_HOME=/research/d2/gds/zzchen2/torchhome \
    --env HF_HOME=/research/d2/gds/zzchen2/transformerscache \
    --env HF_HUB_OFFLINE=1 \
    -B /research/d2/gds/zzchen2:/research/d2/gds/zzchen2 \
    build/vllm/vllm.sif \
    vllm serve Qwen/Qwen3.5-9B \
      --served-model-name qwen3.5-9b \
      --enable-lora \
      --max-lora-rank 128 \
      --lora-modules qwen3.5-9b-mle-lora=outputs/sft_mle_policy/qwen3_5_9b_step250_hf/lora_adapter_vllm \
      --host 0.0.0.0 \
      --port 8000 \
      --api-key sk-vllm-gpu27-qwen35-9b-mle-lora \
      --tensor-parallel-size 2 \
      --max-model-len 65536 \
      --gpu-memory-utilization 0.95 \
      --limit-mm-per-prompt '{"image":0,"video":0}' \
      --max-num-seqs 8 &
```

原模型也可以通过`qwen3.5-9b`来调用，lora模型通过`qwen3.5-9b-mle-lora`来调用，两者共享一个server。最后启动e2e评估

```bash
python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_mcts_qwen_minimal_lora \
  'benchmark.tasks=[tgs-salt-identification-challenge]' \
  'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.5-9B-mle-lora' \
  'solver/client@solver.operators.debug.llm.client=litellm_qwen3.5-9B-mle-lora' \
  'solver/client@solver.operators.draft.llm.client=litellm_qwen3.5-9B-mle-lora' \
  'solver/client@solver.operators.improve.llm.client=litellm_qwen3.5-9B-mle-lora' \
  metadata.git_issue_id=tgs-salt-identification-challenge-8seeds \
  solver.execution_timeout=7200 \
  solver.time_limit_secs=86400 \
  solver.num_children=2 \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=4 \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

这里我特意写了一个no memory和reasoning effort为minimal的配置，来保证尽量贴近训练设置。