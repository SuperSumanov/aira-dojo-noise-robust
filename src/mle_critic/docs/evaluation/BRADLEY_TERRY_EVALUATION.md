# Bradley--Terry reward model 评估

评估脚本读取 pair JSONL 和 cards JSON，给每个 pair 的 better/worse 代码打分，计算 `score(better) > score(worse)` 的比例。它只做推理，不会训练或自动挑选 checkpoint。

## 启动

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate Hista
PYTHONPATH=src/mle_critic python -m src.evaluation.bradley_terry_evaluation \
  --checkpoint outputs/augmented_mle_critic/Qwen3-8B_reward_seed1/checkpoint-100 \
  --base-model Qwen/Qwen3-8B-Base \
  --pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
  --cards data/augmented_mle_critic/augmented_cards_current.json \
  --split test --eval-cap 3000 --seed 7 --batch-size 1 \
  --max-len 16384 --task-cond \
  --output outputs/augmented_mle_critic/eval_filtered_reward_checkpoint_100.json
```

没有 `rm_meta.json` 的 Trainer checkpoint 必须显式传 `--base-model`，并按训练设置传入 `--max-len`、`--head-frac`、`--task-cond`、`--budget-cond`、`--budget-pos`。

## 多卡和显存

CUDA 可用时默认使用 Transformers/Accelerate 的 `device_map="auto"`，将模型分配到可见设备，输入放到首层所在卡；CPU/单卡同样支持。这是按层切分模型，单次前向依次经过各张卡，不是每张卡各放一份模型。自动分配会考虑参数大小和可用显存，不保证各卡层数相同；可以用 `CUDA_VISIBLE_DEVICES=0,1` 指定使用的 GPU。

`--max-len 16384` 是输入长度上限，不代表实际样本一定达到该长度。过长代码按 head/tail 截断，默认保留开头 25% 和末尾 75%。每批会右侧补齐到该批最长输入，因此显存主要受最长样本和 batch size 影响。

2026-09-07 在 Hista 环境、两张 RTX 3090 上，用上述 Qwen3-8B checkpoint 实测：

- 将完整命令的 `--eval-cap` 改为 `1`，结果输出到 `/tmp/bt_eval_one.json`：正常退出，`n_pairs=1`、`accuracy=1.0`，任务为 `denoising-dirty-documents`。这只是冒烟测试，不代表整体准确率。
- 另外通过评估脚本的 `_score_sequences`，同时输入两段各 **16384 token** 的合成序列（重复 EOS token），覆盖 `--batch-size 1` 同时处理 better/worse 的满长度情况。正常退出，logit 为 `[1.0859375, 1.0859375]`，前向约 10.19 秒，没有 OOM。
- 此次自动分配：GPU 0 放 embedding 和第 0–15 层，GPU 1 放第 16–35 层及最终 norm。

| GPU | PyTorch 显存分配峰值 | PyTorch 显存预留峰值 |
| --- | --- | --- |
| 0 | 12.18 GiB | 12.93 GiB |
| 1 | 12.70 GiB | 14.00 GiB |

显存峰值在模型加载完成后重置计数，统计的是满长度前向期间（包含模型权重）的用量，不包含其他进程和 CUDA 上下文占用。这验证了当前环境下 `batch-size=1` 的满长度前向；没有跑完 3000 个 pair，也不代表更大 batch 或有其他任务占用显存时不会 OOM。

## checkpoint 格式

支持：Trainer 原始 checkpoint（`model.safetensors` 含 `backbone.*`、`head.weight`、`head.bias`），或完整 HF backbone 加 `head.pt` 和可选 `rm_meta.json`。不支持 LoRA/adapter 或 `.bin` backbone。

## 数据与输出

cards 文件是 JSON 对象：run ID 映射到 card 列表，每个 card 使用 `id`、`code`、`task.name` 字段。pair 文件是 JSONL，包含 `better`、`worse`、`task`、`intask_split`，以及可选的预算字段。找不到任意一端 card 的 pair 会被过滤。

`--split` 支持 `test`、`train`、`all`。train/test 使用同一个 `--seed` 随机数生成器，先 shuffle train pool，再 shuffle test pool；test 随后按 `(better, worse, budget)` 去重。`--eval-cap` 在这些步骤之后生效，`0` 表示不限制。每个 batch 实际处理 `2 * batch-size` 段输入。输出包含总体 JSON 和 task/budget 分组准确率；指定 `--output` 会写入 JSON，覆盖同路径旧结果。

旧文档中的 `--eval-len-control` 和 `--flip-eval` 不属于当前脚本支持的参数，不能继续使用。当前参数可通过 `--help` 查看。
