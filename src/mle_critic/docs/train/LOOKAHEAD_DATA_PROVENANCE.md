# Lookahead 数据血缘和复原说明

这份文档把数据按流水线拆开说明。每一节都回答：原始来源是什么、如何提取/构建、服务哪个实验、当前文件能不能当作原件。

```text
AIRA-Dojo journals
  -> cards.py / build_cards.py
  -> cards_current.jsonl + task_orientation.json
       |-> value_pairs.py -> value_pairs_v3.jsonl (L1)
       |-> repeated regrade -> regrade_tau_nodes.csv
       |-> budget_pairs_matched.py -> budget_pairs_v2_rebuilt.jsonl
       |                            -> budget_flip_v2_rebuilt.jsonl
       |-> rescue_pairs.py -> rescue_*_rebuilt.jsonl
```

## 1. 版本和状态

代码来自 origin/phase1-value-critic commit b5aa5fe。正式 L1/L2 的基础 corpus 是 commit 08ca3eb 时的 7,190-card corpus，而不是后来增加到 7,880 张的版本。

| 文件 | 行数 | 状态 | 用途 |
| --- | ---: | --- | --- |
| cards_current.jsonl | 7,190 | 按 08ca3eb 的版本化批次重建 | 所有 pair 生成和 RM 的 card 索引 |
| task_orientation.json | 22 条映射 | 原样提取 | 每个任务的分数方向 |
| value_pairs_v3.jsonl | 86,651 | 学生分支已提交，原样提取 | L1 subtree-best RM |
| regrade_tau_nodes.csv | 196 行含 header | 学生分支已提交，原样提取 | L2 噪声过滤 |
| budget_pairs_v2_rebuilt.jsonl | 81,019 | 提交版脚本重建 | L2 训练/普通测试 |
| budget_flip_v2_rebuilt.jsonl | 1,618 | 提交版脚本重建 | L2 flip/control 评估 |
| rescue_*_rebuilt.jsonl | 5,314 至 9,404 | 从 rebuilt L2 派生 | LOTO rescue |
| results/*.csv | 各文件不同 | 学生分支已提交 | 历史结果，不是训练输入 |

cards_current 的 SHA-256 是 dbbd5674937c2ebcbf222df591ad522218454d532d2c89844890e1ed8daedd43；value_pairs_v3 的 SHA-256 是 021400b54be1a5bd8524dc592b975e081b55cea07603a4754f77cf2dfc2f2f4b。JSONL 已在 .gitattributes 中配置 Git LFS。

## 2. 原始来源：AIRA-Dojo journal

原始数据不是 MLEBench 的 train.csv/test.csv，而是每次 AIRA-Dojo MCTS run 的 journal：

```text
<run>/checkpoint/journal.jsonl
<run>/json/JOURNAL.jsonl
```

每行通常包含当前代码、journal step、父节点 parents、agent 自报 validation、MLEBench 外部评分 metric_info.score、任务名、指标方向、medal thresholds、运行时间和错误信息。原始 journal 没有提交到本仓库，所以这里无法重新生成完全相同的 run。

入口是 src/mle_critic/src/preprocess/build_cards.py，底层解析在 cards.py 的 parse_journal 和 card_from_node_data：

1. 扫描两种 journal 路径，并按 run 目录去重；
2. 从 metric_info.competition_id 确定任务；
3. 跳过空 root；
4. 保存 code、self-report、runtime、parent、step、tree depth；
5. 将 metric_info.score 保存为 label.graded；
6. 用 medal thresholds 和指标方向计算 label.y_norm；
7. 丢弃没有正式外部 graded 分的节点，包括只有 HCE/T1 dval 的记录；
8. 按 card ID 去重并写 JSONL。

Card 的关键字段是：

```json
{"id":"task__node_uuid","task":{"name":"..."},"code":"...","obs":{"val_at_low":0.7,"runtime_s":123},"lineage":{"parent_id":"...","step":17,"tree_depth":3},"label":{"graded":0.81,"y_norm":0.62}}
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
```

当前合并结果是 7,190 行、7,190 个唯一 card ID、22 个任务。中间批次没有再复制到 data/mle_critic，因为 pair 生成只需要合并后的 cards，且中间批次会带来大量重复。

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

## 6. L1：value_pairs_v3.jsonl

### 目的

L1 问题是：当前节点代码不变时，历史搜索树中哪个节点最终能通向更好的结果。标签定义为：

```text
V_full(n) = n 自己和 cards 图中全部可见后代的最佳 graded 分
```

它没有预算输入。

### 构建

入口是 build_subtree_pairs.py，原学生文件名是 phase1/value_pairs.py：

1. 用 parent_id 建 children 表；
2. 深度优先遍历全部可见后代；
3. 计算 V_full；
4. 没有可见后代或 V_full 相等时跳过；
5. 每任务最多 20,000 个 pair，seed=7；
6. 按 tree root 做约 80/20 留树，任一端在 held-out tree 的 pair 为 test，其余为 train；
7. 写 better、worse、gap_raw、当前质量是否同向、子树规模和 split。

value_pairs_v3.jsonl 已在 b5aa5fe 提交，是 L1 正式训练输入。当前 cards 重跑生成器仍会得到 86,651 行，但 capped 任务的具体抽样记录不完全相同；要复现学生的 0.8183，应使用仓库中的原文件，不要用本地重新生成文件替换它。

## 7. L2：budget_pairs_v2_rebuilt.jsonl

### 目的

L2 才是在测试预算影响：给两个节点同样的 K 个后续尝试，哪个节点的最好结果更高。

```text
V_K(n) = n 自己和按 lineage.step 排序的前 K 个可见后代中的最佳 graded 分
K = 1, 2, 3, 5
```

K 不是墙钟时间、GPU 小时，也不是重新运行 MCTS K 次。

### 构建

入口是 build_budget_pairs.py，原学生文件名是 phase1/budget_pairs_matched.py：

1. 按 parent_id 回溯 tree root，最多 200 层；
2. 找到所有可达后代并按 lineage.step 排序；
3. 节点后代不足 K 时不定义 V_K；
4. 同任务枚举节点 pair；
5. V_K 相等的 pair 丢弃；
6. 先 split 再 cap：两个端点都在训练树才是 train，两个都在 held-out tree 才是 test，跨边界 pair 丢弃；
7. 使用每任务 cap=6000、K=1/2/3/5；
8. tau filter 删除 gap 小于任务噪声底的具体 (x,y,K)；
9. train 侧 flips_vs_b1=true 的记录重复 5 次，test 侧不重复；
10. 写 task、better、worse、budget、flips_vs_b1、gap_raw、intask_split 等字段。

训练记录不是独立程序数：同一个 pair 可以因四个 K 产生多条记录，flip boost 还会额外复制。

### 为什么是 rebuilt

学生命令引用 phase1/budget_pairs_v2.jsonl 和 phase1/budget_flip_v2.jsonl，但两个文件从未提交。当前使用 b5aa5fe 的生成器、7,190 cards 和：

```text
ks=1,2,3,5
cap=6000
flip_cap=1200
seed=7
tau_filter=true
tau_quantile=0.9
flip_boost=5
```

得到 81,019 条主记录、809 个 flip（另有匹配 control）。调查中的 103,969 条未增强记录和 686/526/252 flip ladder 与此不完全一致，说明实际工作区还存在未提交的脚本版本、参数或输入文件。文件因此保留 _rebuilt 后缀，不能冒充原 v2。

## 8. L2 flip/control 数据

budget_flip_v2_rebuilt.jsonl 是评估集，不是普通训练集。对同一个节点对：

- 小预算固定 K=1；
- 大预算为 K=2、3、5；
- winner 反转则 kind=flip；
- winner 不变则 kind=control；
- 每个任务/预算差最多 flip_cap 个 flip，并匹配 control。

评估会分别计算 score(x,K=1)、score(y,K=1)、score(x,K_hi)、score(y,K_hi)。预算盲模型在 flip pair 上的 acc_mean=0.5 是解析基线，因为它的两个输入完全相同；只有 conditioned 模型在输入尾部加入 K 后才可能改变排序。

## 9. Rescue 数据

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

## 10. results/*.csv 是什么

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

## 11. 推荐操作顺序

只使用学生正式 L1 输入：

```bash
python -m src.mle_critic.src.train.bradley_terry \
  --pairs data/mle_critic/value_pairs_v3.jsonl \
  --cards data/mle_critic/cards_current.jsonl \
  --sizes 24000 --max-len 2048 \
  --deepspeed src/mle_critic/src/train/ds_zero3_offload.json
```

重新运行 L2：

```bash
bash src/mle_critic/scripts/build_lookahead_datasets.sh
bash src/mle_critic/scripts/train_l2_budget.sh blind 7
bash src/mle_critic/scripts/train_l2_budget.sh conditioned 7
```

从新的 Dojo runs 开始时，先生成新 cards，再重新计算 tau、L1/L2 pairs 和 rescue。不要把旧 pairs、旧 tau 和新 cards 混用，因为这些文件通过 card ID、lineage 和任务分布绑定在一起。
