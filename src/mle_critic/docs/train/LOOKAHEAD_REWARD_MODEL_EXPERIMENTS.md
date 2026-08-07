# Lookahead reward model 实验运行说明

这套代码来自学生分支 `origin/phase1-value-critic` 的 `b5aa5fe`，但已经改成当前仓库目录和可配置路径。原调查见 `tmp/student/Lookahead与预算实验详细调查.md`；数据来源和不能精确复原的部分见 [数据说明](LOOKAHEAD_DATA_PROVENANCE.md)。以下命令均从仓库根目录执行。

## 环境和硬件

项目环境：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
```

训练依赖见 `src/mle_critic/src/train/requirements.txt`。当前项目的 `aira-dojo` conda 环境没有安装 `torch`，需要在训练节点为该环境补装依赖：

```bash
python -m pip install -r src/mle_critic/src/train/requirements.txt
```

正式配置是 Qwen2.5-1.5B-Instruct 全参数微调、bf16、ZeRO-3、optimizer CPU offload、pair batch 1、gradient accumulation 16。单张 RTX 3090 可以运行，但 CPU 内存、磁盘临时空间和接近一天的 wall time 都要预留。可用 `MLE_CRITIC_MODEL=/本地模型路径` 避免从 Hugging Face 下载模型。

## `bradley_terry.py` 到底做了什么

学生原脚本同时塞了数据切分、tokenize、模型定义、训练、普通评估、预算翻转评估、checkpoint 保存和 CSV 追加。当前版本的训练逻辑在 `src/mle_critic/src/train/bradley_terry.py`，数据处理在 `src/mle_critic/src/train/dataset/`，普通评估和预算翻转评估在 `src/mle_critic/src/evaluation/bradley_terry_evaluation.py`，HTTP server 在 `bradley_terry_server.py`。评估模块同时提供独立 CLI，详见 [`docs/evaluation/BRADLEY_TERRY_EVALUATION.md`](../evaluation/BRADLEY_TERRY_EVALUATION.md)。

整体流程是：

```text
读取 cards 和 pair
  -> 构造 train_pool
  -> 固定 seed 后 shuffle train_pool
  -> 对 --sizes 中的每个 N：
       取 train_pool[:N]，再按 80/20 切 train/validation
       重新加载一份 pretrained backbone 和新 scalar head
       用其中约 80% 的 training_subset 训练，每 20 个 optimizer step 在 validation_pool 上评估
       保存 validation Bradley–Terry loss 最低的 checkpoint
  -> 训练脚本结束；test/length/flip 评估由独立 evaluator 执行
```

### 1. cards 和 pair 如何读入

`--cards` 文件建立两个内存字典：

```text
card ID -> 当前节点的完整 code
card ID -> MLEBench task name
```

`--pairs` 的每条记录只保存 card ID，不重复保存代码。读入后先丢掉 better 或 worse 无法在 cards 中解析的记录。

这里模型从 card 读取的监督输入只有任务名、代码和可选 budget。`label.graded`、self-report、parent score 等字段不会送进 reward model；它们只在上游 pair 生成阶段决定 better/worse。

### 2. 训练数据如何划分

普通 in-task 模式：

```python
train_pool = [p for p in pairs if p["intask_split"] == "train"]
```

脚本本身不重新做树切分，只信任 pair 文件已经写好的 `intask_split`。因此 L1 是否端点泄漏、L2 是否严格双端留树，取决于上游 pair 生成器，不取决于 trainer。

LOTO 模式则完全忽略 `intask_split`：

```python
train_pool = [p for p in pairs if p["task"] != target]
```

也就是说，其他任务原来的 train/test 记录都会进入 LOTO 训练池；目标任务完全不进入训练。训练脚本本身不读取目标任务 test pool，测试评估由独立 evaluator 按需执行。

训练脚本只 shuffle 训练池，并不截取或平衡测试池。测试 split、`eval-cap` 和任务分组策略由独立 evaluator 的命令行负责。

### 4. 模型输入和截断

默认输入是：

```text
# MLE-bench task: <task name>
<current node code>
```

预算条件化时，再加入：

```text
# remaining budget: K steps
```

`--budget-pos=head` 把预算放在代码前，`tail` 则先给代码 tokenize，预留预算 suffix 的 token 空间，截断代码后再追加 suffix。超长输入保留开头 `head_frac`，默认 25%，以及末尾剩余 75%。tail 模式的目的就是保证预算文本不会被长代码截掉，并让它靠近 scalar head 使用的最后 token。

`--task-cond` 的 argparse 写法是 `store_true, default=True`，因此当前 CLI 实际上无法关闭 task conditioning；不传参数也永远是 true。这是接口写法问题，不应把它理解成学生认真跑过 task-conditioned/无 task-conditioned 两个臂。

### 5. pair batch 和 Bradley–Terry loss

`PairDS` 对每条记录返回 better 和 worse 两段 token。collator 把一个 batch 排成：

```text
[所有 better 序列, 所有 worse 序列]
```

因此 `--bs=1` 表示每张 GPU 每步一个 pair，但 backbone 实际前向两条 code 序列。有效 pair batch 约为：

```text
per-device pair batch * gradient accumulation * GPU 数
```

模型结构为：

```text
Qwen AutoModel
  -> 最后一个非 padding token 的 hidden state
  -> Linear(hidden_size, 1)
  -> scalar reward
```

一个 batch 的 loss 是：

```text
-mean(log sigmoid(score(better) - score(worse)))
```

当前只支持全参数微调；backbone 使用 bf16、gradient checkpointing，优先尝试 Flash Attention 2，失败后回退普通 attention。

### 6. 当前 validation 和 best checkpoint 逻辑

学生原版确实没有训练期 validation。当前版本先从 shuffle 后的训练池取当前 size 对应的前 N 条，再做 record-level 80/20 切分：

```python
sized_pool = train_pool[:N]
validation_size = max(1, int(len(sized_pool) * 0.2))
training_subset = sized_pool[:-validation_size]
validation_pool = sized_pool[-validation_size:]
```

随后给 Trainer 同时传入：

```python
train_dataset=PairDS(training_subset)
eval_dataset=PairDS(validation_pool)
```

默认每 20 个 optimizer step 计算一次 validation Bradley–Terry loss 和 `eval_pair_accuracy`。这里的 step 是 gradient accumulation 完成后的 optimizer/global step，不是每个 micro-batch；可以用 `--eval-steps` 修改间隔。Trainer 配置为：

```text
eval_strategy=steps
eval_steps=20
save_strategy=best
metric_for_best_model=eval_loss
greater_is_better=false
load_best_model_at_end=true
save_total_limit=1
```

项目锁定的 Transformers 4.49 已原生支持 `save_strategy="best"`。因此每 20 个 optimizer step 验证一次，但只有 `eval_loss` 创下新低时才保存 checkpoint。训练脚本不再执行 test-side evaluation；普通 test、length-control 和 flip/control 评估通过独立 evaluator 执行。`eval_pair_accuracy` 仍作为 validation 观察指标报告，但不参与模型选择。

这里按用户要求采用简单 record-level 80/20，而不是 tree-level validation。对带 flip boost 的 L2 数据，相同记录副本可能分别落入 train 和 validation；因此它能用于训练期选 checkpoint，但不是严格的无泄漏 validation。后续若需要严谨比较超参数，应该在 pair 生成阶段按 tree root 单独生成 validation split。

### 7. `--sizes` 循环

原代码是：

```python
for N in [int(x) for x in re.split(r"[,;:]", a.sizes) if x.strip()]:
```

它允许以下写法：

```bash
--sizes 500
--sizes 500,2000,8000
--sizes 500:2000:8000
--sizes '500;2000;8000'
```

这是早期画 learning curve 的遗留接口。它不是 range 语法，冒号也不表示起点/终点/步长，只是和逗号、分号一样的分隔符。

对每个 N，脚本执行：

```python
sized_pool = train_pool[:N]
training_subset, validation_pool = split_80_20(sized_pool)
model = RM(base_model)
tr.train()  # 默认每 20 个 optimizer step 验证并保存最低 eval_loss checkpoint
```

需要注意四件事：

1. 每个 N 都重新从 pretrained model 加载 backbone，并新建 scalar head；不是 N=500 训练完继续扩到 2,000。
2. 因为 train pool 只 shuffle 一次，各规模是嵌套前缀：500 是 2,000 的子集，2,000 是 8,000 的子集。
3. 每个 N 都从各自的 `sized_pool` 尾部取约 20% 作为 validation；因为各规模是嵌套前缀，这些 validation 集并不相同。
4. 训练脚本只保存 checkpoint，不再写 test accuracy CSV；需要比较不同 checkpoint 时，用独立 evaluator 对指定 split 评估。

此外，脚本只在最外层调用一次 `torch.manual_seed(seed)`。第二个 N 的 scalar head 是在第一个模型训练已经消耗 RNG 状态之后初始化的，因此多 size 运行并不保证不同 N 使用同一份 head initialization。要做干净 learning curve，更合理的是每个 N 独立进程运行并显式重置 seed。

正式 L1/L2/rescue 启动脚本都只传一个 N，所以不会触发多模型 learning-curve 循环；在这些实验里可以把 `--sizes` 暂时理解成一个写成字符串的 `--train-record-cap`。

### 8. 训练后的三类评估

这些评估不再由 `bradley_terry.py` 执行。请使用 `src/mle_critic/src/evaluation/bradley_terry_evaluation.py` 的独立 CLI，见[评估文档](../evaluation/BRADLEY_TERRY_EVALUATION.md)。

普通 accuracy 比较 `score(better) > score(worse)`，并打印 task、budget 和 `flips_vs_b1` breakdown。

`--eval-len-control=0.15` 会另外保留两个代码字符长度差不超过较长代码 15% 的 pair。它只是报告一个控制子集，不参与训练或模型选择；少于 100 条时跳过。

`--flip-eval` 会对同一个 x/y 在 K=1 和 K_hi 下分别打分，报告：

- `acc_lo`、`acc_hi` 和二者平均；
- `model_switched`/`moved`：模型是否随预算改变 winner；
- `switch_acc`：发生改变时是否两端都改对；
- `selectivity`：flip pair 改判率除以 control pair 改判率。

预算盲模型会把 budget 置为 None，所以同一代码在不同 K 下的 token 完全一致。它在真正 flip pair 上的平均正确率解析上应为 0.5。

### 9. checkpoint

Trainer 默认每 20 个 optimizer step 验证一次，只有 `eval_loss` 创下新低时才保存。训练脚本保留原始 Hugging Face checkpoint，独立 evaluator 直接读取它：

```text
outputs/mle_critic/rmhf_<pid>_<N>/checkpoint-<step>/
  model.safetensors
  trainer_state.json
```

训练脚本不再写评估 CSV；评估结果由 evaluator 通过 `--output` 写 JSON。

### 10. 对当前结果应该怎么读

训练脚本本身不产出 test accuracy；独立 evaluator 产出的 accuracy 是指定 checkpoint 在指定 split 上的排序准确率。相比学生原版，训练和 test evaluation 已经解耦；validation 仍是训练记录的简单 record split，不是 tree-level split。

当前仍值得补的工程项是 tree-level validation，以及把 learning-curve 的每个 N 拆成独立运行。不要根据 test accuracy 回头选择 N 或超参数。

## L1：整个可见子树的最好分数

L1 标签比较当前节点及全部可见后代中的最佳外部得分。模型输入只有任务名和当前代码，不含预算。

```bash
bash src/mle_critic/scripts/train/pro6000/train_l1_lookahead.sh 7
```

学生报告的原配置是 Qwen2.5-1.5B-Instruct、`N=24000`、`max_len=2048`、2 epochs、`lr=1e-5`、seed 7。当前 `pro6000` launcher 已改成 Qwen3-1.7B-Base、16,384 context、2 GPU 和 accumulation 32，是后续本地配置，不会直接复现学生的 `0.8183`。原结果还使用旧的非对称树切分，测试 pair 中约 87.3% 至少有一个端点代码在训练 pair 中出现过，不能解释成严格的未见树泛化。

## L2：count-matched 预算标签

L2 的 `K` 是 cards 图中按历史 `lineage.step` 排序的前 K 个带分后代，不是墙钟时间、GPU 小时或完整 MCTS step。先跑预算盲臂，再跑预算条件化臂：

```bash
bash src/mle_critic/scripts/train/train_l2_budget.sh blind 7
bash src/mle_critic/scripts/train/train_l2_budget.sh conditioned 7
```

Conditioned 模型把 `# remaining budget: K steps` 放在 token 序列尾部。scalar head 读取最后一个非 padding token，因此不能随意把预算文本移回头部。两个脚本默认使用仓库中的 `_rebuilt` 数据；它们可运行和审计，但并非学生缺失的原始 v2 文件。

要从 cards 重新构造 L1/L2 pair：

```bash
bash src/mle_critic/scripts/build_lookahead_datasets.sh
python -m src.mle_critic.src.preprocess.audit_budget_pairs \
  data/mle_critic/budget_pairs_v2_local.jsonl data/mle_critic/cards_current.jsonl
python -m src.mle_critic.src.preprocess.audit_budget_pairs_details \
  data/mle_critic/budget_pairs_v2_local.jsonl data/mle_critic/cards_current.jsonl 2400
```

## LOTO 和 rescue

LOTO 按任务留一，但不传 `--budget-cond`。它训练的是混合预算记录上的平均排序，不是在测试预算条件化的跨任务迁移。

```bash
bash src/mle_critic/scripts/train/train_loto.sh nomad2018-predict-transparent-conductors 7
```

Rescue 先混入目标任务训练树中的有序 pair key，再在目标任务留出树评估。`K=500` 表示 500 个有序 pair key，不等于 500 条记录或 500 个节点。

```bash
bash src/mle_critic/scripts/build_rescue_datasets.sh
bash src/mle_critic/scripts/train/train_rescue.sh nomad 500 7
bash src/mle_critic/scripts/train/train_rescue.sh petfinder 2000 13
```

## checkpoint 和在线 sidecar

启动 L1 checkpoint sidecar：

```bash
bash src/mle_critic/scripts/serve_lookahead_rm.sh \
  outputs/mle_critic/ckpt_lookahead_v3_seed7/N24000 8765
curl -sS http://127.0.0.1:8765/score \
  -H 'Content-Type: application/json' \
  -d '{"task":"spooky-author-identification","code":"print(1)"}'
```

sidecar 只接收 `task + code`，适用于学生 T3v2 计划中的静态 L1 bias。在线 MCTS consumer 位于 `origin/dojo-reproduce-collect`，不属于训练代码，也没有合入当前 `dojo-reproduce` 分支。T3v2 截至调查时没有正式结果；不要把 sidecar 启动成功当作在线实验已经复现。L2 checkpoint 的 `rm_meta.json` 虽记录 `budget_cond`，当前 sidecar 协议却没有预算字段，因此不能用它验证动态 `score(code, K)`。

## 常见问题

- `cards_current.jsonl` 只包含带外部分数并保留在 cards 图中的节点；断链或无分后代不会进入 lookahead 标签。
- reward model 对超长代码保留头部 25% 和尾部 75%；L2 tail budget 会在截断后追加，确保预算不被裁掉。
- 训练日志和 Hugging Face checkpoint 是训练脚本的主要输出；评估结果由独立 evaluator 写入 JSON。
- `--sizes` 是抽取的记录数。flip boost 和同一节点对的多个预算会造成重复，不能把它当作独立程序数。
- 多臂并行时每个 DeepSpeed 进程必须绑定不同 GPU 和 master port。这里的脚本默认单 GPU，调度层并发应由 Slurm 或外部 launcher 管理。
