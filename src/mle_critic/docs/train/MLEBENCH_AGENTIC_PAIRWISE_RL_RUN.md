# MLEBench Agentic Pairwise RL：当前操作流程

本文记录当前仓库实际使用的数据、训练入口和审查方法。所有命令默认从
`aira-dojo-noise-robust` 仓库根目录执行。底层实现见
[方案与实现说明](MLEBENCH_AGENTIC_PAIRWISE_RL_PLAN.md)。

## 1. 当前主线

```text
selected、filtered、runsplit pair + 原始 cards
  -> build_dataset：A/B 随机化、prompt、代码字段、标签
  -> train/test Parquet + 8 pair 的 smoke Parquet
  -> verl：Qwen3.8-27B 多轮推理 + CPU sandbox 工具
  -> 最后一轮 boxed A/B 的 0/1 reward
  -> GRPO 更新与 checkpoint
  -> trace JSONL、可读 Markdown、audit.json
```

当前 launcher 默认只跑一个小批量训练 step：8 个 pair，每个采样 4 次，共 32 条
trajectory。它用于检查完整闭环，不等于跑完一个 epoch。完整数据有 8331 条 train、
1017 条 test；smoke 文件各取原顺序前 8 条，本次训练的 8 条均来自 spooky 任务。

项目仍在试错，脚本和预算会继续调整。本文描述当前激活配置，历史验收以方案文档
中的固定日期记录为准，不应把当前脚本默认值当作所有历史实验的配置。

## 2. 环境与运行前检查

### 2.1 训练环境

```bash
cd /public/hk-research/users/jiqian/zizhe/aira-dojo-noise-robust
source /public/hk-research/users/jiqian/miniconda3/etc/profile.d/conda.sh
conda activate verl
```

训练与数据构建使用 verl 环境。模型工具运行在另外的 sandbox 中，prompt 建议
使用 aira-dojo 环境；激活宿主 verl 不会自动把它变成 agent 的默认环境。

已验证的训练依赖包括 torch 2.10.0+cu128、transformers 5.5.1、vLLM 0.18.0。
模型为 `Qwen/Qwen3.8-27B`，工具格式使用 `qwen3_coder`。本机 checkpoint 缓存
revision 为 `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`。

### 2.2 节点条件

训练默认使用 8 张空闲 GPU。Sandbox 启动端需要 Linux root，以及创建 mount/PID/
network namespace、chroot、切换 UID/GID 和移除 capabilities 所需权限；没有这些
能力时会报启动错误，不会退化成直接执行宿主代码。

可以先进行不启动训练的检查：

```bash
id
nvidia-smi
df -h /tmp .
unshare --mount --net --pid --fork true
ls data/mlebench/spooky-author-identification/prepared/public
```

最后一个目录应有 description.md、train.csv 等公开文件；其余九个任务也须准备好。
完整 model/optimizer checkpoint 本次约 306 GiB，安排存储时应考虑这个量级。

### 2.3 模型缓存

Launcher 在 HF_HUB_CACHE 未设置且本机已有 Qwen3.8 缓存时，使用
`/root/.cache/huggingface/hub`。MODEL_PATH 未设置且找到了 refs/main 与权重索引时，
会将缓存 snapshot 的本地路径交给模型加载器；否则沿用原脚本的 Hub ID 默认值。
模型权重不会被挂给 agent，训练模型缓存与 sandbox 文件视图是两回事。

需要指定其他位置时，在启动命令前设置：

```bash
MODEL_PATH=/绝对路径/完整Qwen3.8模型目录 \
bash src/verl/my_scripts/train/mle_judge/8xh200/run_qwen3_8_27b_agentic.sh
```

下面的 smoke 命令使用 HF_HUB_OFFLINE=1，适用于已经缓存模型的当前节点。
换到未准备权重的节点时先准备模型，或去掉离线设置；不要把修改 MODEL_PATH
理解为已经验证了其他模型的工具 parser 兼容性。

## 3. 构建 agentic 数据

### 3.1 默认输入和命令

必须使用 selected 版本的 pair，而不是名字相近的未 selected 文件：

```text
data/augmented_mle_critic/batch_value_pairs_selected_filtered_runsplit.jsonl
data/augmented_mle_critic/augmented_cards_current.json
data/mlebench/<task>/prepared/public/
```

```bash
python -m src.mle_critic.src.agentic.build_dataset
```

如需明确指定输入、seed 或输出目录：

```bash
python -m src.mle_critic.src.agentic.build_dataset \
  --pairs data/augmented_mle_critic/batch_value_pairs_selected_filtered_runsplit.jsonl \
  --cards data/augmented_mle_critic/augmented_cards_current.json \
  --data-root data/mlebench \
  --output src/verl/data/mle_agentic \
  --seed 7
```

同一输出目录会被重新生成的数据覆盖；保留历史实验时改用新的输出目录。
Builder 不下载竞赛数据，不修复缺失 card，不重做 run split；这些条件不满足时直接报错。

### 3.2 输出是什么

| 文件，位于 src/verl/data/mle_agentic | 用途 |
| --- | --- |
| train.parquet | 完整训练集，当前 8331 条 |
| test.parquet | intask_split=test 的完整保留集，当前 1017 条 |
| smoke_train.parquet | train 原顺序前 8 条 |
| smoke_test.parquet | test 原顺序前 8 条，默认训练不执行 validation |
| manifest.json | seed、输入路径、各 split 数量、任务分布和 A/B 标签分布 |

```bash
cat src/verl/data/mle_agentic/manifest.json
```

数据仅接受 AI4Code、google-quest-challenge、learning-agency-lab-automated-essay-scoring-2、
spooky-author-identification、petfinder-pawpularity-score、whale-categorization-playground、
chaii-hindi-and-tamil-question-answering、dog-breed-identification、random-acts-of-pizza、
tweet-sentiment-extraction。完整任务计数见方案文档。

Prompt 中只有任务、文件位置、原硬件/时间条件和执行要求；代码留在 solution_A/B
字段，运行时写入 sandbox。Ground truth 留在可信 loop 中，不进入模型 prompt。
Train/test 沿用 intask_split，并检查 card endpoint 不交叉。Builder seed 控制 A/B
方向；它与后面 dataloader 的 shuffle seed 是两个独立设置。

## 4. 跑一个完整 smoke step

### 4.1 启动入口

```bash
HF_HUB_OFFLINE=1 RUN_NAME=agentic-smoke-local \
bash src/verl/my_scripts/train/mle_judge/8xh200/run_qwen3_8_27b_agentic.sh
```

使用新的 RUN_NAME，避免把多次运行的轨迹混在一起。也可以省略 RUN_NAME，脚本
会生成含 UTC 时间的名字。无需切到 src/verl；launcher 会自行切换目录并设置
仓库根与 verl 的 PYTHONPATH。因此自定义数据/产物路径优先使用绝对路径。

### 4.2 当前激活配置

| 项目 | 默认值 |
| --- | --- |
| 训练数据 | smoke_train.parquet，8 个 pair |
| train_batch_size / rollout.n | 8 / 4，即每 step 32 条 trajectory |
| PPO mini batch / micro batch per GPU | 8 / 1；内部还受 verl 的 n 和并行设置影响 |
| GPU / rollout TP / sequence parallel | 8 / 4 / 2 |
| 训练策略 | FSDP2，gradient checkpointing，parameter/optimizer offload |
| rollout 显存比例 | 0.6，继承原单轮脚本 |
| prompt / response 上限 | 4096 / 24576 token，response 包含工具 observation |
| agent worker / sandbox slot | 4 / 节点最多 32 |
| sandbox CPU | 初始 affinity 为 2 个逻辑 CPU，非独占物理核或 cgroup 配额 |
| assistant turns / 同轮工具并行数 | 12 / 1 |
| 单条工具 observation | 先按 16000 字符截断，再受 token 预算限制 |
| command / trajectory 时间 | 120 / 1200 秒，trajectory 从 ready 后计时 |
| 总 step / epoch | 1 / 1，step 上限先使训练结束 |
| checkpoint / validation | 每 step 保存；关闭训练前与训练中 validation |
| resume / logger | disable / console |

Actor 学习率沿用 1e-6，不使用 KL reward、KL loss 或 entropy bonus。更改这些
设置属于新的实验配置，应与日志一起记录。

2026-09-20 的参考耗时是 rollout 328.51 秒、actor update 90.12 秒、保存 48.88 秒，
step 合计 530.54 秒；模型和 vLLM 的初始化不计在内。不要用这个单任务小 batch
耗时直接估算全部任务的吞吐。

## 5. 调整参数：改哪里才生效

### 5.1 启动环境变量

| 变量 | 作用 |
| --- | --- |
| RUN_NAME | 默认的实验名、trace/rollout/checkpoint 子目录名 |
| MODEL_PATH / HF_HUB_CACHE | 模型位置 / Hub 缓存根 |
| TRAIN_FILE / TEST_FILE | Parquet 路径 |
| TOTAL_STEPS | 写入 trainer.total_training_steps，默认 1 |
| MLE_DATA_ROOT | sandbox 可读 public 数据的宿主根，默认仓库 data/mlebench |
| MLE_TRACE_DIR | 逐事件 trace 的完整目录，覆盖 RUN_NAME 推导的默认位置 |
| CKPTS_DIR | checkpoint 根目录 |
| PROJECT_NAME / EXPERIMENT_NAME | 训练项目名 / 实验名 |
| GEN_TP / SP_SIZE / ROLLOUT_GPU_MEM_UTIL | 原脚本支持的 TP、sequence parallel、rollout 显存比例 |

若之前手动 export 过 MLE_TRACE_DIR 或 CKPTS_DIR，仅改 RUN_NAME 不会覆盖这些
显式路径。MLE_TRACE_DIR 只控制自定义 trace；标准 rollout 目录由
trainer.rollout_data_dir 控制。

### 5.2 verl 参数：追加 Hydra override

Launcher 最后的命令行参数优先于默认值。例如调整 response 和轮数：

```bash
HF_HUB_OFFLINE=1 RUN_NAME=agentic-budget-probe \
bash src/verl/my_scripts/train/mle_judge/8xh200/run_qwen3_8_27b_agentic.sh \
  data.max_response_length=28672 \
  actor_rollout_ref.rollout.multi_turn.max_assistant_turns=16
```

这是修改方法示例，不是已验收配置。加长上下文会改变显存和耗时；工具输出同样
占 response budget，不能把 max_response_length 全当成模型自由生成的 token。

常改的其他项有 data.train_batch_size、actor_rollout_ref.rollout.n、
actor_rollout_ref.actor.ppo_mini_batch_size、actor_rollout_ref.rollout.agent.num_workers、
actor_rollout_ref.rollout.multi_turn.max_tool_response_length。Batch、n、mini batch
和并行维度需要一起满足 verl 的配置校验；增加 agent worker 不会自动增加样本数。

### 5.3 sandbox 参数：修改单独的 agent_loop.yaml

文件为 `src/mle_critic/recipes/agentic/agent_loop.yaml`，其中 sandbox 部分当前是：

```yaml
sandbox:
  runtime_base: /tmp/mle-agent-sandboxes
  mlebench_data_root: ${oc.env:MLE_DATA_ROOT}
  conda_roots:
    - /public/hk-research/users/jiqian/miniconda3
  command_timeout_s: 120
  trajectory_timeout_s: 1200
  max_output_bytes: 65536
  max_concurrent_sandboxes: 32
  cpu_cores_per_sandbox: 2
```

这是由 agent worker 另外读取的 YAML，不是 trainer 顶层的 sandbox 配置。可以
直接修改这个文件，或复制出实验版本后通过以下 override 指向它：

```text
actor_rollout_ref.rollout.agent.agent_loop_config_path=/绝对路径/实验agent_loop.yaml
```

所有要共享节点 slot 的 run 应使用同一 runtime_base 与一致的池设置。改变 CPU
核数或 command timeout 时，还应同步修改 build_dataset.py 中写死的 prompt
说明并重新生成 Parquet，避免模型得到的预算描述与执行限制不一致。

RLIMIT_NPROC=128、NOFILE=1024、FSIZE=1 GiB、tmpfs 大小目前写在 sandbox_server.py
内，没有对应的可调 YAML 键。网络/GPU 始终关闭；添加 gpu_mode 等草案字段不会
开启设备。详细边界见方案第 7 节。

## 6. 使用全量数据训练与 validation

### 6.1 从头运行更多 step

```bash
HF_HUB_OFFLINE=1 RUN_NAME=agentic-full-100 \
TRAIN_FILE="$PWD/src/verl/data/mle_agentic/train.parquet" \
TEST_FILE="$PWD/src/verl/data/mle_agentic/test.parquet" \
TOTAL_STEPS=100 \
bash src/verl/my_scripts/train/mle_judge/8xh200/run_qwen3_8_27b_agentic.sh \
  data.shuffle=True data.seed=7 \
  trainer.total_epochs=1 \
  trainer.save_freq=20
```

这里显式开启 shuffle，否则继承的 data.shuffle=False 会按原文件顺序读取，短
实验可能主要覆盖排列在前面的任务。改变 TOTAL_STEPS 不会扩大 smoke 文件，
因此更长训练须同时切换 TRAIN_FILE，或明确增加 epoch 来重复已有数据。

如果希望按一个完整 dataloader epoch 决定 step 数，可以用全量 TRAIN_FILE，并
追加 `trainer.total_training_steps=null trainer.total_epochs=1`。当前 train
dataloader 设置 drop_last=True；8331 条、batch=8 时有 1041 个完整 batch，最后
不足 8 条的部分不会组成一个训练 step。显式 TOTAL_STEPS 也不会让 epoch 循环
自动无限延长，要同时给出足够的 trainer.total_epochs。

### 6.2 validation 不会因 TEST_FILE 存在而自动开启

当前默认 trainer.val_before_train=False、trainer.test_freq=-1。要在上面的全量
命令中开启定期评估，可追加：

```text
trainer.test_freq=20
trainer.validation_data_dir=/绝对路径/本次实验/validation
```

需要训练前也评估，再传 trainer.val_before_train=True。本次单 step 验收没有
执行 validation，全量 validation 的耗时尚未由该 smoke run 验证。

test.parquet 来自 frozen intask_split=test 保留集，不是从 train 临时切出的
validation。若用其结果反复调参或选 checkpoint，就已经使用了这份 holdout，
不要再把它当完全未触碰的最终测试集。

### 6.3 恢复训练

默认 resume_mode=disable，每次从原模型开始，不自动继续同名 checkpoint。
恢复时需要显式设置：

```text
trainer.resume_mode=resume_path
trainer.resume_from_path=/绝对路径/实验checkpoint根/global_step_1
```

路径指向 global_step_N 层，不是 actor/huggingface。保持模型、数据与并行配置
兼容，并将总目标 step/epoch 设置到恢复点之后；TOTAL_STEPS 是总目标，不是
额外执行的 step 数。本次已验证保存，但未单独执行 checkpoint 恢复验收。

## 7. Agent 在 sandbox 里如何工作

```text
/workspace/
├── candidate_A/solution.py
├── candidate_A/data -> /mnt/data
├── candidate_B/solution.py
├── candidate_B/data -> /mnt/data
├── data -> /mnt/data
└── scratch/
```

工具 bash 可以读 /mnt/data、执行小型代码检查；text_editor 的 view/create/
str_replace/insert 只处理 workspace 内路径。Editor 无法直接查看 /mnt/data，
应改用 bash。需要看长代码时使用 sed 按段读取，反复 view 整个大文件只会重复
拿到被截断的开头。

每次 shell 都从 /workspace 重新开始，cd、环境激活不跨调用保留，文件会保留。
模型需要在同一 command 内执行 source、conda activate aira-dojo 和 Python。
整个 trajectory 结束时文件、cache、后台进程一起清理，不会保留探针或 submission。

无需也不应让 agent 跑 private evaluator。它的任务是利用有限反馈比较两份方案，
最后输出一个 `\boxed{A}` 或 `\boxed{B}`。Reward 只读最后一轮 assistant：
正确为 1，错误、冲突、缺失答案为 0，不会把工具返回的 boxed 当成判断。

## 8. 查看训练和推理结果

### 8.1 默认产物目录

| 路径 | 内容 |
| --- | --- |
| src/verl/logs/qwen3_8-27b-时间戳.log | 配置、初始化、step 指标、错误 |
| src/verl/outputs/RUN_NAME/traces/*.jsonl | 每轮 assistant、工具参数与结果、reward、token mask、清理事件 |
| src/verl/outputs/RUN_NAME/rollouts/1.jsonl | verl 第 1 step 的标准 rollout dump，后续按 step 命名 |
| src/verl/checkpoints/PROJECT_NAME/RUN_NAME/global_step_N/ | 训练 checkpoint |

### 8.2 生成可读审查文件

对应第 4 节的 run：

```bash
python -m src.mle_critic.src.agentic.audit_traces \
  src/verl/outputs/agentic-smoke-local/traces
cat src/verl/outputs/agentic-smoke-local/audit.json
```

Audit 在 trace 旁写同名 Markdown，在 trace_dir 的父目录写 audit.json。
输入应该是本次 run 的单独 trace 目录；若混入训练、validation 或多次 run，统计
也会合并，分组依据仍是 sample_uuid，不会自动按训练 step/validation 分开。

建议按这个顺序审查：先看 audit 的 completed/closed/valid_answers/correct；
再选一条 .md 查看两份代码是否读到、做了什么诊断；最后在 JSONL 对照原始
result、实际 observation、最终答案和 token mask。Model token mask 为 1，
observation 为 0。Start 中的 solution SHA-256 可与 Parquet 代码核对。

Completed 表示 trace 有 result，closed 表示记录了 runtime_removed=True，
不等于 audit 已独立检查所有进程。工具错误可能是模型探针出错或被隔离拒绝，
不必然等于训练失败。原始 JSONL 是更完整的审查依据。

### 8.3 怎样确认“真的训练了一步”

检查训练日志中 training/global_step、actor/grad_norm、actor/lr 与 update_actor
用时；再检查 latest_checkpointed_iteration.txt、global_step_N 下的 model/
optim/extra_state shard 和标准 rollout dump。单看 audit 的 reward 不能证明
做过 optimizer 更新。

默认 checkpoint 包含 8 卡 model、optimizer、extra_state 和 Hugging Face 配置，
不是一个可以直接当完整 HF safetensors 模型使用的 actor/huggingface 目录。
原脚本还设置 max_actor_ckpt_to_keep=1，长训练会轮换旧 checkpoint；需要保留更多时
显式覆盖 trainer.max_actor_ckpt_to_keep。

## 9. 常见问题与排查方向

| 症状 | 当前解释与处理 |
| --- | --- |
| Ray AF_UNIX path 超过 107 bytes | Launcher 已设 TMPDIR/RAY_TMPDIR=/tmp；绕开 launcher 时也要检查临时路径 |
| Qwen tokenizer 找不到缓存 | 确认激活环境后的缓存根；本机使用 /root/.cache/huggingface/hub |
| 离线加载抱怨缺 README/LICENSE | 使用完整模型文件所在的本地 snapshot 路径，launcher 已对本机缓存做此处理 |
| Sandbox startup failed / EPERM | 检查 root、namespace/chroot/降权能力；不要绕开 sandbox 改成直接执行 |
| Editor paths must stay under /workspace | /mnt/data 包括 workspace/data 的解析结果都不在 editor 范围；用 bash 读公开数据 |
| 探针 import 失败 | 同一 command 激活 aira-dojo；依赖未挂入仓库源码的 editable package 仍可能不可用 |
| Hugging Face 下载重试/失败 | Sandbox 无网络，也不共享宿主模型 cache；应改做不依赖下载的诊断 |
| 输出不完整 | 同时存在字节、字符和 token 限制；用 head、sed、nrows 等减少输出 |
| 没有最终 boxed | 检查 response 总量和 assistant turns；observation 也占预算，当前没有最终回答保留预算 |
| reward 组内全一样 | GRPO 相对优势缺少信号；同时检查格式失败、样本难度和采样分布 |
| 整个 batch 因 trajectory 超时退出 | 总超时目前上抛异常；与返回 timed_out observation 的单命令超时不同 |

2026-09-20 的 run 有 14/32 条没有有效最终答案，其中 8 条耗尽 token，6 条达到
轮数上限；这是真实配置限制，不应从准确率分母中直接忽略。完整结果见方案第 12 节。

退出阶段可能出现 resource_tracker KeyError、_recursion_count 或 vLLM engine
关闭日志。先确认训练退出码、step/checkpoint/dump 是否完整，再检查 GPU 和 runtime；
不要仅凭一条清理日志判成功或失败。uid-locks 里的锁文件正常保留，不能据此判断
有活动 sandbox，也不要在训练期间通过删除锁文件来“释放 slot”。

## 10. 回归测试与实验记录

激活 verl 环境，在有 namespace 权限的节点从仓库根目录运行：

```bash
HF_HUB_CACHE=/root/.cache/huggingface/hub \
PYTHONPATH="$PWD/src/verl:$PWD" \
python -m pytest \
  src/mle_critic/test/test_agentic_sandbox.py \
  src/mle_critic/test/test_agentic_loop.py \
  src/mle_critic/test/test_agentic_dataset.py -q
```

Loop 测试使用实际缓存的 Qwen3.8 tokenizer、确定性回复和真实 sandbox，不加载
27B GPU 模型。数据测试读取真实 selected pairs/cards；另需第 4 节的训练 run
才能验证真实模型推理与梯度更新。当前 14 项测试与一次真实 step 都已通过。

每次实验至少保存：输入 pair/card 与生成 Parquet 的版本、manifest/seed、模型
revision、训练命令和代码版本、launcher/agent_loop/tools 配置、训练日志、trace、
audit 和 checkpoint 路径。修改 SYSTEM_PROMPT 后要重建 Parquet；否则运行的仍是
旧数据内已经保存的 prompt。方案文档的历史验收指标不随新实验自动更新。
