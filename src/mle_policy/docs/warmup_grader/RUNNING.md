# Warmup MCTS 实验命令

在仓库根目录执行，使用 `aira-dojo` 环境。批量入口沿用现有 `aira_mcts_qwen_medium_lora` 实验的 8 个 seed，并覆盖 benchmark 和 solver。

## 1. 准备数据版本

已有本机 v1 可直接使用。需要新切分时，从现有 prepared 数据生成新目录：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
competition=chaii-hindi-and-tamil-question-answering
python -m dojo.tasks.mlebench.warmup.prepare \
  --data-dir data/mlebench \
  --competition-id "$competition" \
  --output "data/mlebench_warmup/$competition/v1" \
  --seed 0
```

已有目标目录会报错。切分 seed 与 solver 的 8 个实验 seed 相互独立；实验间共享同一数据版本。当前支持的任务和规模见 `DESIGN.md`，逐任务细节见 `datasets/`。

## 2. 检查批量配置

下面的命令只展开配置、显示 8 个 seed 的任务列表，`launcher.debug=true` 时不提交 GPU 作业。四个 client 覆盖保留实验配置里的 medium reasoning 设置。

```bash
python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_mcts_qwen_medium_lora \
  benchmark=mlebench/warmup \
  benchmark.warmup_root="$PWD/data/mlebench_warmup" \
  benchmark.warmup_version=v1 \
  'benchmark.tasks=[chaii-hindi-and-tamil-question-answering]' \
  solver=mlebench/warmup_mcts \
  'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.draft.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.improve.llm.client=litellm_qwen3.8-27b' \
  metadata.git_issue_id=chaii-warmup-mcts-8seeds \
  solver.execution_timeout=7200 \
  solver.time_limit_secs=86400 \
  solver.num_children=4 \
  launcher=srun_pool \
  launcher.debug=true \
  launcher.max_parallel=4 \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

`benchmark=mlebench/warmup` 决定生成 warmup task，`solver=mlebench/warmup_mcts` 决定使用 warmup analyze，两者配套。`warmup_root` 使用绝对路径，worker 共享访问对应文件系统。默认原测试答案仍来自 `data/mlebench`；若源 prepared 数据在其他位置，可加 `+benchmark.overrides.cache_dir=/绝对路径/mlebench`。

## 3. 启动正式实验

先申请满足并行数的 allocation。4 路并行、每路 6 CPU / 1 GPU 对应至少 24 CPU / 4 GPU；分区和时限按机器额度填写。例如：

```bash
salloc \
  --account=gpu \
  --qos=csci5540 \
  --partition=csci5540 \
  --nodes=1 \
  --ntasks=4 \
  --cpus-per-task=6 \
  --gpus-per-node=4
```

在 allocation 中执行：

```bash
python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_mcts_qwen_medium_lora \
  benchmark=mlebench/warmup \
  benchmark.warmup_root="$PWD/data/mlebench_warmup" \
  benchmark.warmup_version=v1 \
  'benchmark.tasks=[chaii-hindi-and-tamil-question-answering]' \
  solver=mlebench/warmup_mcts \
  'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.draft.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.improve.llm.client=litellm_qwen3.8-27b' \
  metadata.git_issue_id=chaii-warmup-mcts-8seeds \
  solver.execution_timeout=7200 \
  solver.time_limit_secs=86400 \
  solver.num_children=4 \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=4 \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

已有独立 allocation 时，可加 `launcher.allocation_job_id=<jobid>`。2 GPU allocation 将 `launcher.max_parallel` 改为 2。实验继承原 Jupyter interpreter 配置，容器路径、数据挂载与模型服务沿用当前集群设置。

常用调整：

- 多任务：`'benchmark.tasks=[chaii-hindi-and-tamil-question-answering,tgs-salt-identification-challenge,dog-breed-identification,tensorflow2-question-answering]'`，每个任务读取自己的 v1。
- 单 seed：`'vars.metadata.seed=[1]'`；使用新数据版本：`benchmark.warmup_version=v2`。
- 保留 Greedy：`solver=mlebench/warmup_greedy`，同时去掉 MCTS 专用的 `solver.num_children` 参数。
- 切换模型：一起覆盖 analyze/debug/draft/improve 的 client。模型专用的 generation kwargs 也需要与实验配置保持一致。

## 4. 结果和回归检查

每轮提交的 `results/grading_report.json` 保存原测试结果和 warmup 字段，`results/warmup_report.json` 保存 warmup 汇总。搜索节点的 analysis 记录诊断解释，正常节点继续按 CV 排序。数据版本的 manifest 位于 `warmup_root/<task>/<version>/private/manifest.json`。

```bash
pytest -q tests/test_mlebench_warmup.py tests/test_blind_ts.py tests/test_slurm_migration.py
```

实现结构和反馈字段见 `DESIGN.md`；具体数据排列与评分行为见 `datasets/`。
