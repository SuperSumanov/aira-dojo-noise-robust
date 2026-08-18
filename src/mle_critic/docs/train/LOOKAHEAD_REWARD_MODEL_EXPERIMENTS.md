# Augmented reward model：当前训练流程

本文记录当前仓库里实际使用的 augmented reward 数据和训练入口。旧的学生版 L1/L2、
rescue、多预算 flip 实验不再是当前主线，相关旧命令不应拿来复现实验。LOTO 仍由当前
Bradley-Terry trainer 原生支持，但不是 augmented launcher 的默认训练臂。

## 1. 当前主线

数据处理和训练顺序是：

```text
raw journal
  -> 每个搜索 batch 的 batch_cards.json
  -> batch_value_pairs.jsonl
  -> gap_filter
  -> frozen physical-run split
  -> context length 预检查
  -> Bradley-Terry reward model
  -> light predictor 对照
```

完整操作清单在 tmp/reminder_train。核心产物是：

```text
data/augmented_mle_critic/augmented_cards_current.json
data/augmented_mle_critic/raw_journal/batch_value_pairs.jsonl
data/augmented_mle_critic/raw_journal/batch_value_pairs_filtered.jsonl
data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl
```

数据构建细节见[数据说明](../data/OVERVIEW_MINE.md)。

## 2. 环境和 launcher

训练通过 accelerate 和 src/mle_critic/recipes/zero3.yaml 启动。augmented launcher 的共享
配置在：

```text
src/mle_critic/scripts/experiment_env_augmented_data.sh
```

它把 DATA_DIR、OUTPUT_DIR、LOG_DIR 分别设为
data/augmented_mle_critic、outputs/augmented_mle_critic、logs/augmented_mle_critic，并
导出仓库根目录 PYTHONPATH。这三个目录可以用
MLE_CRITIC_DATA_DIR、MLE_CRITIC_OUTPUT_DIR、MLE_CRITIC_LOG_DIR 覆盖。

## 3. 训练入口和当前激活配置

当前 augmented reward launcher：

```text
src/mle_critic/scripts/train/pro6000/train_aug_reward.sh
```

运行：

```bash
bash src/mle_critic/scripts/train/pro6000/train_aug_reward.sh
```

可以用第一个位置参数覆盖 seed，例如：

```bash
bash src/mle_critic/scripts/train/pro6000/train_aug_reward.sh 7
```

脚本当前真正执行的只有 Qwen3-8B-Base 这一臂；0.6B、1.7B、4B 的命令保留为注释，没有
执行。实际参数是：

```text
accelerate processes       2
model                      Qwen/Qwen3-8B-Base
train/test pairs           data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl
cards                      data/augmented_mle_critic/augmented_cards_current.json
max_len                    16384
task_cond                  true
per-device train batch     2
per-device eval batch      2
gradient accumulation      32
eval_steps                 10
learning rate              1e-5
epochs                     1
seed                       6
```

日志写到 logs/augmented_mle_critic，checkpoint 写到
outputs/augmented_mle_critic/Qwen3-8B_reward_seed6。

不要把旧文档中 Qwen2.5-1.5B、N=24000、2048 context 或 train_l1_lookahead.sh 的参数当成
当前 augmented 配置；它们属于旧实验或已经停用的 launcher。

## 4. bradley_terry.py 的真实数据流程

入口是 src/mle_critic/src/train/bradley_terry.py，数据部分在
src/mle_critic/src/train/dataset/pairs.py，训练配置在
src/mle_critic/src/train/config/bradley_terry_config.py。

### Cards 和 pairs

当前 read_cards 接受 run-grouped JSON：

```text
run_id -> [Card, Card, ...]
```

它建立两个 lookup：

```text
card_id -> code
card_id -> task name
```

read_pairs 读取 JSONL，只保留 better 和 worse 两个 Card ID 都存在的记录。监督所需的
gap_raw、grade、采样配置等字段不会直接送入模型；模型输入来自 Card 的 task name、code
以及可选 budget 条件。

### train/test pool

launcher 将同一个 split-assigned pair 文件同时传给 --train-pairs 和 --test-pairs。在
trainer 内部：

```python
training_pool = [p for p in pairs if p["intask_split"] == "train"]
testing_pool  = [p for p in pairs if p["intask_split"] == "test"]
```

随后两个 pool 各自按 seed shuffle。training_pool 的全部记录作为 train_dataset，
testing_pool 的全部记录作为 eval_dataset。当前代码没有再从 training pool 切 80/20
validation，也没有单独的 test-only evaluator 阶段；训练中的 eval 实际上直接看 frozen
holdout test pool。

这点要明确：当前 eval pool 并不是训练集内部 validation。若用 eval loss/accuracy 选择
checkpoint，就已经使用了 holdout split，不能再把同一个 split 当完全未触碰的最终测试集。

rescue 和旧的预算实验 launcher 已删除；LOTO 不是独立 launcher，而是
bradley_terry.py 的当前可用参数。

### LOTO

传入 --loto TASK 后，当前 trainer 会忽略 pair 的 intask_split：

~~~python
training_pool = [p for p in pairs if p["task"] != TASK]
testing_pool  = [p for p in pairs if p["task"] == TASK]
~~~

因此其他任务的 train/test 记录都会进入训练池，目标任务的记录进入 eval pool。直接启动示例：

~~~bash
accelerate launch \
  --config_file src/mle_critic/recipes/zero3.yaml \
  --num_processes 2 src/mle_critic/src/train/bradley_terry.py \
  --train-pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
  --test-pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
  --cards data/augmented_mle_critic/augmented_cards_current.json \
  --model Qwen/Qwen3-8B-Base \
  --loto nomad2018-predict-transparent-conductors \
  --max-len 16384 \
  --per-device-train-batch-size 2 \
  --per-device-eval-batch-size 2 \
  --gradient-accumulation-steps 32 \
  --eval-steps 10 \
  --learning-rate 1e-5 \
  --num-train-epochs 1 \
  --output-dir outputs/augmented_mle_critic/loto_nomad_seed7 \
  --seed 7
~~~

## 5. 模型输入和截断

默认 task_cond=true，每个 Card 的输入文本是：

```text
# MLE-bench task: <task name>
<current node code>
```

CardEncoder 对文本 tokenize 后，在 max_len 超限时保留头部 head_frac（默认 25%）和尾部
75%。pair_collate 只在 batch 内右侧 padding，不改变 attention mask 中的真实长度。

单个 pair 的 PairDataset 返回：

```text
{"b": better_tokens, "w": worse_tokens}
```

pair_collate 将一个 batch 排成：

```text
[所有 better 序列, 所有 worse 序列]
```

因此 per-device batch size 2 实际每次 backbone 前向 4 条序列。Bradley-Terry loss 是：

```text
-mean(log sigmoid(score(better) - score(worse)))
```

当前 augmented batch value pair 的记录字段是 budget_steps，不是训练数据集读取的
budget 字段；而当前 launcher 不传 --budget-cond。所以这条主线实际是 budget-blind 的
静态 reward model。不要把 budget_steps 元数据误解为模型已经看到了预算。

## 6. validation、eval 和 checkpoint

bradley_terry.py 每隔 --eval-steps 调用 Trainer 的 eval dataset；当前 launcher 设置为每
10 个 optimizer step。一个 optimizer step 已经包含 gradient accumulation，不能把它理解成
每个 micro-batch。

训练配置的默认值来自 BradleyTerryConfig：

```text
eval_strategy             steps
save_strategy             best
metric_for_best_model     eval_pair_accuracy
greater_is_better         false
load_best_model_at_end    false
save_total_limit          1
```

因此当前代码会保留 Trainer 认定的 best checkpoint，但 greater_is_better=false 与
eval_pair_accuracy 的语义并不匹配；如果要按准确率选最好模型，应显式修正配置，而不是
根据旧文档假设它已经按最高准确率选择。

checkpoint 是 Hugging Face/Trainer 原生目录，通常包含：

```text
<output-dir>/checkpoint-<step>/
  model.safetensors
  trainer_state.json
```

训练脚本不会生成一份独立的最终 accuracy CSV。当前增强流程的主要训练输出是日志和
checkpoint；数据规模、context 长度等比较应在实验记录中显式保存。

## 7. 训练前 context 预检查

不要直接用字符长度估算 context。使用与训练相同的 tokenizer、CardEncoder、PairDataset、
pair_collate 和 DataLoader：

```bash
python -m src.mle_critic.src.postprocess.measure_context \
  --model Qwen/Qwen3-0.6B-Base \
  --pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
  --cards data/augmented_mle_critic/augmented_cards_current.json \
  --context-length 16384
```

脚本会分别报告 train/test/all 的平均 token 数、最大 token 数、超 context 的 sequence 比例，
以及任一侧超 context 的 pair 比例。测量时暂时把 CardEncoder max_len 提高到很大的值；如果
真的碰到这个临时上限，脚本会报错，避免把截断后的长度当成真实长度。

已在当前数据和 Qwen3-0.6B tokenizer 上测得：

```text
all pairs                  6976
average sequence length    3787.07
maximum sequence length    27603
sequences > 16384          9/13952 = 0.06%
pairs with either > 16384  7/6976   = 0.10%
```

这个统计是数据检查，不代表 Qwen3-8B 训练已经完成。

## 8. 轻量模型对照

为了判断收益是否来自代码字符表面特征，当前流程另外提供 sklearn baseline：

```bash
PYTHONPATH=. python -m src.mle_critic.src.train.light_predictor.train \
  --pairs data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl \
  --cards data/augmented_mle_critic/augmented_cards_current.json \
  --output tmp/light_predictor_results.json
```

支持三个模型：

| 模型 | 输入 |
| --- | --- |
| tfidf_lr | train-only 字符 3--5 gram TF-IDF + logistic regression |
| static_lr | 34 个 handcrafted features + scaled logistic regression |
| static_gbm | 同一组 34 个 features + histogram gradient boosting |

三个模型都使用 feature(better)-feature(worse)，并把每个 train pair 的反向顺序也加入训练。
默认随机 seed 为 7，train/test cap 分别为 24,000/6,000，可用 --models、--train-cap、
--test-cap 覆盖。cards reader 同时支持 grouped JSON 和 flat JSONL，并只读取 pair 需要的
Card。

## 9. 复现实验时应保存什么

至少保存以下版本化产物：

```text
augmented_cards_current.json
runsplit_holdruns.json
batch_value_pairs_filtered.jsonl
batch_value_pairs_filtered_runsplit.jsonl
训练命令和 git commit
模型 tokenizer 名称
context length、seed、batch size、gradient accumulation
```

raw pair 必须从当前 Cards 重建，不能每天直接 append：新后代会改变祖先的 reward/value，
新 batch 也会改变 cap 采样池。run split 可以增量更新，但已有 physical run 的 train/test
身份不能漂移。

## 10. 已删掉的旧说明

以下内容不再写入当前实验文档：学生版 L1/L2 数据生成、按预算 K 的 decision/flip 训练、
rescue launcher、旧 minimal_gap.json、训练脚本内的 80/20 validation、训练脚本内的
CSV/普通测试评估，以及旧的 sidecar 复现实验结论。它们可能仍存在于历史提交或未合并分支，
但不属于当前 augmented reward pipeline。
