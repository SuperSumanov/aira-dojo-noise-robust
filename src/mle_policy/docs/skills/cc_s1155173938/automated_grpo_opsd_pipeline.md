---
name: automated-grpo-opsd-pipeline
description: 在 cc_s1155173938 的训练环境中，用已收集的 MLE journal 完成每日 GRPO、hindsight 生成、OPSD、LoRA 导出和打包，并持续监控和处理运行故障。用户要求执行这套管线或继续某一轮时使用。
---

# 每日 GRPO → hindsight → OPSD → LoRA 包

用户准备好一天的 journal 后，执行并监控到最终压缩包可交付。以
`data/augmented_mle_critic/raw_journal/wh/1112` 为例。本文按用户指定位置保存；
日后可以让 agent「读取本文件，执行某任务某天的管线」。需要自动技能发现时，再将本文作为技能目录中的 `SKILL.md` 安装。

## 1. 确定这一轮的参数和状态

从仓库根目录开始，读取根目录 `AGENTS.md` 和将使用的脚本。下面的路径以实际脚本为准，
运行时确认版本；本文记录的是 2026-11-16 核对过的行为。

```bash
REPO=/auxstore/cse/d10/data/s1155173938/aira-dojo-noise-robust
INPUT_ROOT="$REPO/data/augmented_mle_critic/raw_journal/wh/1112"
OUT_ROOT="$REPO/data/mle_policy/dataset/basic/1112"
PAIRS="$REPO/data/mle_policy/opsd/1112/pairs.jsonl"
OUTPUT_ROOT="$REPO/outputs/wh-chaii-metric"
MODEL_PATH=Qwen/Qwen3.8-27B
NPROC_PER_NODE=2
cd "$REPO"
```

这些变量在宿主机和每个新容器 shell 中分别设置。shell 变量不会自动穿过 `--cleanenv`。
`wh/1112` 和 `wh-chaii-metric` 是本例的对应关系；其他任务沿用用户已有的任务名和输出目录。
若给了输入但任务目录无法从上下文确定，先检查 journal 的任务名和已有 outputs，再询问缺少的映射。
日期目录继续采用 `1112` 这样的简单名称。GRPO parquet 固定覆盖
`src/verl/data/mle_policy_grpo/thinking`，同一工作区串行处理不同任务。

启动前记录：输入、任务、日期、节点、分配到的 GPU 型号/数量/可见编号、容器、驱动兼容方式、
本轮初始 adapter、训练参数和日志位置。用 `nvidia-smi`、现有进程、磁盘与内存余量核实资源。
使用当前 allocation；节点或 GPU 尚未分配时，需要用户提供 allocation。

轮次按本任务的 `$OUTPUT_ROOT/opsd` 判断：

- 目录不存在或确实为空：首轮 GRPO，从底模开始。
- 有完整的 `lora_adapter/adapter_config.json` 和 `adapter_model.safetensors`：后续轮，从该 adapter 开始。
- 目录非空但 adapter 不完整：先查上轮记录和产物，恢复完整 adapter 后继续；避免把损坏的上轮当首轮。

LoRA 接续关系固定为：上轮 OPSD adapter → 本轮 GRPO → `basic/lora_adapter` → 本轮 OPSD。
hindsight 提炼始终使用原始 `Qwen/Qwen3.8-27B`，每轮相同。

把运行记录和日志放在 `$REPO/logs/mle_policy/pipeline/<任务>/<日期>/`，
用一个 `status.md` 记录当前阶段、启动命令、PID/进程会话、日志、退出状态、有效步数、耗时、
修复内容和下一步。收到“继续”时先核对记录和存活进程，再接着运行。
持续执行已授权流程，常规重试和工程修复直接处理；改变奖励、模型、训练轮数等实验设置时与用户确认。

无人值守启动前确认宿主工具的审批策略，并预先授权明确范围的派生数据/checkpoint 清理。
会话内的文字授权与工具的自动审批是两层机制，skill 无法覆盖工具审批。
可选清理失败时记录原因，先检查固定 CKPTS_DIR 是否有旧数据；能用
`trainer.resume_mode=disable` 安全启动时继续。必须清理才能继续的操作应在有人值守的准备阶段完成。
遇到工具审批暂停时不能靠换成另一种删除命令绕过审批。

## 2. 准备 GRPO 数据（宿主机，aira-dojo）

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
cd "$REPO"
mkdir -p "$OUT_ROOT"
bash src/mle_policy/scripts/data/build_all_batches_bigjournal.sh "$INPUT_ROOT" "$OUT_ROOT"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/assign_splits.sh "$OUT_ROOT" run 0.1
bash src/mle_policy/scripts/data/to_grpo_metric.sh "$OUT_ROOT"

cd "$REPO/src/verl"
python my_recipes/mle_policy/src/dataset/build_grpo_parquet.py \
  --input "$OUT_ROOT/thinking/grpo.jsonl" \
  --output-dir data/mle_policy_grpo/thinking \
  --model-path "$MODEL_PATH" \
  --max-length 65536 \
  --enable-thinking true \
  --reasoning-effort medium
```

逐条检查退出状态并保留日志。若用 `tee`，在外层 shell 启用 `set -o pipefail`。
重新从头生产时，先清空本轮的 `$OUT_ROOT` 和固定 parquet 输出目录，再运行，避免聚合进旧 batch。
覆盖这些便宜的派生数据已有授权；核实绝对路径后定点清理。

数据阶段必须检查以下实际行为：

- `build_all_batches_bigjournal.sh` 通过 `JOURNAL.jsonl` 上溯到含 `dojo_config.json` 的 run，
  再以其父目录为 batch。它遇到单个 batch 失败会打印 `FAILED` 并继续，最终仍可能返回 0。
  核对发现的 batch、成功的 manifest 和 `$OUT_ROOT/.staging/*.log.json`；脚本清除 staging 目录后这些日志仍保留。
  解决失败并补齐 batch 后再聚合。发现 journal/config 损坏时定位到具体来源；无法修复的输入交用户处理。
- 若出现 `Duplicate step N in journal`，按该 journal 的原始行顺序保留每个 step 首次出现的 node，
  直接删除后面相同 step 的重复 node。这是用户授权的重试数据清理规则；按文件分别去重，
  保留其余行的顺序和内容，不重新编号 step。记录来源文件、删除的行号/step 和数量，
  确认 step 唯一后重跑失败的 batch，补齐 manifest 再聚合。
- 默认只有 `selfhosted` provider 被归为 `thinking`。若 thinking 为空，检查真实 provider 和 manifest，
  确认都是目标模型的思考数据后再设置 `THINKING_PROVIDERS`；按模型和来源判断分类。
- 保持 run 级 10% 验证集和 metric reward。检查 split、任务、provider、有效组与过滤数量，
  尤其是零方差组、非有限 reward/advantage、大量样本丢弃；数据非空才能继续。
- 检查 `conversion_report.json` 和两份 parquet 的实际行数、sample_id 唯一性、response 非空、
  token 长度及有限数值。转换限制的是 prompt + response 总长 65536；分别统计两列最大长度。
  当前自定义 `MlePolicyGRPODataset` 直接读取 token，未按脚本中的 32768/32768 再过滤。
  因此这些默认值不能当作已有数据的长度保证；根据真实长度核查显存和配置，保留完整回答。
- 两种训练的 DataLoader 当前均 `drop_last=True`，每轮步数通常为
  `floor(训练行数 / TRAIN_BATCH_SIZE) × TOTAL_EPOCHS`。小数据不足一个 batch 时，
  将 batch 调成能执行至少一步、且满足 GPU/并行整除约束的大小，记录丢弃尾部行数。

## 3. 容器和 /tmp

使用根 `AGENTS.md` 的 Singularity 镜像、绑定和环境。agent 自动运行时使用
`singularity exec ... bash -lc '...'`，与手动 shell 相同；长进程通过持久会话或
`nohup`/现有作业管理器托管，保存 PID、完整日志和退出码，确保工具调用结束后继续运行。

容器启动模板，宿主机执行：

```bash
SIF=/auxstore/cse/d10/data/s1155173938/singularity_images/verl_vllm.sif
CUDA_ENV=()
# CUDA 12.9 节点执行此行；CUDA 13.0 节点保持数组为空。
# CUDA_ENV=(--env 'LD_LIBRARY_PATH=/usr/local/cuda/compat:$LD_LIBRARY_PATH')
singularity shell --nv --cleanenv \
  --env PYTHONUSERBASE="$REPO/src/verl/verl_env/packages" \
  --env 'PATH=/opt/nodejs/bin:$PATH' \
  "${CUDA_ENV[@]}" \
  -B "$REPO/src/verl:/workspace/verl" \
  -B /auxstore/cse/d10/data/s1155173938:/auxstore/cse/d10/data/s1155173938 \
  -B /auxstore/cse/d10/data/s1155173938/software/nodejs:/opt/nodejs \
  -B /auxstore/cse/ssd/s1155173938:/tmp \
  "$SIF"
```

依据节点配置和容器内 CUDA 初始化结果确定 12.9/13.0 模式；`nvidia-smi` 顶部的 CUDA 值表示驱动支持上限。
保留 allocation 的 GPU 可见性限制，并核实容器内只使用分配的 GPU。
从 `AGENTS.md` 设置 ulimit、缓存目录、`WANDB_MODE=offline`、
`VLLM_WORKER_MULTIPROC_METHOD=spawn` 等环境。密钥从现有配置读取，在关闭命令回显时注入；
运行记录只保存变量名。示例训练脚本带 `set -x`，避免通过命令参数输出凭据。
需要访问 Hugging Face 时显式传入容器所需的现有 token；`--cleanenv` 会清除宿主机环境。

容器内从 `$REPO/src/verl` 运行训练，使用仓库绝对路径可减少工作目录差异。
检查当前 `transformers`/`peft` 组合。continue 脚本注明 Transformers 5.18.0 overlay
配 PEFT 0.21.2；确实遇到版本兼容问题时按该说明修复当前训练环境并记录。

每次开始新的训练前，检查宿主机 `/tmp` 和容器 `/tmp` 的旧训练 checkpoint。
容器 `/tmp` 实际是宿主机 `/auxstore/cse/ssd/s1155173938`，与宿主机 `/tmp` 分开核对。
清理已结束旧训练的 checkpoint 目录，包含本次明确指定的 CKPTS_DIR 和旧实验留下的分片；
先确认无进程使用且需要的 adapter 已导出。保留正在运行/准备恢复的训练、上轮 OPSD adapter、
模型缓存和其他临时服务文件。用实际路径、进程和占用空间列出清理对象后定点删除。

底模沿用现有 HF 缓存；新增大模型副本、checkpoint 和完整导出统一落容器 `/tmp`。
按 checkpoint 分片、完整模型导出和 OPSD token_scores 估算磁盘与 CPU 内存需求，给导出阶段留出余量。

## 4. GRPO 训练、监控和导出

容器内重设第 1 节的路径和 GPU 数量，运行：

```bash
cd "$REPO/src/verl"
export MODEL_PATH=Qwen/Qwen3.8-27B
export NPROC_PER_NODE=2                # 使用实际分配的 2 或 4
export TRAIN_BATCH_SIZE=128 PPO_MINI_BATCH_SIZE=128
export TOTAL_EPOCHS=1 SP_SIZE=1 FSDP_SIZE=-1
export CKPTS_DIR=/tmp/GRPO-mle-policy-offline/current
export EXPERIMENT_NAME=GRPO-offline-Qwen3.8-27B-thinking
# LOG_FILE 指向本轮日志目录中的 grpo.log。

# 首轮：
bash my_scripts/train/mle_policy/2xh200/run_qwen3_8_27b_grpo_thinking_fsdp_lora.sh

# 后续轮只运行下面这一条，并使用本任务上轮的原始 adapter：
# LORA_ADAPTER_PATH="$OUTPUT_ROOT/opsd/lora_adapter" RESUME_MODE=disable \
# bash my_scripts/train/mle_policy/2xh200/run_qwen3_8_27b_grpo_thinking_fsdp_lora_continue_metric.sh
```

实际只执行所选的一条命令。后续轮核对 adapter 的 rank/alpha，默认 128/256，
保持底模为 `Qwen/Qwen3.8-27B`。通过 adapter 加载上轮权重，optimizer/scheduler 本轮重新开始。
初始脚本默认 `resume_mode=auto`，因此新轮开跑前必须清理本轮 CKPTS_DIR；
也可在末尾显式传 `trainer.resume_mode=disable`。继续同一轮故障前先检查 trainer 的恢复实现、
checkpoint/dataloader 状态和原始输入，满足恢复条件才用 auto；上轮接续与同轮恢复分开处理。

### GPU 调整

| 场景 | 调整原则 |
| --- | --- |
| 2 张 H200 | 采用上面的 2xh200 脚本，microbatch=1，保留脚本 offload 设置 |
| 4 张 H200 | 沿用同一脚本并设 `NPROC_PER_NODE=4`、`FSDP_SIZE=-1`，先保持全局 batch=128、1 epoch；根据实测逐步减少 offload 开销 |
| Pro6000 等较小显存卡 | 核查对应硬件脚本和当前 GPU 架构支持；保持 microbatch=1、offload，长序列先验证显存 |

当前 `4xh200` GRPO 首轮脚本默认模型是旧的 `outputs/seqsup-score-day6`，batch=64、3 epochs。
优先用用户指定的 2xh200 脚本配环境覆盖，避免继承旧实验设置。
多卡首先增加并行吞吐，保持 LR、全局 batch、epoch 和 LoRA 结构。
需要关闭 offload 时，用脚本末尾的 Hydra 参数覆盖实际 actor/ref 配置，观察至少一个完整更新再决定保留。
更小 batch 只解决数据不足或内存问题，记录其带来的步数变化。
GRPO 和 OPSD 保持 `use_remove_padding=False`、动态打包关闭、每卡 microbatch=1。
OOM 时先检查计算中间量、checkpoint 和并行配置，实测这些优化后才考虑缩短上下文。
activation offload 默认关闭；仅在其他优化不足且接受速度损失时考虑启用。

### 监控到真正完成

先守到模型加载、GRPO 初始策略 log-probability 缓存结束，且至少一个 optimizer step 成功。
缓存阶段也可能很长，结合其进度而非“尚无训练 step”判断停滞。
记录实际总步数和每步时间，用最近几步估算剩余训练时间，并加上验证、保存耗时。
OPSD 另计每步生成时间。小样本和长序列的耗时差别很大，以实时日志为准。

确认正常后按实测耗时长时间 sleep，接近预计完成时再检查。优先使用可被新消息打断的
`clock.sleep`，一次可以等待几十分钟或数小时；常规 shell 阻塞等待保持短时。
每次醒来核实进程、日志进度、GPU/磁盘、退出码。监控持续到最终包验证完成。
异常时先保存 traceback 和关键配置，定位 OOM、NCCL、版本、长度或磁盘问题，
进行对应修复；同一错误在相同修复后再次出现则停止重复启动并报告具体阻塞。

以日志中的总步数、正常退出码和最终 checkpoint 三者确认训练完成。
`global_step_13` 仅是例子；从本轮实际目录读取数字步数和
`latest_checkpointed_iteration.txt`，按数字选择最终步，核对 actor 的 `fsdp_config.json`、
应有的 model rank 分片、HF 配置与 `lora_train_meta.json`。训练退出且保存完成后再合并。
当前两种 trainer 都在最后一步保存，即使最后一步不是 SAVE_FREQ 的倍数。

### 导出 basic

merger 会同时写完整底模和 `lora_adapter`，先输出到 `/tmp`：

```bash
cd "$REPO/src/verl"
# GRPO_ACTOR 设置为本轮最终 global_step_<实际步数>/actor 的绝对路径。
python -m verl.model_merger merge \
  --backend fsdp \
  --local_dir "$GRPO_ACTOR" \
  --target_dir /tmp/mle_policy_export/basic
```

合并前清理该临时导出目录的旧内容。检查新 adapter 的配置、张量能完整读取、
权重有限、rank/alpha 与本轮相符；alpha=0 或缺失应追查 checkpoint 元数据。
验证成功后删除 `$OUTPUT_ROOT/basic` 的旧内容，创建目录，只复制
`/tmp/mle_policy_export/basic/lora_adapter` 到 `$OUTPUT_ROOT/basic/lora_adapter`。
这样保留用户约定的路径，完整模型留在 `/tmp`，下游始终用底模 + adapter。
导出验证并完成复制后可以释放 GRPO checkpoint 和临时完整导出，给 OPSD 留空间。

## 5. 用原始底模生成 hindsight

确认 GRPO 训练及其 GPU 子进程已经退出，再启动独立 vLLM 服务。
下面宿主机命令沿用第 3 节的 `SIF`、`CUDA_ENV`；2 张卡的 TP=2。
四卡先尝试 TP=4，核实模型注意力头和服务版本支持；若不支持则 TP=2。
以能成功加载的配置为准。服务只加载原始底模。

```bash
singularity exec --nv --cleanenv \
  --env PYTHONUSERBASE="$REPO/src/verl/verl_env/packages" \
  "${CUDA_ENV[@]}" \
  -B "$REPO:/workspace/aira-dojo-noise-robust" \
  -B /auxstore/cse/d10/data/s1155173938:/auxstore/cse/d10/data/s1155173938 \
  -B /auxstore/cse/d10/data/s1155173938/software/nodejs:/opt/nodejs \
  -B /auxstore/cse/ssd/s1155173938:/tmp \
  "$SIF" bash -lc '
    cd /workspace/aira-dojo-noise-robust/src/verl
    python -m vllm.entrypoints.openai.api_server \
      --model Qwen/Qwen3.8-27B \
      --served-model-name qwen3.8-27b \
      --tensor-parallel-size 2 \
      --max-model-len 131072 \
      --max-num-seqs 64 \
      --gpu-memory-utilization 0.95 \
      --host 0.0.0.0 --port 8000 \
      --api-key sk-vllm-gpu27-qwen38-27b
  '
```

若两卡间无nvlink则优先考虑多instance+router，比如脚本

```bash
bash src/mle_policy/scripts/data/hindsight/vllm_router.sh &
```

把服务托管在独立持久会话，保存日志和 PID。启动前确认 8000 端口归属；
等待带认证的 `/v1/models` 返回 `qwen3.8-27b`，再做一条 chat completion 验证。
容器中补齐与训练相同的缓存等环境，避免重复下载。

生成在宿主机 `aira-dojo` 环境、仓库根目录执行：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
cd "$REPO"
export PYTHONPATH="$PWD/src:$PWD/src/verl${PYTHONPATH:+:$PYTHONPATH}"
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
export PRIMARY_KEY_QWEN3_8_27B=sk-vllm-gpu27-qwen38-27b
python -m my_recipes.mle_opsd.build_dataset \
  --input "$INPUT_ROOT" \
  --output "$PAIRS" \
  --base-url http://127.0.0.1:8000/v1 \
  --model-id qwen3.8-27b
```

`build_dataset` 通过 dojo 的 LiteLLM backend 发请求；这里只覆盖 model-id 和 base-url。
认证读取 `PRIMARY_KEY_<模型名转大写且点号/连字符换成下划线>`，其次 `PRIMARY_KEY`，
因此显式设置上述本地服务 key，避免继承源 journal 的远端凭据。

默认并发为 4；显存有余量但吞吐不足时逐步提高 `--concurrency`，观察吞吐、排队和错误率。
KV cache 不足时先降低服务并发/`max-num-seqs`；确需减少 131072 上限时先测实际提炼输入长度。

`pairs.jsonl` 是追加式断点缓存，以 sample_id 跳过已完成项；故障后沿用同一路径重跑。
sample_id 包含 journal 的绝对路径，同一轮继续使用同一个宿主机路径。
检查输出 JSON 完整、ID 唯一、prompt 合法、`hindsight_context` 非空、hint_model 为指定底模。
异常退出留下尾部不完整行时，只修复该尾行后继续；正常数据保留。
完整运行退出成功后，同样命令再跑应为 `extracting 0 hints`，这是候选项已经生成完的核对。
记录初始候选总量、最终有效行数和耗时。生成数为零时检查输入树是否有合格节点。

生成结束后停止本轮独立 vLLM 服务及其 worker，核实端口和 GPU 显存已释放。
OPSD 训练自己启动 rollout 引擎，需要使用这些 GPU。

## 6. OPSD 训练

在相同训练容器中，从 `$REPO/src/verl` 运行。训练前完成第 3 节的旧 checkpoint 清理，
保留本轮 `basic/lora_adapter` 和上轮 OPSD adapter，直到新一轮导出完成。

生成结束后在相同 tokenizer 环境中进行长度过滤，保留 `pairs.jsonl` 作为生成缓存，
训练文件固定写到同目录 `train.jsonl`。OPSD 在线生成回答，按 response 上限预留长度；
同时检查 student / teacher prompt 上限及两种完整序列预算，超限样本整行过滤：

```bash
cd "$REPO/src/verl"
python -m my_recipes.mle_opsd.filter_dataset \
  --input "$PAIRS" \
  --output "$(dirname "$PAIRS")/train.jsonl" \
  --model-path Qwen/Qwen3.8-27B \
  --max-prompt-length 24566 \
  --teacher-max-prompt-length 24566 \
  --max-response-length 32768 \
  --max-length 57334 \
  --enable-thinking true --reasoning-effort medium
```

查看 `train.report.json` 中输入/保留/过滤数量、长度分布和超限 sample_id，
按过滤后的行数计算步数。模板由 `dataset.prompt_token_ids` 与训练共享。
训练的长度配置应与过滤一致。过滤默认沿用原脚本的 24566/32768/57334 上限，
这样只剔除无法放入训练预算的样本，不主动缩短上下文。

```bash
cd "$REPO/src/verl"
TRAIN_FILE="$(dirname "$PAIRS")/train.jsonl" \
CKPTS_DIR=/tmp/mle_opsd \
MODEL_PATH=Qwen/Qwen3.8-27B \
TEACHER_MIX_COEF=0.01 \
LORA_ADAPTER_PATH="$OUTPUT_ROOT/basic/lora_adapter" \
NPROC_PER_NODE="$NPROC_PER_NODE" \
TRAIN_BATCH_SIZE=128 \
TOTAL_EPOCHS=1 \
MAX_PROMPT_LENGTH=24566 TEACHER_MAX_PROMPT_LENGTH=24566 \
MAX_RESPONSE_LENGTH=32768 MAX_TEACHER_LENGTH=57334 \
USE_REMOVE_PADDING=False \
bash my_scripts/train/mle_opsd/pro6000/run_qwen3_8_27b_opsd_fsdp_lora.sh
```

按真实数据量调整不足一个 batch 的情况。脚本的 minibatch 跟随 TRAIN_BATCH_SIZE，
保持每个新 rollout batch 只做一个 minibatch、一个 PPO epoch。
此处显式使用 `TEACHER_MIX_COEF=0.01`，覆盖部分旧文档中的 0.05。
`VAL_FILE` 默认等于训练文件，当前 OPSD 不运行独立验证循环，记录时按这一实际行为描述。

默认 OPSD rollout TP=1；27B 在目标显存上无法容纳时设 `ROLLOUT_TP=2`，
四卡可比较 TP=2 的两组与 TP=4 的一组吞吐，并确保整除 GPU 数。
H200 可对比 `mle_opsd/2xh200` 配置，先核对差异再采用。
优先保留 batch、LR、epoch 和 teacher 系数，调整并行和显存配置以适配 allocation。

按第 4 节持续监控；另看 `metrics.jsonl` 中的 step、损失/梯度有限性、teacher score gap、
回答长度与截断比例，确认从 basic adapter 加载并发生有效更新。
`responses.jsonl` 和 `token_scores/` 会额外占空间，纳入 `/tmp` 容量监控。
默认 `resume_mode=disable`；故障恢复前检查当前 trainer 如何恢复步数和 dataloader，
确认恢复语义正确再覆盖配置；否则从本轮 basic adapter 清理重跑并记录。

## 7. 导出、整理、打包

训练正常结束后，按同样的最终步数/分片规则确定 `OPSD_ACTOR`，先在 `/tmp` 合并：

```bash
cd "$REPO/src/verl"
python -m verl.model_merger merge \
  --backend fsdp \
  --local_dir "$OPSD_ACTOR" \
  --target_dir /tmp/mle_policy_export/opsd
```

清理临时导出目录的旧内容后运行；核实新 adapter 可读取、数值有限、rank/alpha 正确。
验证成功后替换 `$OUTPUT_ROOT/opsd`，只复制新 `lora_adapter`，保留原始 adapter 供下一轮继续训练。
替换前确认上轮 adapter 已完成本轮 GRPO 加载，且没有其他训练正在读取它。

回到仓库根目录，在有 torch/safetensors 的环境执行：

```bash
cd "$REPO"
bash src/mle_policy/scripts/export/prune_lora_adapter_for_vllm.sh \
  "$OUTPUT_ROOT/opsd/lora_adapter"
tar -czf "$OUTPUT_ROOT/opsd/lora_adapter_vllm.tar.gz" \
  -C "$OUTPUT_ROOT/opsd" lora_adapter_vllm
tar -tzf "$OUTPUT_ROOT/opsd/lora_adapter_vllm.tar.gz"
sha256sum "$OUTPUT_ROOT/opsd/lora_adapter_vllm.tar.gz"
```

prune 脚本移除 vLLM 不支持的视觉塔 LoRA 张量，产物为 `lora_adapter_vllm/`。
它会检查待丢弃视觉 LoRA B 是否为零；检查失败时保留异常证据并处理，完整语言 adapter 必须保留。
当前训练已排除 visual，移除零个视觉张量也是正常结果。
原始 `lora_adapter` 用于接续训练，`lora_adapter_vllm` 用于服务。
压缩包只包含后者，检查归档路径、config 和 safetensors，并在临时目录解包验证张量可读取。

最后更新 status.md，交付：输入和任务、初始 adapter、两阶段实际样本数/步数/耗时、
使用的 GPU 和调整参数、故障修复、最终两个 adapter 的绝对路径、tar.gz 大小和 SHA256、日志路径。
确认本轮进程结束，保留尚需排查的 checkpoint，其余已导出的大文件按空间需要清理。
完成标准是压缩包验证成功并交给用户安排发布。
