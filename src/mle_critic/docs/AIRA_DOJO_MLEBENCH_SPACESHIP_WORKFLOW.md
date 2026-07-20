# 用 Spaceship Titanic 复现 AIRA-Dojo × MLE-bench：`dojo-reproduce` 流程

本文以 `spaceship-titanic` 为贯穿示例，分别说明：

1. **`dojo-reproduce` 分支的默认复现和采数流程**：superimage + Jupyter interpreter + 原始 AIRA operators + GPT-4o/o3 配置。
2. **研究分支的差异**：DeepSeek + Python interpreter + prompt/metric 解析改动，以及可选 HCE 评测协议。

如果目标是复现原仓库结果或按原协议采数据，应以第一部分为准。第二部分只用于解释旧的研究分支，不能和原仓库结果直接混算。

## 0. 先明确代码来源边界

当前 `dojo-reproduce` 分支的 Git 边界如下：

| 类别 | 边界/代表提交 | 含义 |
|---|---|---|
| 原仓库基线 | `c795d86` | 复现所依据的上游代码快照 |
| 本机 superimage 适配 | 原提交 `ec6f741`、`9fb0e92`；本分支为 `aef1ed0`、`2a99670` | 为当前机器编译镜像所做的依赖和版本适配；因基点不同，cherry-pick 后 commit ID 改变 |
| 当前分支 | `dojo-reproduce` | `c795d86` 加上述两个适配提交；不包含学生研究分支提交 |

因此本分支可以直接作为代码级复现和正式采数 checkout。工作区中若有个人文档或实验文件，不会改变上述代码边界；正式运行前仍建议用 `git status` 记录工作区状态。

---

# 第一部分：原 AIRA-Dojo 仓库默认流程

## 1. 原仓库中的 Spaceship 是什么

`spaceship-titanic` 是上游 MLE-bench registry 自带的开发任务，来自 Kaggle 入门比赛 Spaceship Titanic：

- 类型：表格二分类。
- 目标列：`Transported`。
- 指标：accuracy，越高越好。
- 原始训练集约 8,700 行。
- 数据很小，适合做端到端 smoke test。

它存在于：

```text
src/dojo/tasks/mlebench/mle-bench/mlebench/competitions/spaceship-titanic/
```

上游 MLE-bench 还把它列在：

```text
mle-bench/experiments/splits/dev.txt
mle-bench/experiments/splits/spaceship-titanic.txt
```

Dojo 原仓库从初始提交起就有任务配置：

```text
src/dojo/configs/task/mlebench/spaceship-titanic.yaml
```

它不是学生新增的任务。不过它不属于正式的 75-task benchmark，也不属于 MLE-bench Lite，不能计入正式 Lite/All 汇总成绩。

## 2. 原仓库运行链路总览

```text
Kaggle competition zip
        |
        v
Dojo prepare.py + 上游 MLE-bench preparer
        |
        +-- prepared/public/   给 agent 看
        `-- prepared/private/  只给 evaluator 看
        |
        v
Hydra 原始 experiment 配置
        |
        +-- interpreter: jupyter
        +-- solver: mlebench/greedy、mcts 或 evo
        +-- operators: 原始 AIRA prompts
        `-- LLM: GPT-4o / o3
        |
        v
Singularity superimage 内启动 Jupyter kernel
        |
        +-- ./data 只读绑定 prepared/public
        +-- agent 生成并执行候选 Python 代码
        `-- 候选写 ./submission.csv
        |
        v
MLEBenchTask 校验 submission
        |
        v
MLE-bench 使用 prepared/private/test.csv 评分
        |
        v
journal/checkpoint/search_data/tree/grading_report
```

原仓库默认的隔离边界是 superimage/Jupyter，而不是宿主 Python 子进程。你已经编译好的 superimage 正是这条流程需要的运行环境。

## 3. 原仓库前置环境

### 3.1 Python 环境

请跟随README中的说明安装aira-dojo，设置环境变量，编译superimage，和安装MLEBench，检查实际 import 来源：

```bash
python - <<'PY'
import inspect
import dojo, aira_core, mlebench

print("dojo:", inspect.getsourcefile(dojo))
print("aira_core:", inspect.getsourcefile(aira_core))
print("mlebench:", inspect.getsourcefile(mlebench))
PY
```

代码级复现时，三个路径都应指向当前 `dojo-reproduce` checkout 或其明确固定的依赖版本。

### 3.2 环境变量与 `salloc`/`srun` 的关系

原仓库至少依赖：

```dotenv
LOGGING_DIR=/absolute/path/to/logs
MLE_BENCH_DATA_DIR=/absolute/path/to/mlebench-data
SUPERIMAGE_DIR=/absolute/path/to/repo/build/superimage/
```

#### 3.2.1 项目自己的 Slurm 默认值

旧 Submitit/`sbatch` launcher 使用下面三个项目环境变量决定提交到哪里：

```dotenv
DEFAULT_SLURM_ACCOUNT=gpu
DEFAULT_SLURM_PARTITION=gpu_2h
DEFAULT_SLURM_QOS=gpu
```

`srun_pool` 本身不使用它们：account、partition 和 QoS 已由外层手工执行的 `salloc` 决定，pool 只在该 allocation 内创建 step，不会再次申请资源。不过当前 `main_runner_job_array` 在导入时仍会加载旧 `SlurmConfig`，因此运行 5.2/5.3 的 pool 命令前，这三个变量目前也必须存在于进程环境中。这是旧 launcher 留下的启动耦合，不是 pool 的资源配置。

另外，`main_runner_job_array` 调用 `load_dotenv()` 晚于 `SlurmConfig` 的模块导入，所以仅把变量写进 `.env` 还不够稳妥；应像第 5 节那样先执行 `set -a; source .env; set +a`，确保它们在启动 Python 前已经导出。5.1 直接调用 `main_run` 不经过 launcher，理论上不需要这三个变量。

#### 3.2.2 allocation 和 step

`salloc` 和 `srun` 做的是两件不同的事：

```text
salloc
  -> 向 Slurm 申请一个顶层 allocation（节点、GPU、CPU、时限、account/QoS）
  -> allocation 获批后启动一个 shell
  -> salloc 进程持续持有 allocation 的生命周期

srun --jobid=<allocation-id>
  -> 不申请新的顶层作业
  -> 在已有 allocation 中创建一个 job step
  -> 从 allocation 剩余资源中取得 CPU/GPU 并启动进程
```

退出 `salloc` 启动的 shell 后，`salloc` 通常随之结束并释放整个 allocation，其中尚未结束的 step 也会失去资源。因此 pool controller 可以在登录节点运行，但原来的 `salloc` 会话必须保持存活；`srun_pool` 不接管或延长 allocation 生命周期。

`salloc` shell 用起来比较特殊，主要是因为 Slurm 自动向它注入了 allocation 上下文。常见变量包括：

```text
SLURM_JOB_ID             顶层 allocation ID
SLURM_JOB_NODELIST       分配到的节点
SLURM_NNODES             节点数
SLURM_JOB_CPUS_PER_NODE  每个节点分到的 CPU
SLURM_SUBMIT_DIR         发起 allocation 时的目录
```

所以在这个 shell 中直接执行 `srun ...` 时，`srun` 可以从 `SLURM_JOB_ID` 自动知道要使用哪个 allocation。这些变量是上下文和默认参数，不是访问资源的秘密凭证；真正的 allocation、所有者和状态由 Slurm controller 保存并校验。

通常，同一用户也可以在另一个登录 shell 中显式附着到仍在运行的 allocation：

```bash
srun --jobid=12345 --exclusive ...
```

这时另一个 shell 不需要继承原 shell 的 `SLURM_JOB_ID`，因为 job ID 已经显式给出。前提是原 `salloc` 进程仍在持有 allocation、job 处于 `RUNNING`，而且集群策略允许该用户从当前提交节点创建 step。不同集群可能对外部附着、提交主机或 step 创建有额外限制，因此不能把这种方式视为所有集群都保证的接口；最稳妥的操作仍是在 `salloc` shell 中启动 controller。

当前 `srun_pool` 两种方式都支持：

1. 默认读取 controller 环境中的 `SLURM_JOB_ID`，适合直接在 `salloc` shell 中运行。
2. 通过 `launcher.allocation_job_id=12345` 显式指定 allocation，适合从另一个 shell 附着。

无论采用哪种方式，pool 都先用 `scontrol show job` 检查 allocation 是否为 `RUNNING`、是否属于当前用户以及 CPU/GPU 是否足够；随后每次启动 worker 都显式执行：

```text
srun --jobid=<allocation-id> --exclusive ...
```

因此 pool 的并发控制不是靠复制环境变量实现的，而是 controller 为每个 RunConfig 创建一个独立 Slurm step。`--exclusive` 让并发 step 不复用同一份已分配 CPU/GPU。worker 进入 step 后，Slurm 还会设置 step 级变量：

```text
SLURM_JOB_ID    仍是顶层 allocation ID，例如 12345
SLURM_STEP_ID   当前 step ID，例如 0、1、2
CUDA_VISIBLE_DEVICES  当前 step 可见的 GPU，由 Slurm/cgroup 配置
```

所以一次实验的完整标识是 `SLURM_JOB_ID.SLURM_STEP_ID`，例如 `12345.2`。GPU 隔离本身由本集群的 Slurm GRES 和 device cgroup 完成，不是仅靠 `CUDA_VISIBLE_DEVICES` 这个环境变量完成。

`SUPERIMAGE_DIR` 当前必须以 `/` 结尾，因为 `sand` 脚本会直接把目录字符串与 `superimage.root.<version>.sif` 拼接。

原仓库的 `litellm_4o.yaml` 和 `litellm_o3.yaml` 是 Azure/OpenAI 示例配置，`base_url` 仍是 placeholder：

```text
https://<<<YOUR_AZURE_ENDPOINT_HERE>>>.azure-api.net
```

正式运行前必须填入可用 endpoint，并设置 LiteLLM client 使用的 key，例如：

```dotenv
PRIMARY_KEY_GPT_4O=...
PRIMARY_KEY_O3=...
# 或通用 fallback：
PRIMARY_KEY=...
```

模型 endpoint、deployment 名和 API 版本属于复现条件，采数时应记录在实验元数据中。

### 3.3 使用当前分支已编译的 superimage

当前机器上的镜像文件是：

```text
build/superimage/superimage.root.2026-07-macos-v1.sif
```

详细的编译流程来自`src/mle_critic/docs/BUILD_SUPERIMAGE_ON_MACOS.md`。当前分支已把：

```yaml
superimage_version: "2026-07-macos-v1"
```

写入 `src/dojo/configs/interpreter/jupyter.yaml`。因此命令行通常不必再覆盖 `interpreter.superimage_version`。这属于本机运行适配，不是学生的 DeepSeek/HCE 协议；当前镜像的依赖集合与历史镜像不完全相同，所以这里复现的是原流程和代码，不宣称逐包复现历史运行环境。

### 3.4 Kaggle 认证

准备数据需要 **Kaggle Legacy API Credentials**：

```text
~/.kaggle/kaggle.json
```

或者：

```bash
export KAGGLE_USERNAME=...
export KAGGLE_KEY=...
```

应先在 Kaggle 网页接受 Spaceship Titanic 比赛规则。测试是否通过认证：

```bash
python - <<'PY'
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()
print(api.competitions_list())
PY
```

## 4. 原仓库的数据准备流程

数据准备代码和 Spaceship preparer 都来自上游流程，

```bash
set -a
source .env
set +a

python src/dojo/tasks/mlebench/utils/prepare.py \
  -c spaceship-titanic \
  --data-dir="$MLE_BENCH_DATA_DIR"
```

发生的事情：

1. 从 Kaggle 下载 Spaceship zip。
2. 校验官方固定 checksum。
3. 解压 Kaggle 原始数据。
4. 调用 `spaceship-titanic/prepare.py`。
5. 从原始 `train.csv` 按 `test_size=0.1, random_state=0` 切出私有测试集。
6. 公开训练部分写入 `prepared/public/train.csv`。
7. 私有测试特征写入 `prepared/public/test.csv`。
8. 带 `Transported` 标签的同一测试部分写入 `prepared/private/test.csv`。
9. 生成 `sample_submission.csv` 和 `description.md`。
10. Dojo wrapper 生成 `prepared/public.tar`。

预期目录：

```text
$MLE_BENCH_DATA_DIR/
`-- spaceship-titanic/
    `-- prepared/
        |-- public/
        |   |-- description.md
        |   |-- train.csv
        |   |-- test.csv
        |   `-- sample_submission.csv
        |-- private/
        |   `-- test.csv
        `-- public.tar
```

`checksums.yaml` 和 `leaderboard.csv` 位于 MLE-bench 代码 registry，不会复制到数据目录。

## 5. 用当前代码跑 Spaceship

原仓库的单次配置仍然是：

```text
src/dojo/configs/_exp/run_example.yaml
```

它使用 Jupyter/superimage、MLE-bench Greedy、GPT-4o operators 和 `step_limit=5`，默认任务是 `aerial-cactus-identification`。改成 Spaceship 后，可以先只解析 Hydra 配置，不启动模型或容器：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
set -a
source .env
set +a

python -m dojo.main_run \
  +_exp=run_example \
  task.name=spaceship-titanic \
  logger.use_wandb=false \
  --cfg job --resolve
```

这里涉及两个不同目录：

- `srun_pool` 的 code snapshot 是当前仓库源码的一份固定副本，位于 `$LOGGING_DIR/aira-dojo/snapshots/<timestamp>/`。worker 从该副本加载 Dojo，避免同一批任务因运行期间修改 checkout 而混用不同代码；它不是 LLM 的工作目录。
- 每个实验都有独立的 `${logger.output_dir}/workspace_agent/`，以读写方式挂载到容器的 `/workspace`。LLM 可以在其中写代码、模型、中间文件和 `submission.csv`；MLE-bench public data 单独只读挂载到 `/workspace/data`。workspace 保留在宿主实验目录中，但每轮评分后 Dojo 会删除 `submission.csv`，避免下一轮误用旧结果。

### 5.1 单次直接运行

如果只是验证原始单次入口，可以在已经申请好的 Slurm allocation 中显式启动一个 step：

```bash
srun \
  --jobid="$SLURM_JOB_ID" \
  --exclusive \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=2 \
  --gres=gpu:1 \
  python -m dojo.main_run \
    +_exp=run_example \
    task.name=spaceship-titanic \
    metadata.seed=42 \
    logger.use_wandb=false
```

这种方式最接近原来的 `run_example`，但它绕过了新 launcher，不创建 code snapshot 和 pool manifest，也没有 controller 级重试和恢复。它适合排查单个 Spaceship 运行本身，不适合正式并行采数。不要在 `salloc` 返回的 shell 中直接运行 `main_run`；应通过上面的 `srun` 让任务真正进入带 GPU 隔离的 job step。

### 5.2 用 `srun_pool` 跑一个 seed

新 launcher 的入口是 `main_runner_job_array`。它需要 benchmark 配置，因此这里复用与 `run_example` 算法设置一致的 `runner_example`，在命令行把 benchmark 缩成 Spaceship，并把 seed 缩成一个：

```bash
python -m dojo.main_runner_job_array \
  +_exp=runner_example \
  'benchmark.tasks=[spaceship-titanic]' \
  'vars={metadata.seed:[42]}' \
  launcher=srun_pool \
  launcher.debug=true \
  launcher.max_parallel=1 \
  launcher.cpus_per_step=2 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

`launcher.debug=true` 只展开并打印任务，不创建 snapshot，也不启动 `srun`。确认输出只有一个 `spaceship-titanic` 后，在一个至少包含 1 GPU、2 CPU 的单节点 allocation 中改成：

```bash
python -m dojo.main_runner_job_array \
  +_exp=runner_example \
  'benchmark.tasks=[spaceship-titanic]' \
  'vars={metadata.seed:[42]}' \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=1 \
  launcher.cpus_per_step=2 \
  launcher.gpus_per_step=1 \
  launcher.min_remaining_seconds_to_launch=0 \
  logger.use_wandb=false
```

短 smoke allocation 可以这样申请：

```bash
salloc \
  --account=gpu \
  --qos=gpu \
  --partition=gpu_2h \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=2 \
  --gpus-per-node=1 \
  --time=02:00:00
```

不要添加 `--mem`、`--mem-per-cpu` 或 `--mem-per-gpu`。`min_remaining_seconds_to_launch=0` 只适合这次短链路验证；较长采集应恢复默认的 1800 秒保护，避免 allocation 即将结束时仍启动新任务。

5.1 和 5.2 最终都调用 `dojo.main_run._main()`，所以在 task、seed、solver、interpreter 和 LLM 配置相同时，运行的是同一套 Spaceship 求解逻辑。区别在调度外壳：5.1 从当前 checkout 直接运行；5.2 从固定 snapshot 运行，并增加 manifest、独立 attempt 日志、重试、恢复和并发补位。因此两者在算法层面等价，但不是运行管理和产物层面的完全相同；即使 seed 相同，远程 LLM 和 GPU 训练也不保证逐步复现。不要让 5.1 和 5.2 同时运行同一配置，以免写入相同实验目录。

### 5.3 多 seed 并行

例如并行跑 seed 1、2、3，先申请同一节点上的 3 GPU 和 6 CPU：

```bash
salloc \
  --account=gpu \
  --qos=gpu \
  --partition=gpu_8h \
  --nodes=1 \
  --ntasks=3 \
  --cpus-per-task=2 \
  --gpus-per-node=3 \
  --time=08:00:00
```

进入 allocation shell 后运行：

```bash
python -m dojo.main_runner_job_array \
  +_exp=runner_example \
  'benchmark.tasks=[spaceship-titanic]' \
  'vars={metadata.seed:[1,2,3]}' \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=3 \
  launcher.cpus_per_step=2 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

controller 会维持最多 3 个独立的 `srun --exclusive` step，每个 step 使用 1 GPU、2 CPU。每个实验的 metadata 记录完整的 `allocation.step` ID；typed config、attempt、stdout/stderr 和状态写入 meta-experiment 下的：

```text
srun_pool/<batch-hash>/manifest.json
```

相同配置中断后再次运行时，会读取同一 manifest：已经完成的 seed 跳过，仍活跃的 step 继续监控，失败或中断的 attempt 按 `launcher.max_retries` 处理。controller 必须保持运行；退出 controller 会终止它管理的 step，但不会取消整个手工 allocation。

`step_limit=5` 仍然只是 smoke 预算。需要更完整地经历 draft/debug/improve 时，可以额外覆盖：

```bash
solver.step_limit=20
```

正式复现实验必须使用论文或正式配置规定的预算，不能把修改过的 step/time limit 与原结果直接比较。

## 6. 原仓库中的 superimage/Jupyter 输入输出

### 6.1 输入挂载

`main_run.py` 构造 Jupyter interpreter 时传入：

```text
task.data_dir = $MLE_BENCH_DATA_DIR/spaceship-titanic/prepared/public
```

Jupyter server 把它作为容器输入目录绑定。agent 只看到：

```text
./data/description.md
./data/train.csv
./data/test.csv
./data/sample_submission.csv
```

agent 看不到：

```text
$MLE_BENCH_DATA_DIR/spaceship-titanic/prepared/private/test.csv
```

### 6.2 Agent 收到的任务说明

任务 prompt 由以下内容拼接：

```text
src/dojo/tasks/mlebench/instructions.txt
+
prepared/public/description.md
```

原始 benchmark 指令要求：

- 读取 `./data`。
- 自行训练和验证模型。
- 在当前目录生成 `submission.csv`。
- 不允许查看私有标签或抄袭其他解法。

### 6.3 候选程序输出契约

候选程序至少需要：

```python
train = pd.read_csv("./data/train.csv")
test = pd.read_csv("./data/test.csv")

# train model and predict test

submission = pd.DataFrame({
    "PassengerId": test["PassengerId"],
    "Transported": predictions,
})
submission.to_csv("submission.csv", index=False)
```

预期 CSV：

```csv
PassengerId,Transported
0013_01,False
0018_01,True
```

原仓库 prompt 要求候选打印验证指标，但**没有学生后来加入的强制 `FINAL_VALIDATION_SCORE:` marker**。原始 Greedy 主要依赖 analyze LLM 把 stdout 总结为结构化的：

```text
metric
summary
is_bug
```

## 7. 原仓库的搜索和评测语义

### 7.1 Greedy 搜索

原始 Greedy 大致执行：

```text
root
  -> draft 多个候选
  -> 执行候选
  -> analyze LLM 阅读 stdout
  -> submission 校验和私有评分
  -> 有错误则 debug
  -> 否则 improve 当前最佳节点
  -> 保存 journal/checkpoint
```

原始代码将节点判为 buggy 的条件包括：

```text
analyze LLM 返回 is_bug=true
或程序退出失败
或没有解析到 validation metric
或 submission 无效
```

### 7.2 Validation score 与 private score

默认 `solver.use_test_score=false`：

```text
node.metric.value          = analyze LLM 从候选 stdout 提取的 validation score
node.metric.info["score"] = MLE-bench 私有 accuracy
```

因此搜索按候选自己报告的验证分数推进；私有分数被记录，但默认不用于搜索选择。这是原仓库本身的语义，不是学生 HCE 改动。

不要开启：

```bash
solver.use_test_score=true
```

除非实验明确允许 oracle/test-score selection；否则会把私有评分直接反馈给搜索，改变标准评测协议。

### 7.3 Submission 评分

`MLEBenchTask.step_task()` 会：

1. 在 superimage Jupyter kernel 中执行候选代码。
2. 从容器工作目录 fetch `submission.csv`。
3. 调用 `mlebench.grade.validate_submission()` 校验列、ID 和预测。
4. 使用 `prepared/private/test.csv` 和 Spaceship accuracy grader 评分。
5. 用 `leaderboard.csv` 计算排名阈值信息。
6. 写入 `results/grading_report.json`。
7. 删除本轮 submission，避免下一候选误用旧文件。

## 8. 原仓库运行产物

默认运行目录：

```text
$LOGGING_DIR/aira-dojo/user_<user>_issue_<git_issue_id>/<run_id>/
```

核心产物：

```text
<run_dir>/
|-- dojo_config.json
|-- config_tree.log
|-- env_variables.json
|-- checkpoint/
|   |-- state.json
|   `-- journal.jsonl
|-- json/
|   |-- JOURNAL.jsonl
|   `-- STATE.jsonl
|-- results/
|   `-- grading_report.json
|-- <exp>_<timestamp>_Greedy_search_data.json
`-- <exp>_<timestamp>_Greedy_tree.html
```

注意：

- `submission.csv` 在每轮评分后被删除，运行结束后不存在是正常的。
- `results/grading_report.json` 会被后续有效候选覆盖，不一定对应最佳节点。
- 完整逐节点数据应从 `checkpoint/journal.jsonl` 或 `*_search_data.json` 读取。
- 运行时的 `metric.info["score"]` 序列化后是 journal 中的 `metric_info.score`。
- `env_variables.json` 可能包含 API key，不应公开上传。

快速检查：

```bash
python - <<'PY' /path/to/run/checkpoint/journal.jsonl
import json
import sys

nodes = [json.loads(line) for line in open(sys.argv[1])]
working = [n for n in nodes if not n.get("is_buggy", True)]
print("nodes", len(nodes))
print("working", len(working))
for node in working[-5:]:
    print(
        "step", node.get("step"),
        "validation", node.get("metric"),
        "private", (node.get("metric_info") or {}).get("score"),
    )
PY
```

## 9. 原仓库的高并发采数

原仓库多运行入口：

```bash
python -m dojo.main_runner_job_array
```

原始示例 `runner_example.yaml` 使用：

- `benchmark=mlebench/dev`
- `interpreter=jupyter`
- `solver=mlebench/greedy`
- GPT-4o operators
- seeds `[1,2,3]`

它不是 Spaceship 单任务 runner。若只想用 Spaceship 验证并发框架，可新增一个**仅选择任务、不改变算法**的 benchmark 配置：

```yaml
# src/dojo/configs/benchmark/mlebench/spaceship.yaml
_target_: dojo.config_dataclasses.benchmark.BenchmarkConfig

name: mlebench
tasks:
  - spaceship-titanic
```

再复制原始 runner 结构：

```yaml
# src/dojo/configs/_exp/mlebench/upstream_spaceship_runner.yaml
# @package _global_
defaults:
  - override /benchmark: mlebench/spaceship
  - override /interpreter: jupyter
  - override /solver: mlebench/greedy
  - override /solver/client@solver.operators.analyze.llm.client: litellm_4o
  - override /solver/client@solver.operators.debug.llm.client: litellm_4o
  - override /solver/client@solver.operators.draft.llm.client: litellm_4o
  - override /solver/client@solver.operators.improve.llm.client: litellm_4o

metadata:
  git_issue_id: upstream_spaceship_smoke

solver:
  step_limit: 5

vars:
  metadata.seed: [1, 2, 3]

launcher:
  debug: true
  array_parallelism: 3
```

这两个配置是为了选择 Spaceship 而增加的薄包装，不应加入 DeepSeek、Python interpreter、HCE 或学生 prompt 改动。

先 dry run：

```bash
python -m dojo.main_runner_job_array \
  +_exp=mlebench/upstream_spaceship_runner \
  logger.use_wandb=False \
  launcher.debug=True
```

再正式提交：

```bash
python -m dojo.main_runner_job_array \
  +_exp=mlebench/upstream_spaceship_runner \
  logger.use_wandb=False \
  launcher.debug=False \
  launcher.array_parallelism=3
```

正式复现原仓库 Lite 数据采集时，应直接使用原始 experiment，例如：

```bash
python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_greedy_o3 \
  logger.use_wandb=False \
  launcher.debug=True
```

确认 dry run 后再设 `launcher.debug=False`。`aira_greedy_o3.yaml` 的原始语义是：

- MLE-bench Lite benchmark。
- Jupyter/superimage。
- AIRA Greedy。
- o3 负责 draft/debug/improve。
- GPT-4o 负责 analyze。
- 每个任务 10 个 seed。

这才是原仓库面向正式 benchmark 的代表性采数配置；Spaceship 只是用来先验证整个系统。

### 9.1 原仓库 Lite 的 22/20 任务差异

原仓库存在一个需要显式处理的配置差异：

```text
src/dojo/configs/benchmark/mlebench/lite.yaml  22 个任务
src/dojo/tasks/mlebench/splits/low.txt          20 个任务
```

`low.txt` 少了：

```text
detecting-insults-in-social-commentary
the-icml-2013-whale-challenge-right-whale-redux
```

因此，仅执行：

```bash
python src/dojo/tasks/mlebench/utils/prepare.py \
  -s low \
  --data-dir="$MLE_BENCH_DATA_DIR"
```

不足以准备 `aira_greedy_o3` 的全部 22 个 benchmark tasks。还需要单独准备：

```bash
python src/dojo/tasks/mlebench/utils/prepare.py \
  -c detecting-insults-in-social-commentary \
  --data-dir="$MLE_BENCH_DATA_DIR"

python src/dojo/tasks/mlebench/utils/prepare.py \
  -c the-icml-2013-whale-challenge-right-whale-redux \
  --data-dir="$MLE_BENCH_DATA_DIR"
```

正式提交 runner 前，应以 `benchmark/mlebench/lite.yaml` 为准逐项检查数据是否 prepared，而不是只相信 split 名称。

---

# 第二部分：学生研究分支（不在当前 checkout）

## 10. 学生流程增加和改变了什么

以下内容用于解释 `phase1-value-critic` 等历史研究分支与原协议的差异。所列 DeepSeek/HCE 配置和实现**不在当前 `dojo-reproduce` checkout 中**，也不应为了正式复现而迁回本分支。

### 10.1 新增 DeepSeek client

新增：

```text
src/dojo/configs/solver/client/litellm_deepseek_pro.yaml
src/dojo/configs/solver/client/litellm_deepseek_flash.yaml
```

模型配置：

```text
deepseek-v4-pro
deepseek-v4-flash
https://api.deepseek.com
```

使用：

```dotenv
PRIMARY_KEY_DEEPSEEK_V4_PRO=...
PRIMARY_KEY_DEEPSEEK_V4_FLASH=...
```

或者通用 `PRIMARY_KEY`。

### 10.2 新增 DeepSeek experiment

Spaceship 相关新增配置：

```text
src/dojo/configs/_exp/mlebench/deepseek_smoke.yaml
src/dojo/configs/_exp/mlebench/deepseek_greedy_spaceship.yaml
src/dojo/configs/_exp/mlebench/deepseek_mcts.yaml
src/dojo/configs/_exp/mlebench/deepseek_greedy_hce_spaceship.yaml
```

这些文件不属于原 AIRA-Dojo 默认流程。

### 10.3 Smoke 改用 Python interpreter

`deepseek_smoke.yaml` 明确选择：

```yaml
interpreter: python
solver: mlebench/greedy
task: mlebench/spaceship-titanic
clients: deepseek-v4-pro
step_limit: 5
```

Python interpreter 本身原仓库已有，但原始 `run_example` 和正式 MLE-bench experiments 使用的是 Jupyter。学生 smoke 当时改用宿主 Python，是为了绕过 Singularity runtime backend 落地前的 Apptainer/user namespace 限制；当前默认 Jupyter 配置已经可以直接使用 Singularity。

因此它与原流程的主要环境差异是：

| 项目 | 原仓库默认 | 学生 smoke |
|---|---|---|
| 执行环境 | superimage 内 Jupyter kernel | 宿主 Python multiprocessing 子进程 |
| 数据提供 | container bind | `workspace_agent/data` 符号链接 |
| 可用依赖 | superimage 固定依赖 | 当前 Conda/宿主环境依赖 |
| LLM | GPT-4o/o3 | DeepSeek Pro/Flash |
| 隔离性 | 较强 | 较弱 |

### 10.4 Python interpreter guard 修复

学生在 `src/dojo/core/interpreters/python.py` 增加：

```python
global_scope["__name__"] = "__main__"
```

这样候选代码中的：

```python
if __name__ == "__main__":
    main()
```

会在 Python interpreter 中正常执行。原代码没有显式设置该值。

该改动不影响 Jupyter 原流程，因为 Jupyter 走另一套 interpreter 实现。

### 10.5 修改 AIRA operator prompts

学生在 draft/debug/improve prompts 中加入：

- 强制处理 object/string/categorical dtype。
- 首个方案优先简单、鲁棒、避免过早 Optuna。
- 强制最后打印：

```text
FINAL_VALIDATION_SCORE: <number>
```

这些要求会直接改变 LLM 生成代码的分布，所以即使使用相同模型和 seed，也不能视为原仓库 prompt 的复现。

### 10.6 修改 Greedy/MCTS metric 解析

学生增加正则 fallback：当 analyze LLM 没能给出结构化 metric 时，从 stdout 提取：

```text
FINAL_VALIDATION_SCORE: 0.8123
```

学生还改变了 buggy 判定：

```text
原仓库：analyze is_bug 也参与判定
学生版：忽略 analyze is_bug，只看退出码、metric 和 submission validity
```

这会改变搜索树中哪些节点被 debug、哪些节点被保留，因此属于实质性算法行为变化。

### 10.7 新增 HCE 协议

学生新增：

```text
src/dojo/tasks/mlebench/hce_eval.py
```

并修改：

```text
src/dojo/tasks/mlebench/task.py
src/dojo/config_dataclasses/task/mlebench.py
src/dojo/configs/task/mlebench/_default.yaml
```

HCE 把私有答案固定切为：

```text
D_search / D_val / D_test
```

支持：

```text
task.arm=full
task.arm=naive
task.arm=consistency
```

搜索 fitness 可以来自外部 `D_search`，而不是候选自报 validation。它是学生研究噪声鲁棒评估的实验协议，不属于原 MLE-bench/AIRA 默认评测。

## 11. 学生普通 DeepSeek smoke 怎么走

命令：

```bash
python -m dojo.main_run \
  +_exp=mlebench/deepseek_smoke \
  logger.use_wandb=False \
  metadata.seed=1
```

链路：

```text
同一份 prepared/public 和 prepared/private
        |
        v
deepseek_smoke.yaml
        |
        +-- Python interpreter
        +-- Greedy
        +-- DeepSeek Pro operators
        `-- step_limit=5
        |
        v
workspace_agent/data -> prepared/public
        |
        v
DeepSeek 生成带 FINAL_VALIDATION_SCORE marker 的代码
        |
        v
宿主 Python 子进程执行
        |
        v
标准 MLEBenchTask submission 校验与 private score
        |
        v
学生版 Greedy metric fallback/buggy 判定
```

`deepseek_smoke` 的 `step_limit=5`，root 占 step 0，实际候选数量有限；同时默认 `num_drafts=5`，所以 smoke 通常还没进入完整 improve 阶段。

要观察 draft 后的 improve/debug：

```bash
python -m dojo.main_run \
  +_exp=mlebench/deepseek_smoke \
  logger.use_wandb=False \
  metadata.seed=1 \
  solver.step_limit=12
```

这条命令适合复现学生自己的采数协议，不适合替代第一部分的原仓库流程。

## 12. 学生 HCE 流程怎么走

命令示例：

```bash
python -m dojo.main_run \
  +_exp=mlebench/deepseek_greedy_hce_spaceship \
  logger.use_wandb=False \
  metadata.seed=1 \
  task.arm=full
```

HCE 与普通学生 smoke 的差异：

```text
普通 smoke：
  搜索 metric = 候选自报 validation
  private score = 只记录到 metric.info.score

HCE：
  搜索 metric = D_search 外部评分或其低成本 proxy
  D_val score = 保存为辅助/最终选择信息
  D_test = 不在搜索中评分
```

不同 arm：

| arm | 搜索信号 |
|---|---|
| `full` | 完整 D_search 真实评分 |
| `naive` | D_search 子采样 proxy |
| `consistency` | 多次 proxy 均值加方差惩罚 |

这套协议改变了 private labels 的使用方式，不能与原仓库默认分数直接比较。

## 13. 学生流程的输入输出和产物

数据准备结果与第一部分相同，但 Python interpreter 工作区表现不同：

```text
<run_dir>/workspace_agent/
`-- data -> $MLE_BENCH_DATA_DIR/spaceship-titanic/prepared/public
```

候选代码在宿主 Python 子进程中执行，输出仍必须是：

```text
./submission.csv
```

学生 prompt 额外要求：

```text
FINAL_VALIDATION_SCORE: <number>
```

普通学生流程序列化后的节点仍包含：

```text
metric              候选 validation 或 fallback marker
metric_info.score   MLE-bench private accuracy
is_buggy
code
term_out
parents / children
```

HCE 节点还会包含：

```text
metric_info.arm
metric_info.dsearch_fitness
metric_info.dsearch_info
metric_info.dval_score
metric_info.n_search
metric_info.n_val
```

## 14. 两套流程的直接对比

| 维度 | 原仓库流程 | 学生流程 |
|---|---|---|
| 代表配置 | `run_example`, `aira_greedy_o3` | `deepseek_smoke`, `deepseek_mcts`, `deepseek_greedy_hce_*` |
| 主要 LLM | GPT-4o/o3 | DeepSeek Pro/Flash |
| 默认执行环境 | Jupyter + superimage | Python interpreter |
| 数据接口 | 容器只读 bind `./data` | 宿主 workspace symlink `./data` |
| 原始 prompt | AIRA/AIDE 默认 prompt | 加 dtype、简单 baseline、marker 要求 |
| Metric 解析 | analyze LLM 结构化输出 | analyze + marker 正则 fallback |
| Buggy 判定 | 包含 analyze `is_bug` | 忽略 analyze `is_bug` |
| 默认搜索信号 | self-reported validation | 普通版相同；HCE 改为 D_search 外部信号 |
| 私有分数 | 记录到 aux info | 普通版相同；HCE 进一步切分私有答案 |
| 是否适合原结果复现 | 是 | 否，属于研究 fork |


## 15. 当前代码中的共同注意事项

### 15.1 最终 EVAL logging 问题

当前 `src/dojo/main_run.py` 调用：

```python
logger.log(fitness, LogEvent.EVAL)
```

但 logger 接口期望字典，正确形式应是：

```python
logger.log({"fitness": fitness}, LogEvent.EVAL)
```

这个问题存在于原始 `main_run.py`，不是学生 DeepSeek/HCE 特有改动。它可能导致搜索结果已经导出后，进程在最终 logging 阶段报错。

在修复前判断运行是否有效，应优先检查：

```text
checkpoint/journal.jsonl
*_search_data.json
*_tree.html
```

以及其中是否存在非 buggy 节点和 `metric_info.score`。不要只根据最终退出码判断整次搜索没有产物。

### 15.2 `grading_report.json` 会被覆盖

每个有效候选写同一个：

```text
results/grading_report.json
```

最后留下的不一定是最佳节点。逐节点分析以 journal/search data 为准。

### 15.3 `submission.csv` 会被删除

每轮评分后 Dojo 都会删除 submission，避免后续节点复用旧提交。运行结束后 workspace 中没有 submission 是预期行为。
