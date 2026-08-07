# Reward Model 评估说明

`src/mle_critic/src/evaluation/bradley_terry_evaluation.py` 既可以被训练脚本作为工具模块导入，也可以作为独立命令运行。独立运行时不会启动训练任务。

## 支持的 checkpoint 格式

评估脚本只支持全量微调产物，但支持两种保存形式。

第一种是 Hugging Face Trainer 原始 checkpoint，backbone 和 linear head 位于同一个文件：

```text
checkpoint-160/
  model.safetensors
  trainer_state.json
  training_args.bin
  ...
```

`model.safetensors` 必须同时包含：

```text
backbone.*
head.weight
head.bias
```

第二种是完整 HF backbone 加单独的 linear head：

```text
checkpoint/
  config.json
  model.safetensors
  head.pt
  rm_meta.json
```

这种格式下，`model.safetensors` 是正常的完整 backbone，`head.pt` 只包含 scalar linear head 的 `weight` 和 `bias`。两部分都会严格加载。

脚本不支持 LoRA 或任何 adapter。也不支持用 PyTorch `.bin` 代替 backbone 的 `model.safetensors`。checkpoint 的模型结构与 `--base-model` 不一致时会直接报错，不会忽略缺失或多余的权重。

Trainer 原始 checkpoint 没有保存 `bradley_terry.py` 自己定义的输入构造参数，因此评估时必须根据训练命令补上 `--base-model`，以及训练时修改过的 `--max-len`、`--head-frac`、`--task-cond`、`--budget-cond` 和 `--budget-pos`。带 `rm_meta.json` 的 backbone + linear head 导出目录可以自动读取这些参数，也允许用命令行覆盖。

## Pro6000 L1 checkpoint

当前 Pro6000 L1 全量微调模型的完整评估命令如下，需从仓库根目录执行：

```bash
python -m src.mle_critic.src.evaluation.bradley_terry_evaluation \
  --checkpoint outputs/mle_critic/rmhf_205490_24000/checkpoint-300 \
  --base-model Qwen/Qwen3-4B-Base \
  --pairs data/mle_critic/value_pairs_v3.jsonl \
  --cards data/mle_critic/cards_current.jsonl \
  --split test --eval-cap 3000 --seed 7 --batch-size 8 \
  --max-len 16384 --task-cond \
  --output outputs/mle_critic/eval_l1_checkpoint_300.json
```

上述 checkpoint 使用 Qwen3-4B-Base、16,384 token、启用 task conditioning、不启用 budget conditioning。评估其他 checkpoint 时必须以它实际使用的训练命令为准，不能照抄这里的 base model。

需要先做小规模冒烟测试时，可以把 `--eval-cap 3000` 改成 `--eval-cap 2`。这仍会加载完整模型，但只对两条 pair 做推理。

## 数据选择

`--split` 支持：

- `test`：只评估 `intask_split=test`，默认值；
- `train`：只评估 `intask_split=train`；
- `all`：评估全部有效 pair。

脚本会复现训练脚本的数据顺序：使用 `--seed` 创建同一个随机数生成器，依次 shuffle train pool 和 test pool，然后对 test pair 按 `(better, worse, budget)` 去重。`--eval-cap` 在 shuffle 和去重之后生效；传 `0` 表示不限制数量。

评估输入由 cards 文件中的任务名和代码构造。超长代码使用与训练相同的 head/tail 截断；是否加入任务名和预算由命令行参数决定。对没有 `rm_meta.json` 的 Trainer checkpoint，不要依赖默认值，应当显式传入训练时的配置。

## 输出指标

主指标 `accuracy` 的定义是：

```text
score(better) > score(worse) 的 pair 数量 / 总 pair 数量
```

脚本还会向 stdout 打印 task、budget 和 flip pair 的分组结果。传 `--output` 时，会把汇总结果写成 JSON 文件。

长度接近的控制子集可以通过下面的参数启用：

```bash
--eval-len-control 0.15
```

这表示只保留两端代码字符长度差不超过较长一端 15% 的 pair，并额外报告该子集的准确率。

预算 flip/control 数据可以通过下面的参数评估：

```bash
--flip-eval data/mle_critic/budget_flip_v2_rebuilt.jsonl
```

输出包括低预算准确率、高预算准确率、两端平均准确率、模型改判率、改判正确率，以及 flip/control 改判选择性。评估预算模型时，必须显式传入与训练一致的 `--budget-cond` 和 `--budget-pos`。

## 注意事项

这个脚本只做离线 pairwise evaluation，不会重新切 validation、继续训练或自动选择 checkpoint。checkpoint 需要由调用者明确指定。不要在多个 checkpoint 上反复查看 test accuracy 后再选择最好者，否则 test set 实际上已经被用于模型选择。
