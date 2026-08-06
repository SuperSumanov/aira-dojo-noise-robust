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

也可以用 `MLE_CRITIC_CONDA_ACTIVATE` 和 `MLE_CRITIC_CONDA_ENV` 指向准备好的环境。LoRA 或读取 LoRA checkpoint 时还需要 `peft`。代码优先使用 Flash Attention 2，加载失败会回退到普通 attention。

正式配置是 Qwen2.5-1.5B-Instruct 全参数微调、bf16、ZeRO-3、optimizer CPU offload、pair batch 1、gradient accumulation 16。单张 RTX 3090 可以运行，但 CPU 内存、磁盘临时空间和接近一天的 wall time 都要预留。可用 `MLE_CRITIC_MODEL=/本地模型路径` 避免从 Hugging Face 下载模型。

## `reward_model.py` 到底做了什么

学生原脚本同时塞了数据切分、tokenize、模型定义、训练、普通评估、预算翻转评估、checkpoint 保存和 CSV 追加。当前版本已经把普通评估和预算翻转评估移到 `src/mle_critic/evaluation/reward_model_evaluation.py`，HTTP server 也移到了同一目录。

整体流程是：

```text
读取 cards 和 pair
  -> 构造原始 train_pool / test_pool
  -> 固定 seed 后分别 shuffle
  -> 截取或按任务平衡 test_pool
  -> 对 --sizes 中的每个 N：
       取 train_pool[:N]，再按 80/20 切 train/validation
       重新加载一份 pretrained backbone 和新 scalar head
       用其中约 80% 的 training_subset 训练，每 20 个 optimizer step 在 validation_pool 上评估
       保存 validation Bradley–Terry loss 最低的 checkpoint
       恢复 best checkpoint 后在 test_pool 上算最终 accuracy
       可选：算 length-control 和 budget flip/control 指标
       可选：保存 backbone/adapter、scalar head、rm_meta.json
  -> 将每个 N 的结果追加到 CSV
```

### 1. cards 和 pair 如何读入

`--cards` 文件建立两个内存字典：

```text
card ID -> 当前节点的完整 code
card ID -> MLEBench task name
```

`--pairs` 的每条记录只保存 card ID，不重复保存代码。读入后先丢掉 better 或 worse 无法在 cards 中解析的记录。

这里模型从 card 读取的监督输入只有任务名、代码和可选 budget。`label.graded`、self-report、parent score 等字段不会送进 reward model；它们只在上游 pair 生成阶段决定 better/worse。

### 2. train/test 是如何划分的

普通 in-task 模式：

```python
train_pool = [p for p in pairs if p["intask_split"] == "train"]
test_pool  = [p for p in pairs if p["intask_split"] == "test"]
```

脚本本身不重新做树切分，只信任 pair 文件已经写好的 `intask_split`。因此 L1 是否端点泄漏、L2 是否严格双端留树，取决于上游 pair 生成器，不取决于 trainer。

LOTO 模式则完全忽略 `intask_split`：

```python
train_pool = [p for p in pairs if p["task"] != target]
test_pool  = [p for p in pairs if p["task"] == target]
```

也就是说，其他任务原来的 train/test 记录都会进入 LOTO 训练池；目标任务原来的 train/test 记录都会进入 LOTO 测试池。由于目标任务完全没进训练，这仍是 task-level holdout，但它不是“只在目标任务 test-tree 上评估”。

两个 pool 用同一个 `random.Random(seed)` 依次 shuffle。test 随后按 `(better, worse, budget)` 去重，主要用于去掉 flip boost 在 LOTO 目标任务里带来的重复记录。

### 3. `eval_cap` 和 `eval_stratify`

不传 `--eval-stratify` 时，shuffle 后直接取：

```python
test_pool = test_pool[:eval_cap]
```

这种抽法会让 pair 数量最大的任务主导 pooled accuracy。

传 `--eval-stratify` 时：

1. 按 task 分组；
2. 丢掉测试记录少于 `eval_min_task` 的任务，默认阈值为 60；
3. 每个保留任务最多取 `max(eval_cap // n_tasks, eval_min_task)` 条；
4. 将各任务子集拼回 test pool。

这不是严格保证总数等于 `eval_cap` 的 sampler。因为代码用了 `max`，当 `eval_cap < n_tasks * eval_min_task` 时，总数可能超过 cap；记录少的任务也会被整个移除。正式 L2 配置 `eval_cap=2400` 时该行为比较稳定，但修改参数时要重新核对实际 `n_test`。

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

默认是全参数微调。`--lora` 时只在 q/k/v/o projection 上加 rank-16 LoRA，同时 scalar head 始终训练。backbone 使用 bf16、gradient checkpointing，优先尝试 Flash Attention 2，失败后回退普通 attention。

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

项目锁定的 Transformers 4.49 已原生支持 `save_strategy="best"`。因此每 20 个 optimizer step 验证一次，但只有 `eval_loss` 创下新低时才保存 checkpoint；训练结束自动恢复 loss 最低的 checkpoint，然后才运行普通 test、length-control 和 flip/control 评估。传 `--save-adapter` 时导出的也是恢复后的 best model。`eval_pair_accuracy` 仍作为观察指标报告，但不参与模型选择。CSV 和 `rm_meta.json` 额外记录 `n_train_actual`、`n_validation`、`best_validation_loss` 和 best checkpoint 路径。

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
tr.train()  # 默认每 20 个 optimizer step 验证，结束时恢复最低 eval_loss checkpoint
evaluate_pairs(tr.model, same_test_pool)
```

需要注意四件事：

1. 每个 N 都重新从 pretrained model 加载 backbone，并新建 scalar head；不是 N=500 训练完继续扩到 2,000。
2. 因为 train pool 只 shuffle 一次，各规模是嵌套前缀：500 是 2,000 的子集，2,000 是 8,000 的子集。
3. 每个 N 都从各自的 `sized_pool` 尾部取约 20% 作为 validation；因为各规模是嵌套前缀，这些 validation 集并不相同。不同 N 最终评估的是同一个 test pool；如果继续根据 test 选择 N，test 仍会被污染。
4. CSV 的 `N` 和 checkpoint 目录仍记录请求值；`n_train_actual` 和 `n_validation` 才是 80/20 后实际送入两边的记录数。若训练池只有 5,000 条而传 `--sizes 8000`，实际会把 5,000 条切成约 4,000/1,000。

此外，脚本只在最外层调用一次 `torch.manual_seed(seed)`。第二个 N 的 scalar head 是在第一个模型训练已经消耗 RNG 状态之后初始化的，因此多 size 运行并不保证不同 N 使用同一份 head initialization。要做干净 learning curve，更合理的是每个 N 独立进程运行并显式重置 seed。当前 CSV 已记录 `n_train_actual`。

正式 L1/L2/rescue 启动脚本都只传一个 N，所以不会触发多模型 learning-curve 循环；在这些实验里可以把 `--sizes` 暂时理解成一个写成字符串的 `--train-record-cap`。

### 8. 训练后的三类评估

普通 accuracy 比较 `score(better) > score(worse)`，并打印 task、budget 和 `flips_vs_b1` breakdown。

`--eval-len-control=0.15` 会另外保留两个代码字符长度差不超过较长代码 15% 的 pair。它只是报告一个控制子集，不参与训练或模型选择；少于 100 条时跳过。

`--flip-eval` 会对同一个 x/y 在 K=1 和 K_hi 下分别打分，报告：

- `acc_lo`、`acc_hi` 和二者平均；
- `model_switched`/`moved`：模型是否随预算改变 winner；
- `switch_acc`：发生改变时是否两端都改对；
- `selectivity`：flip pair 改判率除以 control pair 改判率。

预算盲模型会把 budget 置为 None，所以同一代码在不同 K 下的 token 完全一致。它在真正 flip pair 上的平均正确率解析上应为 0.5。

### 9. checkpoint 和 CSV

Trainer 默认每 20 个 optimizer step 验证一次，只有 `eval_loss` 创下新低时才保存，并在训练结束恢复 best checkpoint。传 `--save-adapter` 后，再将这个 best model 导出为可供 sidecar 使用的目录：

```text
<save-adapter>/N<N>/
  backbone 权重或 LoRA adapter
  head.pt
  rm_meta.json
```

`save-adapter` 这个名字仍不准确：全参数微调时保存的是完整 backbone，不是 adapter。当前 `rm_meta.json` 已同时记录 `budget_cond` 和 `budget_pos`。

CSV 使用追加写。如果已有文件 header 和当前 row 字段不一致，脚本会改写到 `_s2.csv`。它不会检查旧行是不是同一个 pairs 文件或同一实验，因此复用输出路径时仍可能把不同配置混在一起。

### 10. 对当前结果应该怎么读

这个脚本当前产出的 accuracy 是 validation loss 最低的 checkpoint 在独立 `test_pool` 上的排序准确率。相比学生原版，它不再固定使用最终 epoch；但 validation 是训练记录的简单 80/20 record split，不是 tree-level split。

当前仍值得补的工程项是 tree-level validation，以及把 learning-curve 的每个 N 拆成独立运行。只要不再根据最终 test accuracy 回头选择 N 或超参数，`test_pool` 就可以恢复为最终报告集。

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

Conditioned 模型把 `# remaining budget: K steps` 放在 token 序列尾部。scalar head 读取最后一个非 padding token，因此不能随意把预算文本移回头部。两个脚本默认使用仓库中的 `_rebuilt` 数据；它们可运行和审计，但并非学生缺失的原始 v2 文件，结果不应和已保存 CSV 做逐行相等断言。

要从 cards 重新构造 L1/L2 pair：

```bash
bash src/mle_critic/scripts/build_lookahead_datasets.sh
python -m src.mle_critic.src.dataset.audit_budget_pairs \
  data/mle_critic/budget_pairs_v2_local.jsonl data/mle_critic/cards_current.jsonl
python -m src.mle_critic.src.dataset.audit_budget_pairs_details \
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
- CSV 是追加写。若 header 与当前字段不一致，trainer 会改写到 `_s2.csv`；跑 seed 前应检查输出路径，避免把不同实验混在一个文件中。
- `--sizes` 是抽取的记录数。flip boost 和同一节点对的多个预算会造成重复，不能把它当作独立程序数。
- 多臂并行时每个 DeepSpeed 进程必须绑定不同 GPU 和 master port。这里的脚本默认单 GPU，调度层并发应由 Slurm 或外部 launcher 管理。
