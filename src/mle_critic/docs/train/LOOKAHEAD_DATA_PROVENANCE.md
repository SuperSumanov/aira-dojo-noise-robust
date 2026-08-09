# Lookahead 数据血缘和复原说明

这份文档把数据按流水线拆开说明。每一节都回答：原始来源是什么、如何提取/构建、服务哪个实验、当前文件能不能当作原件。

```text
AIRA-Dojo journals
  -> cards.py / build_cards.py
  -> cards_current.jsonl + card_run_map.json + task_orientation.json
       |-> build_subtree_pairs.py -> value_pairs_base.jsonl
       |                         -> build_runsplit.py -> value_pairs_runsplit.jsonl (L1)
       |-> repeated regrade -> regrade_tau_nodes.csv
       |-> build_budget_pairs.py -> budget_pairs_base.jsonl / budget_flip_base.jsonl
       |                         -> build_runsplit.py -> budget_pairs_v3_runsplit.jsonl (L2)
       |-> rescue_pairs.py -> rescue_*_rebuilt.jsonl
```

## 1. 版本和状态

代码来自 origin/phase1-value-critic commit ab580f3（2026-08-09）。当前 corpus 是 v7：按 26 个批次合并后重建为 10,755 张有标签 card、515 个物理 run。当前只保留 run-clean 数据，避免把旧的 tree/fragment split 当成有效评估结果。

| 文件 | 行数 | 状态 | 用途 |
| --- | ---: | --- | --- |
| cards_current.jsonl | 10,755 | v7 批次合并，注入 `run_id` | 当前所有 pair 生成和 RM 的 card 索引 |
| card_run_map.json | 10,755 条映射 | 按批次内 run 连续性重建，V1/V2 校验通过 | run-level split 的固定映射 |
| runsplit_holdruns.json | 约 20% runs | seed=7、按任务抽 held-out runs | 所有 run-clean pair 文件共用 |
| cards_senior_0806/0807.jsonl | 892 / 430 | 学生分支最新 LFS 批次 | v7 新增数据 |
| task_orientation.json | 22 条映射 | 原样提取 | 每个任务的分数方向 |
| regrade_tau_nodes.csv | 196 行含 header | 学生分支已提交，原样提取 | L2 噪声过滤 |
| rescue_*_rebuilt.jsonl | 5,314 至 9,404 | 从 rebuilt L2 派生 | LOTO rescue |
| value_pairs_runsplit.jsonl | 57,013 | L1 pair 按物理 run 重切，跨界丢弃 | L1 run-clean 评估/训练 |
| value_pairs_v4.jsonl | 91,052 | v7 corpus 重新生成的 run-clean L1 | 新 corpus 的 L1 训练候选 |
| budget_pairs_v3_runsplit.jsonl | 107,359 | L2 count-matched pair 按物理 run 重切 | L2 run-clean 训练/测试 |
| budget_flip_v3_runsplit.jsonl | 运行后生成 | 同一 run 规则重切的 flip/control 评估集 | L2 预算条件化评估 |
| decision_pairs_runsplit.jsonl | 4,455 | 同父兄弟决策对，按物理 run 切分 | 决策点实验 |
| results/*.csv | 各文件不同 | 学生分支已提交 | 历史结果，不是训练输入 |

当前大文件仍按仓库的 LFS 规则管理；重建命令会从 `data/mle_critic/raw/corpus_manifest.txt` 读取批次清单。

### 1.1 runsplit_holdruns.json

`runsplit_holdruns.json`由 `build_runsplit.py` 根据当前 corpus 的物理 run 映射生成：

1. 读取 `cards_current.jsonl`，用每张 card 的 `task.name` 和 `card_run_map.json` 建立 `task -> run_id` 集合；
2. 对每个任务分别取其全部唯一 run，按 run ID 排序；
3. 用固定 `seed=7` 的 `random.Random` 独立打乱该任务的 run 列表；
4. 取打乱后列表的后 20%：`runs[int(0.8 * len(runs)):]`；
5. 把所有任务的 held-out run 合并，按排序后的 run ID 写入 `runsplit_holdruns.json`。

因此它实现的是“每个任务内部约 80/20 按物理 run 切分”，不是全局随机抽 20% card。某个 pair 的规则随后固定为：两端 run 都在这个文件中才是 test，两端都不在才是 train，跨界 pair 丢弃。

当前文件由 v7 corpus 的 515 个 run 生成，使用的固定输入是：

```text
data/mle_critic/cards_current.jsonl
data/mle_critic/card_run_map.json
seed = 7
```

可以从仓库根目录复现或更新它（如果文件已存在，脚本会读取并复用已有 holdout，不会悄悄换测试集）：

```bash
python -m src.mle_critic.src.preprocess.build_runsplit \
  data/mle_critic/cards_current.jsonl \
  data/mle_critic/card_run_map.json \
  data/mle_critic/runsplit_holdruns.json \
  /tmp data/mle_critic/value_pairs_runsplit.jsonl --seed 7 --regenerate-hold
```

实际生成 L1/L2/decision 数据时，三者都必须传入同一个 `runsplit_holdruns.json`；新增 batch 或改变 run map 后，应先重新生成 holdout，再重新生成全部 pair 文件，不能只替换其中一个。

## 2. 原始来源：AIRA-Dojo journal

原始数据不是 MLEBench 的 train.csv/test.csv，而是每次 AIRA-Dojo MCTS run 的 journal：

```text
<run>/checkpoint/journal.jsonl
<run>/json/JOURNAL.jsonl
```

每行通常包含当前代码、journal step、父节点 parents、agent 自报 validation、MLEBench 外部评分 metric_info.score、任务名、指标方向、medal thresholds、运行时间和错误信息。原始 journal 没有提交到本仓库，所以这里无法重新生成完全相同的 run。

入口是 `src/mle_critic/src/preprocess/build_cards.py`，底层解析在 `cards.py` 的 `parse_journal` 和 `card_from_node_data`；离线合并后再由 `run_segment.py` / `add_run_id.py` 补上物理 run 信息：

1. 扫描两种 journal 路径，并按 run 目录去重；
2. 从 metric_info.competition_id 确定任务；
3. 跳过空 root；
4. 保存 code、self-report、runtime、parent、step、tree depth；
5. 将 metric_info.score 保存为 label.graded；
6. 用 medal thresholds 和指标方向计算 label.y_norm；
7. 丢弃没有正式外部 graded 分的节点，包括只有 HCE/T1 dval 的记录；
8. 按 card ID 去重并写 JSONL；合并批次后按文件内连续 run 重建 `run_id`，并验证父子节点不跨段、段内不混任务。

Card 的关键字段是：

```json
{"id":"task__node_uuid","task":{"name":"..."},"code":"...","obs":{"val_at_low":0.7,"runtime_s":123},"lineage":{"parent_id":"...","step":17,"tree_depth":3},"label":{"graded":0.81,"y_norm":0.62},"run_id":"cards_senior_0806.jsonl:12"}
```

后续所谓的“子树”只是在这些保留下来的 cards 中沿 parent_id 可达的图。被过滤掉的父节点会造成断链；无分节点也不会计入后代。

## 3. cards_current.jsonl 的具体输入

08ca3eb 的 rebuild_corpus.sh 按以下顺序合并已提交批次：

```text
cards_ours_20260727.jsonl
cards_senior_0724.jsonl
cards_senior_0726.jsonl
cards_senior_0727.jsonl
cards_senior_0728.jsonl
cards_senior_0729.jsonl
cards_senior_0730.jsonl
cards_senior_0731.jsonl
cards_senior_0801.jsonl
cards_gen2A.jsonl
cards_gen2B.jsonl
cards_gen2C.jsonl
cards_gen2D.jsonl
cards_gen3A.jsonl
cards_senior_0802.jsonl
cards_t3era_missing.jsonl
cards_senior_0803.jsonl
cards_deepA.jsonl
cards_gen2VAL.jsonl
cards_senior_0804.jsonl
cards_deepB2.jsonl
cards_gen2VALb.jsonl
cards_senior_0805seq.jsonl
cards_senior_0806.jsonl
cards_senior_0807.jsonl
```

当前合并结果是 10,755 行、10,755 个唯一 card ID、22 个任务、515 个重建 run。每张 card 带有 `run_id`；来源是批次内连续性重建，并由父节点同 run、单段不混任务两项检查约束。中间批次仍保留在 `data/mle_critic/raw`，便于审计和重建。

每次更新数据时，把新批次放入 `data/mle_critic/raw/` 并加入 `raw/corpus_manifest.txt`，然后运行 `bash src/mle_critic/scripts/rebuild_corpus.sh`。脚本会先拼接批次，再运行 `run_segment.py` 生成 `card_run_map.json`，最后由 `add_run_id.py` 写出带 run_id 的 `cards_current.jsonl`。

## 4. task_orientation.json

来源是学生分支 phase1/task_orientation.json，原样提取。它决定标签比较方向；true 表示 lower-is-better，而不是 higher-is-better。例如 lower-is-better 任务必须用 min(V_K(x), V_K(y)) 的方向判断 winner。

它被 build_subtree_pairs.py、build_budget_pairs.py、audit 脚本和 baseline 脚本共同使用。方向错一项，整项任务的 better/worse 都会反转。

## 5. tau：重复评分得到的噪声底

### 原始输入

学生先在相同容器/环境中重复执行同一个 card，并做 MLEBench 外部 regrade。原始输入是：

```text
regrade_results*.jsonl
regrade_manifest*.jsonl
```

这些 results 和 manifests 未提交，当前仓库只有汇总后的 regrade_tau_nodes.csv。

### 计算

入口是 compute_regrade_tau.py。对同一个 card 的重复分数 s1...sn 计算：

```text
tau(card) = population_std(s1, ..., sn)
offset(card) = mean(si) - original_graded
```

CSV 关键列为 card_id、competition、n_reps、tau、orig_graded、mean_rerun、offset、reps。

budget_pairs 生成器把同一任务所有可用 card 的 tau 排序，取约 p90，形成任务级 TAU[task]。每条具体的 (x,y,K) 记录只有在 abs(V_K(x)-V_K(y)) >= TAU[task] 时才保留。它没有使用 pair 两端各自 tau，也没有传播最佳后代的不确定性；没有 tau 数据的任务不会被过滤。

重新计算需要原始 results 和 manifest：

```bash
python -m src.mle_critic.src.preprocess.compute_regrade_tau \
  regrade_results.jsonl manifest_a.jsonl manifest_b.jsonl \
  --out data/mle_critic/regrade_tau_nodes_local.csv
```

## 6. L1：value_pairs_runsplit.jsonl

### 目的

L1 问题是：当前节点代码不变时，历史搜索树中哪个节点最终能通向更好的结果。标签定义为：

```text
V_full(n) = n 自己和 cards 图中全部可见后代的最佳 graded 分
```

它没有预算输入。

### 构建

入口是 `build_subtree_pairs.py`，产出的中间文件只作为重建输入，不作为训练/评估数据：

1. 用 parent_id 建 children 表；
2. 深度优先遍历全部可见后代；
3. 计算 V_full；
4. 没有可见后代或 V_full 相等时跳过；
5. 每任务最多 20,000 个 pair，seed=7；
6. 先写出 pair 候选和 lineage 元数据；
7. 写 better、worse、gap_raw、当前质量是否同向、子树规模和 split。

正式输入是 `value_pairs_runsplit.jsonl`（57,013 条）。它经过 `build_runsplit.py` 按 `card_run_map.json` 重切：两个端点都属于训练 run 才保留为 train，两个端点都属于 held-out run 才保留为 test，跨边界 pair 全部丢弃。`value_pairs_v4.jsonl`（91,052 条）是同一规则下在 v7 corpus 重新生成的候选版本。

每次更新数据时应该运行：

```bash
set -euo pipefail

# 从当前 corpus 的 card 元数据生成完整的方向表。不要沿用旧的
python - <<'PY'
import json
from pathlib import Path

data_dir = Path("data/mle_critic")
orientations = {}
with (data_dir / "cards_current.jsonl").open() as f:
    for line in f:
        card = json.loads(line)
        task = card["task"]
        # build_subtree_pairs 的格式是 lower_is_better，而 card 中存的是反向字段。
        lower_is_better = not task["higher_is_better"]
        previous = orientations.setdefault(task["name"], lower_is_better)
        if previous != lower_is_better:
            raise ValueError(f"inconsistent metric direction for {task['name']}")

with (data_dir / "task_orientation.json").open("w") as f:
    json.dump(orientations, f, indent=2, sort_keys=True)
    f.write("\n")
PY

# 1) 生成未切 run 的候选 pair（中间文件）
python -m src.mle_critic.src.preprocess.build_subtree_pairs \
  /tmp/value_pairs_base.jsonl \
  data/mle_critic/cards_current.jsonl \
  --orientation data/mle_critic/task_orientation.json \
  --cap 1500 \
  --seed 7 \
  --split-by tree

# 2) 按物理 run 重切；跨 run 边界的 pair 丢弃
python -m src.mle_critic.src.preprocess.build_runsplit \
  data/mle_critic/cards_current.jsonl \
  data/mle_critic/card_run_map.json \
  data/mle_critic/runsplit_holdruns.json \
  data/mle_critic \
  /tmp/value_pairs_base.jsonl \
  --out-name value_pairs_runsplit.jsonl

# 实验训练/评估只使用 data/mle_critic/value_pairs_runsplit.jsonl；
# 不要把中间候选或旧的 fragment-split 文件当作正式数据。
```

## 7. L2：budget_pairs_v3_runsplit.jsonl

### 目的

L2 才是在测试预算影响：给两个节点同样的 K 个后续尝试，哪个节点的最好结果更高。

```text
V_K(n) = n 自己和按 lineage.step 排序的前 K 个可见后代中的最佳 graded 分
K = 1, 2, 3, 5
```

K 不是墙钟时间、GPU 小时，也不是重新运行 MCTS K 次。

### 构建

入口是 `build_budget_pairs.py`：

1. 按 parent_id 回溯 tree root，最多 200 层；
2. 找到所有可达后代并按 lineage.step 排序；
3. 节点后代不足 K 时不定义 V_K；
4. 同任务枚举节点 pair；
5. V_K 相等的 pair 丢弃；
6. 先生成 count-matched pair 候选；run-level train/test 不在这里决定；
7. 使用每任务 cap=6000、K=1/2/3/5；
8. tau filter 删除 gap 小于任务噪声底的具体 (x,y,K)；
9. train 侧 flips_vs_b1=true 的记录重复 5 次，test 侧不重复；
10. 写 task、better、worse、budget、flips_vs_b1、gap_raw、intask_split 等字段。

训练记录不是独立程序数：同一个 pair 可以因四个 K 产生多条记录，flip boost 还会额外复制。

### run-level 生产流程

正式 L2 输入是 `budget_pairs_v3_runsplit.jsonl`（107,359 条）。先用 count-matched 生成器得到临时 pair 文件，再用 `build_runsplit.py` 和固定的 `card_run_map.json` / `runsplit_holdruns.json` 重分配：两端都在训练 run 才进 train，两端都在 held-out run 才进 test，跨界 pair 丢弃。

参数固定为 `ks=1,2,3,5`、`cap=6000`、`flip_cap=1200`、`seed=7`、`tau_filter=true`、`tau_quantile=0.9`、`flip_boost=5`。

```bash
# 1) 生成 count-matched 候选 pair 和 flip/control 候选
python -m src.mle_critic.src.preprocess.build_budget_pairs \
  /tmp/budget_pairs_base.jsonl /tmp/budget_flip_base.jsonl \
  data/mle_critic/cards_current.jsonl \
  --orientation data/mle_critic/task_orientation.json \
  --tau-csv data/mle_critic/regrade_tau_nodes.csv \
  --ks 1,2,3,5 --cap 6000 --flip-cap 1200 \
  --tau-filter --tau-quantile 0.9 --flip-boost 5 --seed 7

# 2) 对主 pair 应用固定物理 run split
python -m src.mle_critic.src.preprocess.build_runsplit \
  data/mle_critic/cards_current.jsonl \
  data/mle_critic/card_run_map.json \
  data/mle_critic/runsplit_holdruns.json \
  data/mle_critic \
  /tmp/budget_pairs_base.jsonl \
  --out-name budget_pairs_v3_runsplit.jsonl

python -m src.mle_critic.src.preprocess.build_runsplit \
  data/mle_critic/cards_current.jsonl data/mle_critic/card_run_map.json \
  data/mle_critic/runsplit_holdruns.json data/mle_critic \
  /tmp/budget_flip_base.jsonl --out-name budget_flip_v3_runsplit.jsonl
```

flip/control 评估数据也必须使用同一份 run 映射；它不是普通训练集，且不应混入 L2 主训练文件。

## 8. 决策对：decision_pairs_runsplit.jsonl

### 目的和构造

这份数据模拟搜索时比较同一父节点的候选，但严格说是“同父有分兄弟的事后 pair”，不是日志中一次完整的在线 MCTS decision event。构造过程是：

1. 按 `parent_id` 收集孩子，只保留有外部 grade 的孩子；同一父节点至少有两个孩子才形成 decision set。
2. 在每个 set 内枚举两两组合；无分兄弟会被排除，因此不应把它解释成完整的兄弟集合。
3. 对每个 pair 生成 K=0、1、2 三种标签：K=0 只比较孩子自身 grade；K=1/2 比较自身和按 `lineage.step` 排序的前 1/2 个可见后代中的最佳 grade。双方后代不足 K 时，该记录不生成。
4. 先生成候选 pair，再按 `card_run_map.json` 和固定 `runsplit_holdruns.json` 切分；两端都在 train run 才是 train，两端都在 held-out run 才是 test，跨界 set 丢弃。

最新文件 `decision_pairs_runsplit.jsonl` 共 4,455 条，run-clean 后训练侧约 3,194 对、测试侧 1,261 对。原始标签构成为 K=0 3,529、K=1 569、K=2 494；run-clean 测试中 K=0/1/2 分别为 947/170/144。由于 K=0 占多数，overall 主要反映同父兄弟的当前 grade 排序，不应直接称为纯 lookahead 能力。

### 生产流程

```bash
# 1) 从带 run_id 的 cards 生成同父兄弟候选（中间文件）
python -m src.mle_critic.src.preprocess.build_decision_pairs \
  /tmp/decision_pairs_base.jsonl data/mle_critic/cards_current.jsonl \
  --orientation data/mle_critic/task_orientation.json --ks 0,1,2 --seed 7

# 2) 使用与 L1/L2 相同的 run map 和 held-out runs
python -m src.mle_critic.src.preprocess.build_runsplit \
  data/mle_critic/cards_current.jsonl data/mle_critic/card_run_map.json \
  data/mle_critic/runsplit_holdruns.json data/mle_critic \
  /tmp/decision_pairs_base.jsonl --out-name decision_pairs_runsplit.jsonl
```

训练命令没有打开 `--budget-cond` 时，K=0/1/2 会混合成 budget-blind RM；因此 K=1/2 的结果只能作为小样本诊断，不能当作严格的预算条件化模型结论。

## 9. L2 flip/control 数据

L2 的 flip/control 候选是评估集，不是普通训练集。对同一个节点对：

- 小预算固定 K=1；
- 大预算为 K=2、3、5；
- winner 反转则 kind=flip；
- winner 不变则 kind=control；
- 每个任务/预算差最多 flip_cap 个 flip，并匹配 control。

评估会分别计算 score(x,K=1)、score(y,K=1)、score(x,K_hi)、score(y,K_hi)。预算盲模型在 flip pair 上的 acc_mean=0.5 是解析基线，因为它的两个输入完全相同；只有 conditioned 模型在输入尾部加入 K 后才可能改变排序。

## 10. Rescue 数据

### 目的

LOTO 跨任务迁移不稳定。rescue 问的是：保留跨任务训练池，再加入多少目标任务训练树 pair，才能恢复目标任务表现。

### 构建

入口是 build_rescue_pairs.py：

1. 从非目标任务记录随机取 4,000 条基础训练池；
2. 目标任务只取 intask_split=train；
3. 按 (better,worse) 去重，移除 flip boost 副本；
4. 抽 K 个有序 pair key；
5. 每个 key 保留它在可用预算下的所有记录；
6. 加入目标任务 test 记录，并按 (better,worse,budget) 去重；
7. 检查注入训练 pair 与测试 pair 没有相同 pair，也没有相同 node。

因此 K=500 是 500 个有序 pair key，不是 500 条记录。当前 rescue_*_rebuilt.jsonl 是从 rebuilt L2 派生的可运行替代品。

## 11. results/*.csv 是什么

这些文件是历史实验输出，不是训练数据：

| 文件 | 实验 |
| --- | --- |
| rm_lookahead_strong.csv | L1，N=24,000 |
| l2v2_blind.csv | L2 seed 7，无预算 |
| l2v2_cond_tail.csv | L2 seed 7，预算放尾部 |
| l2v2_blind_s13.csv | L2 seed 13，无预算 |
| l2v2_cond_s13.csv | L2 seed 13，预算放尾部 |
| l2v2_cond_s17.csv | L2 seed 17，预算放尾部 |
| loto_lookahead.csv | 五个任务的 LOTO |
| rescue_nomad.csv / rescue_petfinder.csv | rescue 多个 dose/seed 的结果 |

分支没有 blind seed 17 的 CSV；调查里提到的该格无法从提交单独复核。

## 12. 推荐操作顺序

只使用 run-clean L1 输入：

```bash
accelerate launch --config_file src/mle_critic/recipes/zero3.yaml \
  --num_processes 1 src/mle_critic/src/train/bradley_terry.py \
  --pairs data/mle_critic/value_pairs_runsplit.jsonl \
  --cards data/mle_critic/cards_current.jsonl \
  --max-len 2048 \
  --output-dir outputs/mle_critic/l1_full
```

重新运行 L2：

```bash
bash src/mle_critic/scripts/build_lookahead_datasets.sh
bash src/mle_critic/scripts/train_l2_budget.sh blind 7
bash src/mle_critic/scripts/train_l2_budget.sh conditioned 7
```

从新的 Dojo runs 开始时，先生成新 cards，再重新计算 tau、L1/L2 pairs 和 rescue。不要把旧 pairs、旧 tau 和新 cards 混用，因为这些文件通过 card ID、lineage 和任务分布绑定在一起。
