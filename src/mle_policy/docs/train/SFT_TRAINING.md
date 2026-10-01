# MLE policy 的 SFT 训练（verl）

数据怎么来的见 `src/mle_policy/docs/data/README.md`；这篇只讲拿它去训练。

**先看结论**：数据、转换脚本、训练脚本都跑通了，**但 Qwen3.5 在
`verl.trainer.sft_trainer` 这条路上会崩**（第 5 节，有证据），所以现在真正跑起来的
基线用的是 `Qwen/Qwen3-8B-Base`。换回 Qwen3.5 只要改一个环境变量，
前提是先把第 5 节的坑填掉。

## 1. 训练的是什么

* **数据**：`data/mle_policy/dataset/<bucket>/sft.jsonl`
  —— 每个 prompt group 里挑一条最好的episode（rejection sampling）。
* **模型**：`Qwen/Qwen3-8B-Base`（原计划 `Qwen/Qwen3.5-9B`，见第 5 节）
* **框架**：`src/verl` 的 `verl.trainer.sft_trainer`（纯 FSDP，不起 Ray）
* **机器**：projgpu39，2× RTX PRO 6000（每张 98 GB）
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

在宿主机上起一个交互式 `singularity shell`，进容器后：

```bash
cd <repo>/src/verl          # 容器里就是 /workspace/verl/src/verl
bash my_scripts/train/mle_policy/pro6000/run_qwen3_5_9b_sft_fsdp_sp.sh
```

**工作目录必须是 `src/verl`**，因为 `data.custom_cls.path` 写的是
`pkg://my_recipes.dataset.mlepolicy_sft_dataset`（类名 `MlePolicySFTDataset`），
要靠在当前目录下找到 `my_recipes` 这个包。这个类必须用：verl 自带的
`MultiTurnSFTDataset` 会逐条渲染 message，Qwen3.5 上直接崩，见第 2 节。