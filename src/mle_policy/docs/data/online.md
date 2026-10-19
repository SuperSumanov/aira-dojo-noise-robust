# 手动Online训练

## 复用旧流程

由于多个集群之间不能直连，所以数据生产，汇总，训练，和模型部署都是手动完成的。其中数据汇总的过程如下，首先下载和解压数据

```bash
PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.download_journals \
  --url https://drive.google.com/drive/folders/1NGEBRqush6M7e3kVXWupNJ1WQCdwt6oN?usp=drive_link \
  --output-dir data/augmented_mle_critic/raw_journal/comparison/1014

PYTHONPATH=src/mle_critic python \
  -m src.preprocess.download_and_resolve.unzip \
  data/augmented_mle_critic/raw_journal/comparison/1014
```

随后基本上和现存的数据处理流程相同，不过为了确保online，每轮的训练数据只从上个checkpoint里面出来


```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
OUT_ROOT=data/mle_policy/online_score_day2
mkdir -p $OUT_ROOT
bash src/mle_policy/scripts/data/build_all_batches.sh data/augmented_mle_critic/raw_journal/comparison/1015 "$OUT_ROOT"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/assign_splits.sh "$OUT_ROOT" run 0.1
bash src/mle_policy/scripts/data/to_grpo.sh "$OUT_ROOT"

python my_recipes/mle_policy/src/dataset/build_grpo_parquet.py \
  --input  ../../data/mle_policy/online_score_day1/thinking/grpo.jsonl \
  --output-dir data/mle_policy_grpo/thinking \
  --model-path Qwen/Qwen3.8-27B \
  --max-length 65536 \
  --enable-thinking true \
  --reasoning-effort medium
```

为了保证公平，我们也测试直接拿metric进行训练

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
OUT_ROOT=data/mle_policy/online_metric_day1
mkdir -p $OUT_ROOT
bash src/mle_policy/scripts/data/build_all_batches.sh data/augmented_mle_critic/raw_journal/comparison/1014 "$OUT_ROOT"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/assign_splits.sh "$OUT_ROOT" run 0.1
bash src/mle_policy/scripts/data/to_grpo_metric.sh "$OUT_ROOT"

python my_recipes/mle_policy/src/dataset/build_grpo_parquet.py \
  --input  ../../data/mle_policy/online_metric_day1/thinking/grpo.jsonl \
  --output-dir data/mle_policy_grpo/thinking \
  --model-path Qwen/Qwen3.8-27B \
  --max-length 65536 \
  --enable-thinking true \
  --reasoning-effort medium
```

## 新流程

旧的数据流程只读小journal，而有些没有小journal的run（不知道是不是qwen3.8-27b太蠢连两个solution都跑不出来）就完全被浪费了。因为数据生产实在太慢，所以我们打算把大journal也利用起来。流程和上面几乎一致，只需要换一个脚本即可

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
OUT_ROOT=data/mle_policy/online_score_day3
mkdir -p $OUT_ROOT
bash src/mle_policy/scripts/data/build_all_batches_bigjournal.sh data/augmented_mle_critic/raw_journal/comparison/1017 "$OUT_ROOT"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/assign_splits.sh "$OUT_ROOT" run 0.1
bash src/mle_policy/scripts/data/to_grpo.sh "$OUT_ROOT"

python my_recipes/mle_policy/src/dataset/build_grpo_parquet.py \
  --input  ../../$OUT_ROOT/thinking/grpo.jsonl \
  --output-dir data/mle_policy_grpo/thinking \
  --model-path Qwen/Qwen3.8-27B \
  --max-length 65536 \
  --enable-thinking true \
  --reasoning-effort medium
```

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
OUT_ROOT=data/mle_policy/online_metric_day3
mkdir -p $OUT_ROOT
bash src/mle_policy/scripts/data/build_all_batches_bigjournal.sh data/augmented_mle_critic/raw_journal/comparison/1018 "$OUT_ROOT"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$OUT_ROOT"
bash src/mle_policy/scripts/data/assign_splits.sh "$OUT_ROOT" run 0.1
bash src/mle_policy/scripts/data/to_grpo_metric.sh "$OUT_ROOT"

python my_recipes/mle_policy/src/dataset/build_grpo_parquet.py \
  --input  ../../$OUT_ROOT/thinking/grpo.jsonl \
  --output-dir data/mle_policy_grpo/thinking \
  --model-path Qwen/Qwen3.8-27B \
  --max-length 65536 \
  --enable-thinking true \
  --reasoning-effort medium
```