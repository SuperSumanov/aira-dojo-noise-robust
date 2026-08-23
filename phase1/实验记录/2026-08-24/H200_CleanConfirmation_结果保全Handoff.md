# H200 结果保全与 clean-confirmation handoff

日期：2026-08-24

状态：`EXPLORATORY_RESULTS_PRESERVE_NOW / CLEAN_CONFIRMATION_NOT_AUTHORIZED`

对象：学长 `dojo-reproduce` H200 训练；只做已有产物保全与未来确认链交接。本文不授权新 GPU、API、模型拟合、
future truth 读取或 test 推理。

## 0. 先给结论

1. `myfork/dojo-reproduce@62964aae03229b8ed6ac8ba5eb40d0060d543025` 新增了三份 H200 launcher；当前三个
   H200 scheduler job 的实际 WorkDir 是学长自己的 `/research/d2/gds/zzchen2/mle_project/aira-dojo-noise-robust`，
   尚未取得逐 job source commit/launcher receipt，因此不能未经保全就断言它们精确运行了 `62964aa`。无论实际
   commit 最终为何，这批 checkpoint、日志和指标目前**全部只能标为 exploratory**。最关键原因不是旧的
   `greater_is_better` 方向 bug——当前代码已是 `true`——而是训练进程仍把 outer `intask_split=test` 当作周期
   eval，checkpoint 因而 test-touched；同时缺少 experiment-closed train/dev/frozen、test 前 lock、逐 pair
   endpoint predictions、checkpoint manifest 和排他 one-shot ledger。
2. 这些产物仍有价值：可以保留容量趋势、训练稳定性、显存/耗时和下一轮预算依据；但**不能**通过事后补哈希、
   重新挑 checkpoint、补跑一次 test 或改称 frozen，把它们升级成确认结果。
3. 当前应立即做的是“内容盲保全”：不筛选或抄录未发布 metric，只复制完整目录并对文件、源码、数据和配置做哈希；
   不要删 checkpoint。正式确认另起全新 experiment，使用已冻结的
   `critic-scaling-confirmation-contract-v1`，严格跑 Qwen3-Base
   `{0.6,1.7,4,8}B × seeds {6,7}` 的 8-run matrix。
4. 按 2026-08-23 顶层入口，当前唯一主实验是 **mechanism commit 后 300 个 physical runs 的 score-channel
   dual-truth 复现**；更早已激活的 first-960 predictor cohort 是另一套仍需保持封存的确认资产，不能覆盖当前主实验。
   两者 closure 前都不得打开各自 label/outcome vault；本 handoff 也不创建第二套可提前揭盲的“确认集”。

## 1. 本 handoff 锁定的源码身份

### 1.1 学长已推送的 H200 代码（不冒充逐 job source receipt）

- 分支：`myfork/dojo-reproduce`；
- 最新审计 commit：`62964aae03229b8ed6ac8ba5eb40d0060d543025`；
- parent：`ac008af8b907d319b694f26b0ba9cf4053b3bf69`；
- 该 commit 只新增下列三份 launcher：

三者都把第一个位置参数作为 seed，未传时默认为 `6`。

| launcher | Git blob | 当前真正会执行的模型 | pair 输入 | epochs / eval cadence |
|---|---|---|---|---|
| `src/mle_critic/scripts/train/h200/train_aug_reward.sh` | `ebfec1c4ba96a868c69f1818cae2f31119a56240` | 仅 14B；0.6/1.7/4/8B 均被注释 | `$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl` | 1 / 每 10 steps |
| `src/mle_critic/scripts/train/h200/train_aug_reward_decision.sh` | `d884d6330303c500f142494c6922da0fe8264d8b` | 0.6、1.7、4、8、14B，顺序执行 | `$DATA_DIR/merged_decision_pairs_filtered_runsplit.jsonl` | 2 / 每 9 steps |
| `src/mle_critic/scripts/train/h200/train_mixed_decision_value.sh` | `1d2904ca8babb4915a2f756a2524441f7246604b` | 14、8、4、1.7B，顺序执行；缺 0.6B | `$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl` | 1 / 每 10 steps |

三份 launcher 均 source：

- `src/mle_critic/scripts/experiment_env_augmented_data.sh`，blob
  `aa07325ab11aa1e977e96fd712b6d16b493083e3`；
- trainer：`src/mle_critic/src/train/bradley_terry.py`，blob
  `06db36c997222277fd0e0abc84ef3a76ea7c096d`；
- trainer config：`src/mle_critic/src/train/config/bradley_terry_config.py`，blob
  `13cb390fc39efda2e29d6e78a0d4a3dab05c76cf`；
- Accelerate/ZeRO 配置：`src/mle_critic/recipes/zero3.yaml`。

环境脚本真实默认值是：

```text
DATA_DIR   = $REPO_ROOT/data/augmented_mle_critic
OUTPUT_DIR = $REPO_ROOT/outputs/augmented_mle_critic
LOG_DIR    = $REPO_ROOT/logs/augmented_mle_critic
TRAIN_SCRIPT = $REPO_ROOT/src/mle_critic/src/train/bradley_terry.py
ACCELERATE_CONFIG = $REPO_ROOT/src/mle_critic/recipes/zero3.yaml
```

但 `MLE_CRITIC_DATA_DIR`、`MLE_CRITIC_OUTPUT_DIR`、`MLE_CRITIC_LOG_DIR` 可以覆盖前三项。因此保全时必须记录**运行时
解析后的绝对路径**，不能把上述默认路径当作实际路径。

2026-08-24 的只读 scheduler snapshot 显示：job `11408/11410/11411` 均为 `RUNNING`，分别申请 `2/2/4`
张 GPU，TimeLimit 均为 24 小时，WorkDir 均为
`/research/d2/gds/zzchen2/mle_project/aira-dojo-noise-robust`；scheduler 只对 `11408` 暴露
`Command=/bin/bash`，另两项为 `Command=(null)`。这些字段只证明资源与工作目录，不证明 Git commit、实际 launcher、
模型、seed 或数据路径。故第 3 节必须从各 job 的真实工作目录/Slurm stdout 与启动命令取得身份，不得拿我方远端
`/research/d7/.../aira-dojo-reproduce` 的旧且无关 worktree HEAD 回填。

### 1.2 已冻结的 clean-confirmation 接口

- 人类合同：`phase1/contracts/CRITIC_SCALING_CONFIRMATION_V1.md`；
- 机器合同：`phase1/critic_scaling_confirmation_contract_v1.json`；
- 机器合同 SHA-256：
  `579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568`；
- 分析 producer：`phase1/critic_scaling_confirmation_analysis.py`；
- 独立分析 verifier：`phase1/verify_critic_scaling_confirmation_analysis.py`；
- outcome-blind materializer：`phase1/critic_scaling_confirmation_materializer.py`；
- 独立 source-binding verifier：`phase1/verify_critic_scaling_confirmation_materialization.py`；
- materialization 合同：`phase1/contracts/CRITIC_SCALING_CONFIRMATION_MATERIALIZATION_V1.md`。

上游 overlay 只在 `dojo-reproduce@ac008af8b907d319b694f26b0ba9cf4053b3bf69` 上按下列顺序做过 exact-base
验证：

1. `phase1/upstream_patches/0001-Harden-critic-confirmation-protocol.patch`，SHA-256
   `2fd5ca7b38e4277b68c2eb90b42c0f0ce85b8ab0ef687802e68ceeb8f0fc1fe2`；
2. `phase1/upstream_patches/0002-Allow-fixed-step-critic-budget-calibration.patch`，SHA-256
   `89d7af494e436c4d5a7ed5c4a06e43c4d012cb26c3efd3c1e9f52bf00b3bd641`；
3. `phase1/upstream_patches/0003-Record-critic-wall-clock-receipts.patch`，SHA-256
   `a4146bdc6ef3123e3b88a3b909352dd40db3cff992503919d4207c1756313f67`；
4. `phase1/upstream_patches/0004-Emit-endpoint-score-receipts.patch`，SHA-256
   `237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`。

不要把 patch 文件名相近的 `0001-Enforce-exact-experiment-strata-6-focused-tests-pass.patch` 混入上述四补丁序列。
`62964aa` 是 `ac008af` 的子提交，但 overlay 尚未以 `62964aa` 为 exact base 重新验收；若坚持在最新 commit 上移植，
必须先 `git apply --check`、跑同一聚焦/完整测试并形成新 receipt，不能沿用 `ac008af` 的通过记录。

## 2. 为什么三类 H200 作业只能 exploratory

当前 trainer 的真实行为是：`load_training_pool` 读取 `intask_split=train`，`load_testing_pool` 读取
`intask_split=test`，随后把 test pool 直接交给 Hugging Face Trainer 作为 `eval_dataset`。因此这不是“test 进入梯度”的
指控，而是更准确的 **outer test 被训练过程周期访问并参与 checkpoint 保存**：

- `eval_strategy=steps`；
- `save_strategy=best`；
- `metric_for_best_model=eval_pair_accuracy`；
- `greater_is_better=true`（当前方向正确，旧 bug 已修）；
- `save_total_limit=1`；
- `load_best_model_at_end=false`。

据此逐项裁决：

| 当前作业 | 可保留用途 | 不能支持的主张 |
|---|---|---|
| augmented value / 14B | 14B 可训练性、资源和 exploratory value 指标 | 不在冻结 0.6–8B 主矩阵；test-touched；单 seed 默认值不能确认 scaling |
| merged decision / 0.6–14B | 同一旧 decision pool 内的探索性模型尺寸曲线 | 两 epochs 与其他臂不同；outer test 周期 eval；14B 是未预注册 extension；不能称 frozen confirmation |
| mixed decision+value / 1.7–14B | 0DV 已恢复的 mixed recipe 与探索性混合监督现象 | 缺 0.6B；不是精确 8-run matrix；旧 mixed test 与 merged-decision test 相同且已被周期访问；不能代替 0EA 五臂或 clean scaling |

另外，`train_aug_reward.sh` 与 `train_aug_reward_decision.sh` 对相同 model/seed 使用相同命名。例如两者的 14B
均写：

```text
$OUTPUT_DIR/Qwen3-14B_reward_seed${SEED}
$LOG_DIR/Qwen3-14B_reward_seed${SEED}.log
```

两份 launcher 没有“目录必须不存在”的排他门，且日志使用 `>`，第二次启动会截断同名日志。若两类 14B 作业曾共用
`OUTPUT_DIR/LOG_DIR/SEED`，该 run 必须标记 `AMBIGUOUS_OUTPUT_COLLISION`；不得凭 checkpoint 时间或最后一行日志猜来源。
在确认归属前不要启动另一个同名作业。

0EA 的 `L1/Lbudget/Gbudget/G→L/Ghash→L` 五臂仍是
`REVISED_CANDIDATE_PROTOCOL_IDENTITY_G0_BUDGET_BLOCKED`。上述三份 H200 launcher 没有 Ghash 负控、同 token/step
五臂合同或单旋钮隔离，不能事后给它们贴上 0EA arm 名称。

## 3. 现在就做的结果保全（0 GPU、0 API、0 新推理）

### 3.1 先冻结删除动作和 run 身份

对每个已提交或完成的 scheduler job 单独建立 `run_id`，至少包含：

```text
scientific_arm__qwen3-<size>b__seed-<seed>__scheduler-<jobid>__start-<UTC>
```

先记录 job id、提交脚本、实际 seed、开始/结束 UTC、节点、GPU 型号/数量、退出码和当前 output/log 绝对路径。若作业仍在
运行，只标记 `RUNNING_DO_NOT_DELETE`；不要把正在变化的目录哈希冒充最终 manifest。作业退出后再做最终内容盲复制和哈希。

### 3.2 每个 run 必须保留的五组资产

#### A. checkpoint/output 完整树

保留实际 output directory 的完整目录树，而不是只留下某个“最好”的 `model.safetensors`。对**实际存在**的文件全部做
SHA-256，特别包括：

- 每个仍存在的 `checkpoint-*`；
- `model.safetensors`；
- `trainer_state.json`、`training_args.bin`、scheduler/optimizer state（若实际存在）；
- `config.json`、tokenizer 文件、`head.pt`、`rm_meta.json`（若实际存在）；
- 根目录与 checkpoint 子目录内的其他 Trainer/Accelerate 状态文件。

当前 `save_total_limit=1` 可能已经只保留一个 checkpoint；不要把缺失的中间 checkpoint 写成“已保留”。若训练中断，状态写
`PARTIAL` 并保留现场，不能用最后一次 metric 猜成 `COMPLETE`。

#### B. 原始日志与 scheduler/W&B 收据

保留 launcher 重定向的完整 `.log`、Slurm stdout/stderr、`scontrol show job`/提交参数、W&B run id 与离线目录（若存在）。
保全阶段只复制和哈希，不筛选或抄录未发布 metric。若同名日志已被 `>` 截断，明确写
`LOG_TRUNCATION_POSSIBLE`，不要重建缺失部分。

#### C. 数据与 split 身份

不需要把大文件提交到 Git，但必须保存以下**实际运行时文件**的绝对路径、bytes、rows 和 SHA-256：

- 对应三者之一：
  - `$DATA_DIR/batch_value_pairs_filtered_runsplit.jsonl`；
  - `$DATA_DIR/merged_decision_pairs_filtered_runsplit.jsonl`；
  - `$DATA_DIR/decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl`；
- `$DATA_DIR/augmented_cards_current.json`。

另保留 pair builder 命令、seed、source-batch manifest/receipt 和 train/test row count。不要把旧 test 改名为 dev；不要重排、过滤
或覆盖原文件后继续沿用旧 SHA。0DV 的后验 recipe-recovery/replay 证据应与本次实际 pair SHA 一起保留；它只解决
recipe reconstruction，不等于补回生成时缺失的原始 receipt，也不解决 test touch。

#### D. 代码、模型和环境身份

每个 run 记录：

- `git rev-parse HEAD`；
- launcher path + Git blob；
- `experiment_env_augmented_data.sh`、`bradley_terry.py`、`bradley_terry_config.py`、`zero3.yaml` 的 blob/SHA；
- 实际展开后的完整命令与所有环境覆盖项；
- `../verl_models/Qwen3-*-Base` 的 resolved absolute path 与不可变 revision；若本地目录没有 Hugging Face commit，生成整个
  模型快照的文件 manifest SHA-256，不得只记目录名；
- Python、PyTorch、Transformers、Accelerate、DeepSpeed、CUDA/NCCL、driver 版本；
- Python/NumPy/Torch/launcher seed；当前 launcher 未显式记录 `PYTHONHASHSEED`，如未设置就写 `UNRECORDED`，不得补写。

#### E. predictions 与 ledger

当前 trainer 不产生满足确认合同的逐 pair endpoint prediction，也没有排他 one-shot ledger。处理规则只有两条：

- 如果此前已经产生过 prediction/ledger，原样保存文件、绝对路径、SHA 和生成命令，并标
  `EXPLORATORY_TEST_TOUCHED`；
- 如果没有，明确写 `MISSING_NOT_RETROFILLED`。**不要现在补跑旧 frozen/test 推理**，更不能事后伪造
  `test_attempts=1` 或 `LOCKED_BEFORE_TEST_ACCESS`。

### 3.3 内容盲保全的命令框架

下列命令只展示如何解析真实路径和生成 manifest；先把占位符替换为该 job 的真实值。保全根必须是一个新建、不会与训练
目录重名的共享路径，本文不猜远端绝对路径。

```bash
set -euo pipefail
repo_root=$(git rev-parse --show-toplevel)
data_dir=${MLE_CRITIC_DATA_DIR:-$repo_root/data/augmented_mle_critic}
output_dir=${MLE_CRITIC_OUTPUT_DIR:-$repo_root/outputs/augmented_mle_critic}
log_dir=${MLE_CRITIC_LOG_DIR:-$repo_root/logs/augmented_mle_critic}

run_id='<arm>__qwen3-<size>b__seed-<seed>__scheduler-<jobid>__start-<UTC>'
keep_root='<new-immutable-shared-preservation-root>'
run_keep="$keep_root/$run_id"
mkdir -p "$run_keep"

git rev-parse HEAD > "$run_keep/source_commit.txt"
git status --porcelain=v1 > "$run_keep/source_worktree_status.txt"
git diff --binary > "$run_keep/source_uncommitted.patch"

# 作业已经退出后，复制真实 output/log；不要在这里挑 checkpoint。
rsync -a --checksum '<resolved-run-output-dir>/' "$run_keep/output/"
cp -a '<resolved-run-log>' "$run_keep/"

find "$run_keep" -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$run_keep/files.sha256"
```

若 `git status` 非 clean，`source_uncommitted.patch` 是必要资产；但它可能含私密路径或凭据，先做 credential scan，只能放共享
保全区，未经检查不得提交 Git。模型权重、原始日志、`.env`、W&B 凭据和 raw tar 也不得提交 Git。

## 4. 从 exploratory 过渡到 clean confirmation 的唯一合法链

以下都是**下一轮预算获批后**才执行的步骤。现在只准备，不运行。

### 4.1 新建独立 clean worktree，不改现有 H200 输出

最低风险基线是学长 `ac008af8b907d319b694f26b0ba9cf4053b3bf69` 加第 1.2 节四份 overlay；该组合已有
focused 36/36 的工程验收。四份 patch 必须按顺序校验 SHA、`git apply --check` 后应用，再跑 fresh no-smudge 聚焦测试和
完整回归。若改以 `62964aa` 为 base，必须产生新的 exact-commit verification receipt。

overlay 新增的单-run 训练入口是真实路径：

```text
src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh
```

目录名 `pro6000` 不等于训练硬件授权；在 H200 上使用仍需另行给出 scheduler matrix、GPU 数、wall cap 和总 GPU·时并获批。
该 launcher 每次只允许一个 model×seed、新 output dir、新 log path，且不接受 test path。

### 4.2 先闭合数据与 split，再训练

1. 使用 future、experiment-closed source batch；exact stratum 固定为
   `(task.name, client, hardware, time_limit, execution_timeout)`，任何 physical run 混 stratum 都 fail closed。
2. 在 physical-run 层做 train/dev/frozen test 零交集；train/dev 只能来自 outer-train runs。
3. Trainer 进程只挂载 dedicated train/dev/Cards；frozen test 路径在训练环境中不可见。周期 eval 只能读 dev。
4. primary 只接受 `pair_semantics=canonical_raw_sibling`。其他 semantics 只能另列 extension。
5. clean-scaling 必须另有结果前绑定的 dedicated future pairs/Cards、closure receipt 与单独揭盲授权；在这些资产齐备前，
   任何人都不得运行 materializer 的真实 `truth` 子命令。当前 300-run score-channel cohort 与旧 first-960 cohort
   都不能在结果后自动改作 clean-scaling test，也不得读取其 label/outcome vault。

### 4.3 精确训练矩阵与固定项

正式矩阵恰为 8 个 run：

```text
Qwen3-Base {0.6B, 1.7B, 4B, 8B} × seeds {6, 7}
```

缺一个、重复一个或多一个均 fail closed。14B 只能在另行预注册后作为 extension，不能补进 primary matrix。所有 run
除 model size/seed 外必须固定：source pairs/Cards、prompt/rendering、max length、head fraction、task/budget conditioning、
optimizer、learning rate、scheduler、warmup、有效 pair batch、token/step budget、eval cadence 和 dev checkpoint 规则。

每个 run 必须训练完成，并且只按 dev `eval_pair_accuracy` 选 checkpoint：

```text
metric_for_best_model = eval_pair_accuracy
greater_is_better = true
load_best_model_at_end = true
```

训练前需另交 exact matrix、8 个 run 的 GPU 数、wall cap 和总 GPU·时。当前机器合同仍明确是
`gpu_jobs_authorized=0 / model_fits_authorized=0`。

### 4.4 test 前必须先形成 checkpoint manifest

每个选定 checkpoint 单独写一个不可变 manifest，字段名必须与 materializer 一致：

```json
{
  "protocol": "critic-scaling-checkpoint-manifest-v1",
  "status": "LOCKED_BEFORE_TEST_ACCESS",
  "model_size_b": 0.6,
  "seed": 6,
  "artifacts": {
    "model.safetensors": "<sha256>",
    "head.pt": "<sha256-if-present>",
    "rm_meta.json": "<sha256-if-present>",
    "config.json": "<sha256-if-present>"
  }
}
```

`model.safetensors` 必须存在。`head.pt/rm_meta.json/config.json` 中凡 evaluator 目录里实际存在者都必须入 manifest；不存在者
不得凭空填写。manifest 本身再计算 SHA-256。大权重留共享存储，Git 只保留 manifest/hash 和非敏感 receipt。

### 4.5 test 前 lock 的真实字段

truth 只能由获授权的 custodian 在 closure 后生成；研究者无需查看数值内容，但 lock 必须绑定其 hash/rows。完整 lock 至少为：

```json
{
  "protocol": "critic-scaling-confirmation-lock-v1",
  "status": "LOCKED_BEFORE_TEST_ACCESS",
  "contract_sha256": "579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568",
  "source_commit": "<40-or-64-hex>",
  "frozen_at_utc": "<UTC-ending-in-Z>",
  "dataset": {
    "split": "test",
    "truth_sha256": "<sha256>",
    "truth_rows": 1,
    "pairs_sha256": "<sha256>",
    "cards_sha256": "<sha256>"
  },
  "baseline": {
    "id": "char_tfidf_lr",
    "fit_scope": "train_only",
    "receipt_sha256": "<sha256>"
  },
  "runs": [{
    "model_size_b": 0.6,
    "seed": 6,
    "base_model": "<pinned-Qwen3-Base-snapshot>",
    "model_revision": "<40-or-64-hex>",
    "checkpoint_manifest_sha256": "<sha256>",
    "one_shot_output_path_sha256": "<sha256-of-resolved-absolute-path-utf8>",
    "one_shot_ledger_path_sha256": "<sha256-of-resolved-absolute-path-utf8>",
    "checkpoint_locked_before_test_access": true,
    "training_status": "COMPLETE",
    "selected_on_dev_only": true,
    "checkpoint_step": 1,
    "dev_selection_metric": 0.0
  }]
}
```

上面的数值 `1/0.0` 只是类型示例，必须替换为真实 step/dev metric；8 个 run 都要列出。绝对 output/ledger 路径的身份哈希
应调用仓库已有实现，不要另写一套规范：

```bash
python -c 'from pathlib import Path; from phase1.critic_scaling_confirmation_materializer import path_identity; print(path_identity(Path("<absolute-path>")))'
```

lock 必须在首次 test access 前进入 Git 历史。看到 test 后再补 checkpoint、换路径、换 seed、换 step 或改 manifest，本轮即作废。

### 4.6 一次性 evaluator 输出与 ledger

四补丁 overlay 后的 evaluator 路径是：

```text
src/mle_critic/src/evaluation/bradley_terry_evaluation.py
```

正式 test 调用必须提供 `--split test`、不可覆盖的 `--output`、不可覆盖的 `--one-shot-ledger`，以及 pairs、Cards、
`model.safetensors` 和所有实际存在可选 artifact 的 expected SHA。`--eval-cap` 在 test 禁止。调用前先生成排他 ledger；即使
崩溃或 hash 错误也消耗该 checkpoint 的唯一尝试，不得删 ledger 重试。

upstream one-shot output 的协议/关键字段是：

```json
{
  "protocol": "rm-one-shot-test-v1",
  "split": "test",
  "n_pairs": 1,
  "artifacts": {
    "pairs": "<sha256>",
    "cards": "<sha256>",
    "model.safetensors": "<sha256>"
  },
  "pair_predictions": [{
    "pair_index": 0,
    "task": "<task>",
    "pair_semantics": "canonical_raw_sibling",
    "parent": "<card-id>",
    "parent_run_id": "<run-id>",
    "better": "<card-id>",
    "worse": "<card-id>",
    "endpoint_run_ids": ["<run-id>", "<run-id>"],
    "better_score": 0.0,
    "worse_score": 0.0,
    "margin": 0.0
  }]
}
```

正式源 ledger 必须是 `protocol=rm-one-shot-test-v1`、`status=COMPLETE`，并精确绑定
`expected_artifacts/observed_artifacts/output/result.output_sha256/result.n_pairs`。随后
`critic_scaling_confirmation_materializer.py model-prediction` 才能将其规范化为每行：

```text
pair_id / better_score / worse_score / margin
```

并生成 analyzer 使用的 derived ledger：

```json
{
  "status": "COMPLETE",
  "test_attempts": 1,
  "lock_sha256": "<sha256>",
  "truth_sha256": "<sha256>",
  "prediction_sha256": "<sha256>",
  "checkpoint_manifest_sha256": "<sha256>"
}
```

所有模型与 TF-IDF 必须覆盖完全相同的 truth/pair IDs；任何缺失、重复、反向 pair、nonfinite、endpoint score 不一致或
component 不连通均 fail closed。

### 4.7 bundle 与双实现验收

bundle root 内只允许相对普通文件，禁止绝对路径、`..` 和 symlink。materializer 的真实 CLI 是：

```text
truth            --pairs --cards --expected-pairs-sha256 --expected-cards-sha256 --source-commit --output --receipt
model-prediction --truth --expected-truth-sha256 --lock --expected-lock-sha256
                 --one-shot-output --expected-one-shot-output-sha256
                 --one-shot-ledger --expected-one-shot-ledger-sha256
                 --checkpoint-manifest --checkpoint-manifest-sha256 --output --ledger
bundle           --contract --expected-contract-sha256 --lock --expected-lock-sha256
                 --root --inputs --expected-inputs-sha256 --output
```

其中真实 `truth` 阶段当前禁止执行。最终 bundle 必须由 producer 和不 import producer 的 analysis verifier 同时通过；
source binding 还必须由 `verify_critic_scaling_confirmation_materialization.py` 的 `truth/model` 两个入口独立复核。只有双实现
一致且支持门通过，结果才能进入论文表格。

## 5. 交付给我方时的最小目录与状态词

### 5.1 exploratory H200 保全包

```text
<run_id>/
  run_receipt.json
  source_commit.txt
  source_worktree_status.txt
  source_uncommitted.patch
  command.txt
  environment.txt
  scheduler.txt
  data_manifest.json
  model_source_manifest.json
  output/
  <launcher-log>
  files.sha256
```

`run_receipt.json` 必须显式写：

```text
classification = EXPLORATORY_TEST_TOUCHED
completion = COMPLETE | PARTIAL | RUNNING_DO_NOT_DELETE | AMBIGUOUS_OUTPUT_COLLISION
predictions = PRESENT_EXPLORATORY | MISSING_NOT_RETROFILLED
eligible_for_clean_confirmation = false
```

### 5.2 future clean 包

只有新 experiment 才能交付：

```text
contract.json + pre-test-lock.json
truth.jsonl + truth receipt
TF-IDF fit receipt + predictions + ledger
8 × checkpoint manifest
8 × one-shot output + source ledger
8 × normalized predictions + derived ledger
bundle-inputs.json + bundle.json
producer result + independent verifier result + artifact manifest
```

## 6. 停止条件与明确禁止

- 任何现有 H200 checkpoint 已接触 outer test：立即保持 exploratory，不争辩“只看过均值”或“没进梯度”。
- 任何 output/log 路径碰撞：标记歧义并保全现场，不通过修改时间猜归属。
- 任一 clean run 缺失、未完整训练、非 dev-only 选择、无 exact model revision 或无 checkpoint manifest：test 前停止。
- train/dev/test 在 endpoint、unordered pair 或 physical run 上任一交集：停止。
- dedicated clean-scaling closure receipt 缺失或 future truth 未获单独授权：停止在 truth/test 之前；不得用当前
  300-run score-channel 或旧 first-960 cohort 事后替代。
- 不得定位或运行已正式撤回的旧 v11 b0/b1/b2 checkpoint scoring。
- 不得把 mixed/14B、0EA 五臂或 confidence-cost extension 偷换进 primary 8-run scaling matrix。
- 不得只交聚合 accuracy；正式交付必须有逐 pair endpoint scores、逐 task/run/component 统计与两个 seed。
- 不得把大权重、`.env`、API key、原始带 key 的 tar、未扫描日志提交 Git；只提交经过凭据扫描的 manifest/receipt/hash。
- 本文不授权 GPU/API/model fit/base-LLM update/future truth；预算和揭盲必须另行批准。

## 7. 本文依据的源码与合同

- `AGENTS.md`（工作区上层，2026-08-21 方向覆盖）；
- `phase1/ADVISOR_DIRECTIVES.md`；
- `phase1/CURRENT_DIRECTION.md` 的 0EP、0EA、0DV、0DS；
- `dojo-reproduce@62964aa` 的三份 H200 launcher；
- `src/mle_critic/scripts/experiment_env_augmented_data.sh`；
- `src/mle_critic/src/train/bradley_terry.py`；
- `src/mle_critic/src/train/config/bradley_terry_config.py`；
- `src/mle_critic/src/train/dataset/pairs.py`；
- `phase1/contracts/CRITIC_SCALING_CONFIRMATION_V1.md`；
- `phase1/contracts/CRITIC_SCALING_CONFIRMATION_MATERIALIZATION_V1.md`；
- `phase1/critic_scaling_confirmation_contract_v1.json`；
- `phase1/critic_scaling_confirmation_analysis.py` 与独立 verifier；
- `phase1/critic_scaling_confirmation_materializer.py` 与独立 source verifier；
- `phase1/upstream_patches/README.md` 及 0001–0004 clean-confirmation overlay；
- `phase1/tests/test_critic_scaling_confirmation_analysis.py`；
- `phase1/tests/test_critic_scaling_confirmation_materializer.py`。

本文编写过程未读取未发布 H200 metric，未打开 future truth，未调用 GPU/API，也未提交 Git。
