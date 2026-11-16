# MLE hindsight OPSD

从 `Qwen/Qwen3.8-27B` 底模直接验证。数据来自仓库根目录的
`data/augmented_mle_critic/raw_journal/wh/1112`。

本文说明数据准备、训练、导出与检查。实现细节、实验结果和调参建议见
[实现与实验经验](IMPLEMENTATION.md)；逐次运行记录保留在仓库根目录
`tmp/opsd/EXPERIMENTS.md`。当前按探索性实验接入 online，完整答案的交付能力仍需持续评测。

## 1. 提炼经验

在 `aira-dojo` 环境中、从仓库根目录运行：

```bash
export PYTHONPATH="$PWD/src:$PWD/src/verl${PYTHONPATH:+:$PYTHONPATH}"
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
python -m my_recipes.mle_opsd.build_dataset \
  --input data/augmented_mle_critic/raw_journal/wh/1112 \
  --output outputs/opsd/pairs.jsonl \
  --base-url http://127.0.0.1:18451/v1 --model-id qwen3.8-27b
```

程序复用原有 hindsight 的经验提炼提示词，覆盖已修好的 debug 链中每个待修节点，
以及有更优子方案的节点。每行保存原始 `prompt`、`hindsight_context`、节点来源、
提炼请求与结果。它只生成经验，不生成训练回答。重复运行复用同一 JSONL 中已完成的行。
`--limit` 可限制本次新增行数；评测集按来源 journal/run 分开构建。

## 2. 当前学生生成

学生只看到原始输入，使用当前权重生成完整 reasoning 和代码。
每批生成后更新一次权重，下一批重新生成。启动脚本用 temperature=1、top_p=1、
top_k=-1，使采样参数与训练概率计算一致。vLLM 与训练引擎的数值差异另行监测。

## 3. Trust-region teacher 打分

生成后、更新前，用同一个 actor worker group 顺序做三遍无梯度前向：

- 原始 prompt + 学生回答，得到学生逐 token log probability。
- 在原始 prompt 的 response-format 段前插入经验，再接同一串学生 token，开启 LoRA 评分。
- 同一个带经验输入，临时关闭 LoRA，用冻结底模评分。

teacher 在冻结底模与当前 actor 之间插值，`TEACHER_MIX_COEF` 是当前 actor 的权重：

```text
teacher_score = (1 - alpha) * log_p_base_with_hint + alpha * log_p_actor_with_hint
```

默认 `alpha=0.05`，是本 recipe 的实验起点。`0` 是固定底模教师，`1` 恢复原来的当前模型教师。
两遍教师前向都使用同一份经验、同一串回答和相同 temperature；不复制模型或维护 EMA。
若从已有 adapter 继续训练，冻结端仍是关闭 LoRA 后的原始底模，而不是启动时的 adapter。
回答不经过 decode/re-tokenize，首 token、EOS、padding 和回答 mask 按原位置保留。
长度超限直接报错。

SDPO 官方 `TrustRegionTeacher` 对完整 logits 插值后归一化。本实现保留 fused kernels，
只插值采样到的 token log probability，省掉一个随前缀变化、与当前 token 无关的
归一化项。在当前单次 on-policy、stop-gradient、无裁剪的 `gpg` 损失下，这个差值是
baseline，期望梯度与归一化后的 logits 插值教师相同；有限采样的方差可以不同。
插值结果记为 score，不作为归一化的 teacher log probability 或精确 KL 使用。

## 4. 更新学生

每个学生生成 token 的信号为
`advantage = stop_gradient(teacher_score - log_p_student)`。
调用 verl 已有的 `gpg` loss：`-advantage * log_p_student_current`，只统计回答 token。
这是在学生前缀上的逐 token sampled reverse-KL 梯度估计；不把单个样本的 log ratio
当成精确 KL，也不累加成整条序列的奖励。

每批只有一个 optimizer minibatch、一个 epoch，microbatch 只用于梯度累积。
本机 Qwen 混合注意力实现未为打包后的线性注意力提供样本边界；启动脚本固定
每张卡每次前向一个样本，训练、学生打分和底模打分均关闭动态打包。
没有 PPO clipping、组内归一化、任务得分奖励或单独的 critic。
`src/verl/tests/recipes/test_mle_opsd.py` 用完整小词表验证该估计的期望梯度与 reverse KL 一致。

从 `src/verl` 运行：

```bash
TRAIN_FILE=/absolute/path/pairs.jsonl \
CKPTS_DIR=/absolute/path/checkpoints \
MODEL_PATH=/absolute/path/to/local/Qwen3.8-27B/snapshot \
TEACHER_MIX_COEF=0.05 \
bash my_scripts/train/mle_opsd/pro6000/run_qwen3_8_27b_opsd_fsdp_lora.sh
```

手动进入训练容器后，从仓库根目录运行 CPU 测试：

```bash
PYTHONPATH="$PWD/src/verl:$PWD/src${PYTHONPATH:+:$PYTHONPATH}" CUDA_VISIBLE_DEVICES= \
python3 -m pytest --import-mode=importlib -q src/verl/tests/recipes/test_mle_opsd.py
```

测试统一放在 verl 的 `tests/recipes`，CHAIi 专用检查测试位于主仓库的
`src/mle_policy/test/test_chaii_inspect.py`。启动脚本按 DATA、MODEL、ACTOR、REF、
ROLLOUT、TRAINER 分组列出参数，末尾 Hydra 参数可以覆盖默认值。

启动脚本关闭 `use_remove_padding` 和动态打包，每卡 microbatch 固定为 1。
`NPROC_PER_NODE`、`ROLLOUT_TP`、`LR`、`TEACHER_MIX_COEF`、`KL_LOSS_COEF`、`TOTAL_STEPS`、
`SAVE_FREQ`、`LORA_ADAPTER_PATH`、`LOG_FILE` 等配置集中在脚本开头。
`TRAIN_FILE` 必填；`VAL_FILE` 默认复用训练文件，但当前不运行独立验证循环。
`CKPTS_DIR` 默认落在 `/tmp`，正式实验请显式指定持久化输出目录。

## 5. 检查效果

checkpoint 使用 verl 原格式。训练目录另有 `metrics.jsonl` 和每步完整学生回答
`responses.jsonl`。重点观察 `opsd/sampled_teacher_score_gap`、score 差的 RMS、回答长度、截断比例、
梯度范数，以及训练后没有经验输入时的代码。
默认另外计算相对底模的 sampled KL 和 log-ratio RMS，底模前向通过暂时禁用 LoRA
完成。`KL_LOSS_COEF=0` 时只监测偏移；可调整该系数研究知识吸收和底模保持的取舍。
`token_scores/step_*.pt` 保存原始回答 token、两种 prompt token、mask，以及学生、
vLLM 和底模的逐 token log probability，以及教师的 `teacher_actor_log_probs`、
`teacher_base_log_probs`、`teacher_log_scores` 和 `teacher_mix_coef`，便于复算。
带经验的底模教师评分与原始输入上的底模 KL 评分是两次不同前向；后者随
`use_kl_loss` 开关启用，默认打开。教师评分始终执行，与 `KL_LOSS_COEF` 无关。

checkpoint 完整保存后，复用 verl 的 checkpoint 合并和已有 adapter 整理工具。
先从 `src/verl` 导出：

```bash
python3 -m verl.model_merger merge \
  --backend fsdp \
  --local_dir /absolute/path/checkpoints/global_step_1/actor \
  --target_dir /absolute/path/exported_step1
```

这一步会写出完整模型和 `lora_adapter/`，需要预留相应内存与磁盘空间。
再从仓库根目录运行已有工具，检查并移除未训练的视觉塔 LoRA：

```bash
PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}" \
python3 -m mle_policy.src.export.lora_adapter \
  --adapter-dir /absolute/path/exported_step1/lora_adapter
```

默认输出 `lora_adapter_vllm/`，将其交给 vLLM 的 `--lora-modules`。
`lora_adapter.py` 负责整理已导出的 adapter；FSDP 分片合并由 `verl.model_merger` 负责。

使用仓库现有 `mle_policy.src.self_distillation.chaii_test` 对底模和导出的 adapter
运行相同 prompt/采样设置，比较代码中的 `use_fast=True` 和显式 fast tokenizer 类。
同时检查正常结束、有完整代码、reasoning 和代码逻辑是否连贯。
fast-tokenizer 命中率证明这条知识是否被吸收；保留 MLE 推理能力需要留出任务的
实际解题和运行结果来验证。

生成入口和离线检查共用同一套统计。对已有回答，从仓库根目录、使用第一节的
`PYTHONPATH` 运行；下面显式指定原始 thinking 模式：

```bash
python3 -m mle_policy.src.self_distillation.chaii_test.inspect \
  --responses /absolute/path/baseline/responses.jsonl /absolute/path/checkpoint/responses.jsonl \
  --response-mode thinking \
  --output /absolute/path/quality-comparison.json
```

输出同名 JSON 和 Markdown 表，分为“思考：明确标识符”“思考：含文字描述”
和“最终代码：明确标识符”，同时报告 think 闭合、提前停止、截断、代码语法和长度。
思考里的示例代码只计思考命中。长度包括生成 token 均值/P90、思考/答案字符数，
JSON 另提供相对首组的均值差和比值。详细定义见 CHAIi 测试目录的 `README.md`。
另外单列默认调用 `AutoTokenizer.from_pretrained` 的代码，以及显式调用
`XLMRobertaTokenizer` 并请求 offsets 的代码，区分明确选择 fast 与实际风险。
这些是静态代码指标，执行环境的 transformers 版本仍需结合原 journal 判断。
`explicit_fast_constructor` 进一步检查实际的 `from_pretrained` 调用；
给 `XLMRobertaTokenizer` 传 `use_fast=True` 单列为 `slow_class_use_fast`，
与明确选择 Fast 类或 `AutoTokenizer(..., use_fast=True)` 分开统计。

## 6. 目录分工

- `src/verl/my_recipes/mle_opsd/`：通用 hindsight 数据、teacher 输入、训练逻辑和配置。
- `src/verl/my_scripts/train/mle_opsd/pro6000/`：本机启动参数。
- `src/verl/tests/recipes/test_mle_opsd.py`：通用 OPSD 回归测试。
- `src/mle_policy/src/self_distillation/chaii_test/`：CHAIi 专用采样与检查。
- `tmp/opsd/`：实验流水账、逐条分析和临时产物。
