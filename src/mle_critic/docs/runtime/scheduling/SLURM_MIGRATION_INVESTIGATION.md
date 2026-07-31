# AIRA Dojo Slurm 调查与 srun Pool 迁移方案

日期：2026-07-20

## 结论

本集群的 Slurm、GPU GRES、cgroup 隔离和 Singularity 已经打通。大规模采集不再采用“每个 MLE task 提交一个 `sbatch`/数组元素”的方式，而采用下面的结构：

```text
手动申请一个多 GPU allocation
  -> main_runner_job_array 展开 benchmark、seed 和 sweep
  -> SrunPoolLauncher 在 allocation 内维持固定并发
  -> 每个 RunConfig 启动一个独立 srun step
  -> step 内运行 main_run
  -> main_run 为每次候选代码执行启动 Singularity/Jupyter
```

选择这套方案的原因是：

- 普通 `gpu` QoS 的 `MaxJobsPerUser=4`、`MaxSubmitJobsPerUser=4`，大数组和大量独立作业都会被拒绝。
- 一个 allocation 内可以有多个并发 job step。Slurm 只计算一个顶层 job，但仍对每个 step 分配和隔离 GPU、CPU。
- `gpu7` 有 8 张 Titan X 和 16 个逻辑 CPU，适合按 `8 x (1 GPU + 2 CPU)` 运行能放进 12 GB 显存的 lite 任务。
- 当前 SIF 已在 `gpu7` 验证：容器内 `torch 2.5.1+cu124` 支持 Titan X 的 `sm_50`，CUDA tensor 运算正常。

实现前还需要处理三类问题：

1. 删除宿主 runner 对 PyTorch 和 TensorFlow 的检查及元数据硬依赖。训练框架只在容器内检查。
2. 新增 `SrunPoolLauncher`、worker entrypoint 和持久化 manifest。
3. 让结果分析读取 manifest，并为 Slurm 19.05 使用 `sacct -P`，不再假定旧数组任务布局和 `sacct --json`。

## 当前代码如何运行任务

主入口是 `src/dojo/main_runner_job_array.py`：

1. Hydra 生成一个或多个 `RunnerConfig`。
2. benchmark、seed 和 sweep 被展开成多个 `RunConfig`，每个配置对应一个 MLE task 求解过程。
3. runner 使用 `RsyncSnapshot` 把代码复制到共享日志目录。
4. 当前实现把每个 `RunConfig` 作为一个 Slurm 数组元素提交。
5. 计算节点调用 `dojo.main_run._main(run_cfg)`。
6. `main_run` 构建 task、solver 和 interpreter。Greedy、MCTS 或 EVO 在求解过程中反复调用 interpreter；Singularity Jupyter interpreter 为候选代码运行提供隔离的训练环境。

因此有两层执行环境：

| 层次 | 负责内容 | 是否需要训练框架 |
|---|---|---|
| 宿主 runner/worker | 配置、LLM 搜索、日志、启动容器 | 不应为诊断而导入 PyTorch/TensorFlow |
| Singularity 容器 | 候选 MLE 代码、训练、推理和评分 | 需要 PyTorch/TensorFlow 等完整环境 |

### 删除宿主训练框架依赖

当前宿主仍有两处不必要的 PyTorch 依赖：

- `src/dojo/config_dataclasses/omegaconf/resolvers.py` 顶层 `import torch`，只为生成 `metadata.torch_version`。
- `src/dojo/main_run.py` 调用 `check_pytorch_gpu()`，通过宿主 Python 打印 GPU 类型。

`main_run.py` 还调用 `check_tensorflow_gpu()`，同样是在宿主 Python 中导入 TensorFlow。这些检查不能代表实际训练环境：宿主和 SIF 是两套独立 Python 环境，真正相关的是容器内版本和 CUDA 状态。

迁移时应：

1. 删除 `get_torch_version` resolver 和 `MetadataConfig.torch_version`，或把字段改成不触发 import 的普通可选字符串。
2. 删除 `main_run._main()` 中的 `PYTORCH_GPU`、`TENSORFLOW_GPU` 宿主检查。
3. 删除不再使用的 `check_pytorch_gpu()`、`check_tensorflow_gpu()`。
4. 如需记录训练环境，在 Singularity/Jupyter 启动后的容器内收集框架版本、CUDA 版本和 GPU 名称，并写入实验目录。

宿主仍可用 `nvidia-smi` 做 Slurm 分配诊断，但它不应成为运行任务的必要步骤。

这里删除的是 AIRA runner 的训练框架诊断依赖，不是承诺整个宿主环境永远不安装 TensorFlow。vendored MLE-bench 的数据准备代码对少数 TFRecord 任务仍会按需导入 TensorFlow；该依赖属于离线数据准备，不应在每个 runner/worker 启动时加载。MLE-bench 宿主代码没有对应的 PyTorch 运行依赖。

## 本集群约束

以下结论来自 2026-07-19 至 2026-07-20 的本地探测和短作业测试。

### Slurm 和 QoS

- Slurm 版本：19.05.4。
- 集群名：`gpu`。
- 当前用户的普通 account/QoS：`gpu`/`gpu`。
- 通用分区包括 `gpu_2h`、`gpu_8h`、`gpu_24h` 和 `gpu_72h`。
- 默认分区 `gpu_2h` 最长 2 小时；36 小时任务需要 `gpu_72h`。
- `AccountingStorageEnforce=associations,limits,qos,safe`。
- `MaxJobsPerUser=4`、`MaxSubmitJobsPerUser=4`。
- `MaxTRESPerUser=gres/gpu=8`。
- `MaxArraySize=1001`，但 QoS 的 4 作业限制会更早生效。
- GPU 使用 GRES 和 device cgroup 隔离，`ConstrainDevices=yes`。

数组的 `%N` 只限制同时运行数，不减少 QoS 计算的待运行加运行元素总数。因此不能用低 `array_parallelism` 绕过 4 作业限制。

同一个 Unix 用户切换 Slurm account 也不一定产生独立配额，因为这里看到的是 QoS 的 per-user 限制。多账号操作由用户手工管理，launcher 不实现账号切换。

### CPU/GPU 比例规则

本集群加载了自定义 `job_submit/lua` 插件。实测规则为：

- `CPU:GPU > 10:1`：普通 GPU 作业被拒绝。
- `6:1 < CPU:GPU <= 10:1`：必须指定 `--constraint=highcpucount`。
- `CPU:GPU <= 6:1`：可以作为普通 GPU 作业提交。

对 srun pool 来说，总 allocation 和每个 step 都应使用一致、实际可用的 CPU/GPU 比例。

### 内存登记不可靠

部分实际有数百 GB 内存的节点在 Slurm 中登记为 `RealMemory=1` MB，`gpu7` 也属于这种节点。

不能用 `--mem=1M` 迁就这个登记值。本集群启用了 `ConstrainRAMSpace=yes`，实测带 `--mem=1M` 的两个并发 PyTorch 容器在启动阶段超时；完全不发送 `--mem` 后，同样的两个容器约 10 秒完成。

在管理员修复 `RealMemory` 前：

- `salloc` 不发送 `--mem`、`--mem-per-cpu` 或 `--mem-per-gpu`。
- `SrunPoolLauncher` 也不向 step 传内存参数。
- 应用层可记录 RSS，但不能依赖 Slurm 在所有节点上提供一致的内存调度语义。

### 共享文件系统

以下路径必须对 allocation 节点可见：

- 宿主 conda 环境；
- runner 创建的代码 snapshot；
- `LOGGING_DIR`、manifest 和 step 日志；
- MLE-bench 数据；
- SIF、overlay 和 bind 源路径。

这些内容应放在 `/research` 等共享文件系统，不能放在登录节点本地 `/tmp`。

## 已验证的运行路径

### Slurm 和 Singularity

- 原生单 GPU Slurm 作业能正确设置 GRES 和 device cgroup。
- Singularity 3.5.2 能在 Slurm 作业内使用 `--nv`。
- 容器只能访问分配给当前作业或 step 的 GPU。

### 同一 allocation 内并发 srun

allocation 7662 在 `gpu7` 上申请 2 GPU 和 2 CPU，并发启动 step `7662.0`、`7662.1`：

- 两个 step 均成功完成。
- 两个 step 分配到不同的 Titan X UUID。
- 每个 step 内 `CUDA_VISIBLE_DEVICES` 都被重映射为 `0`，这是正常行为；容器和代码只看到自己的第一张 GPU。

allocation 7668 又验证了完整的关键路径：

```text
salloc
  -> 两个并发 srun step
  -> 每个 step 启动一份相同的 Singularity SIF
  -> 每个容器执行 PyTorch CUDA tensor
```

两个 step 均成功，证明 `SrunPoolLauncher -> main_run -> Singularity` 的资源模型可行。

### gpu7 镜像兼容性

`gpu7` 的关键参数：

- 8 张 NVIDIA GeForce GTX TITAN X；
- 每张 12 GB 显存；
- 16 个逻辑 CPU；
- 节点驱动 560.35.05；
- 可进入 `gpu_72h`。

当前 SIF 内：

- PyTorch：`2.5.1+cu124`；
- CUDA build：12.4；
- `torch.cuda.get_arch_list()` 包含 `sm_50`；
- `torch.cuda.is_available()` 为 True；
- 小型 CUDA tensor 运算成功。

满卡 profile 应是 8 个并发 step，每个 step 1 GPU、2 CPU。是否能运行具体 lite task 仍取决于其峰值显存是否低于 12 GB。

8 GPU 短探针 7665 在用户已有 3 张 GPU allocation 时触发 `QOSMaxGRESPerUser`，因此没有完成满卡测试。该请求已经通过语法、节点和 CPU/GPU 规则检查；在其他 allocation 释放后仍需补做一次 8 step smoke test。

## 目标实现

### 代码结构

入口继续使用 `src/dojo/main_runner_job_array.py`。该文件负责配置展开和 snapshot，是选择 launcher 的合适位置；具体进程池逻辑放到独立模块，避免继续扩大入口文件。

建议新增：

```text
src/dojo/config_dataclasses/launcher/srun_pool.py
src/dojo/configs/launcher/srun_pool.yaml
src/dojo/core/runners/slurm/srun_pool.py
src/dojo/main_srun_worker.py
```

职责划分：

| 组件 | 职责 |
|---|---|
| `main_runner_job_array.py` | 展开 RunnerConfig、生成 RunConfig、创建 snapshot、选择 launcher |
| `SrunPoolConfig` | 描述每个 step 的资源和 pool 行为 |
| `SrunPoolLauncher` | 验证 allocation、派发/监控 srun、补位、更新 manifest |
| `main_srun_worker.py` | 读取一个序列化 RunConfig，调用 `main_run._main()` |
| manifest | 保存任务、step、日志、状态和恢复信息 |

现有 batch launcher 可以保留，用于小规模回归或其他集群；本集群的大规模采集走 `srun_pool`。

### SrunPoolConfig

建议配置：

```yaml
_target_: dojo.config_dataclasses.launcher.srun_pool.SrunPoolConfig

debug: true
monitor_jobs: true
max_parallel: 8
cpus_per_step: 2
gpus_per_step: 1
ntasks_per_step: 1
poll_interval_seconds: 5
max_retries: 1
fail_fast: false
allocation_job_id: null
```

约束：

- `allocation_job_id=null` 时从 `SLURM_JOB_ID` 自动发现。
- 节点、partition、QoS、account、总 GPU、总 CPU 和 time limit 都由外层 allocation 决定，不在 pool 配置中重复声明。
- `max_parallel * gpus_per_step` 不得超过 allocation GPU 数。
- `max_parallel * cpus_per_step` 不得超过 allocation 可供 job step 使用的 CPU 数。
- 第一版只支持单节点 allocation。多节点的 step 放置和本地数据缓存以后再设计。
- 不提供内存字段。

### main_runner_job_array 改动

建议把当前 `launch_jobs()` 拆成三部分：

1. `create_snapshot()`：只负责共享代码 snapshot 和 `PYTHONPATH`。
2. `launch_batch_jobs()`：保留现有 batch 路径。
3. `launch_srun_pool()`：把 `run_configs` 和 `snapshot_path` 交给 `SrunPoolLauncher`。

分派逻辑只根据 launcher dataclass 类型判断：

```python
if isinstance(launcher_cfg, SlurmConfig):
    return launch_batch_jobs(...)
if isinstance(launcher_cfg, SrunPoolConfig):
    return launch_srun_pool(...)
raise ValueError(...)
```

不要在 `SlurmConfig` 中添加 `use_salloc`、`allocated_node` 等开关。两种 launcher 的资源语义不同，分开的 dataclass 更容易验证。

当前 `main()` 在提交后统一调用 `monitor_jobs(jobs)`，这个收尾逻辑也要按 launcher 拆开：batch launcher 可以继续返回原 Job 列表；srun pool 自己同步监控全部 step，结束后返回一份 pool summary，不能再传给旧的 `monitor_jobs()`。

### worker 和 RunConfig 传递

每个 RunConfig 在 controller 启动 step 前写成独立 JSON：

```text
<meta-run>/srun_pool/configs/<run-id>.json
```

worker 只做四件事：

1. 从 JSON 恢复 `RunConfig`。
2. 从 `SLURM_JOB_ID`、`SLURM_STEP_ID` 取得 allocation/step 标识。
3. 原子写入当前 attempt 的 identity 文件，供 controller 获得 Slurm 分配的 step ID；manifest 保持只有 controller 一个写入者。
4. 调用 `main_run._main(run_cfg)`，并用进程退出码报告成功或失败。

不建议直接把 Python callable pickle 给 step。JSON 更容易检查、恢复和跨版本分析。

### srun 命令

单节点、单 GPU step 的命令形状为：

```bash
srun \
  --jobid="$SLURM_JOB_ID" \
  --exclusive \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=2 \
  --gres=gpu:1 \
  --chdir=<snapshot> \
  --output=<step-log>.out \
  --error=<step-log>.err \
  <host-python> -m dojo.main_srun_worker <run-config.json>
```

本集群 Slurm 19.05 支持 `--exclusive`，不依赖较新版本的 `--exact`。

所有命令使用参数列表传给 `subprocess.Popen`，不使用 `shell=True`。controller 最多维护 `max_parallel` 个进程；任一 step 退出后立即从 pending 队列补一个任务。

### allocation 发现和校验

controller 启动时至少检查：

- 存在 `SLURM_JOB_ID`；
- allocation 是 RUNNING；
- `SLURM_JOB_NODELIST` 只包含一个节点；
- 可用 GPU、CPU 足以满足 pool 配置；
- snapshot、Python、SIF、数据和日志路径在计算节点可见；
- 当前工作目录不依赖登录节点本地文件。

`allocation_job_id` 仅用于显式附着或测试，正常使用时无需用户填写 job ID 或 node。资源应由手工 `salloc` 决定。

### manifest、ID 和恢复

同一 allocation 内所有 step 的 `SLURM_JOB_ID` 相同，必须连同 `SLURM_STEP_ID` 才能唯一标识一次运行。

建议 manifest 为一个原子更新的 JSON 文件：

```json
{
  "allocation_id": "7668",
  "node_list": "gpu7",
  "tasks": {
    "<run-id>": {
      "config_path": "...json",
      "status": "running",
      "attempt": 1,
      "step_id": "7668.0",
      "stdout": "...out",
      "stderr": "...err",
      "exit_code": null
    }
  }
}
```

状态至少包括 `pending`、`launching`、`running`、`completed`、`failed`、`cancelled`。写 manifest 时先写临时文件，再用 rename 原子替换。

controller 启动 `srun` 时还不知道 Slurm 将分配哪个 step ID，因此先写 `launching`。worker 启动后立即写一个按 run ID 和 attempt 区分的 identity 文件；controller 读取它后把状态改成 `running` 并记录完整 step ID。stdout/stderr 文件名也应包含 run ID 和 attempt，避免重试覆盖前一次证据。

`metadata.slurm_id` 在 srun 模式记录完整 step ID，例如 `7668.0`。建议同时新增：

- `slurm_allocation_id`：`7668`；
- `slurm_step_id`：`0`；
- `launcher_type`：`srun_pool`。

controller 重启时读取 manifest：

- `completed` 不重复运行；
- `pending` 重新进入队列；
- `running/launching` 通过 `sacct` 或 `scontrol` 核对后恢复或标记失败；
- `failed` 只在未超过 `max_retries` 时重试。

### 信号和 allocation 超时

controller 收到 SIGINT/SIGTERM 时：

1. 停止派发新任务。
2. 更新 manifest。
3. 向仍在运行的 step 发送终止信号并等待有限时间。
4. controller 退出，但不主动取消用户手工申请的整个 allocation。

还应读取 allocation 的结束时间，在剩余时间不足以开始新 MLE task 时停止补位。第一版可以配置保守的 `min_remaining_seconds_to_launch`，避免新任务刚启动就随 allocation 超时被杀。

## 结果分析迁移

### 统一使用 manifest

srun pool 不生成旧 batch launcher 的 pickle 和 Job 对象。新的日志和任务映射以 manifest 为准，不伪造旧目录来兼容分析代码。

dashboard 和分析工具应先支持统一的 manifest 数据源；旧 batch 实验仍可走原读取路径。

### Slurm 19.05 accounting

本集群不支持：

```text
sacct --json
squeue --json
scontrol --json
```

使用固定字段的 parsable 输出：

```bash
sacct -P -n -j <allocation-or-step-ids> \
  --format=JobIDRaw,JobName,State,ExitCode,Submit,Start,End,ElapsedRaw,NodeList
```

这里的 `-o/--format` 选择 accounting 字段；`srun --output` 只指定 stdout 文件，不能替代 accounting 查询。

解析层应归一化成简单内部记录，不向 DataFrame 暴露不同 Slurm 版本的原始 JSON/文本结构。查询 allocation 时会同时看到：

- 顶层 allocation，例如 `7668`；
- `.extern`；
- 实验 step，例如 `7668.0`、`7668.1`。

分析时以 manifest 中记录的完整 step ID 过滤，只关联实验 step。

状态至少处理：

- `COMPLETED`；
- `FAILED`；
- `CANCELLED`；
- `TIMEOUT`；
- `OUT_OF_MEMORY`；
- `NODE_FAIL`；
- `PREEMPTED`；
- `BOOT_FAIL`；
- `DEADLINE`；
- `REVOKED`。

## 使用方式

第一版由用户手动申请 allocation。不要让 Python 自动启动交互式 `salloc`，这样 allocation 生命周期、断线处理和多账号操作保持清楚。

`gpu7` 示例：

```bash
salloc \
  --account=gpu \
  --qos=gpu \
  --partition=gpu_72h \
  --nodelist=gpu7 \
  --nodes=1 \
  --ntasks=8 \
  --cpus-per-task=2 \
  --gpus-per-node=8 \
  --time=72:00:00
```

不要添加 `--mem`。进入 allocation shell 后运行：

```bash
python -m dojo.main_runner_job_array \
  +_exp=<config> \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=8 \
  launcher.cpus_per_step=2 \
  launcher.gpus_per_step=1
```

如果需要无人值守，后续可以提供一个单独的 `sbatch` controller 脚本；它申请整个多 GPU allocation 后运行相同的 pool controller。不要把 allocation 申请逻辑耦合进 `SrunPoolLauncher`。

## 实现顺序

1. 删除宿主 PyTorch/TensorFlow import、resolver、metadata 和诊断调用。
2. 新增 `SrunPoolConfig` 及 Hydra launcher 配置。
3. 抽取 `main_runner_job_array.py` 的 snapshot 公共逻辑。
4. 新增 JSON worker entrypoint。
5. 实现 allocation 校验、固定并发 srun pool 和独立日志。
6. 实现原子 manifest、重试、信号处理和恢复。
7. 修改 Slurm ID 记录，区分 allocation ID 和 step ID。
8. 让分析代码读取 manifest，并增加 `sacct -P` parser。
9. 在 2 GPU allocation 上跑两个短真实 RunConfig。
10. 当前用户其他 GPU allocation 释放后，在 `gpu7` 完成 8 step smoke test。
11. 最后运行一个短 lite task，再逐步扩大采集规模。

## 验收条件

开始大规模采集前至少满足：

- AIRA runner/worker 不导入 PyTorch 或 TensorFlow，也能展开配置并启动任务。
- 两个并发真实 RunConfig 能在同一 allocation 内完成，且分别只看到自己的 GPU。
- 每个实验记录唯一的 `allocation.step` ID。
- controller 中断后能从 manifest 恢复，不重复运行已完成任务。
- step 失败、超时和 allocation 到期能正确落入 manifest。
- stdout/stderr、RunConfig、实验目录和 step ID 能稳定互相映射。
- `sacct -P` 能恢复 step 的状态、时间和退出码。
- `gpu7` 上 8 个并发 step 的 GPU UUID 不重复。
- 至少一个目标 lite task 在 Titan X 12 GB 显存内端到端完成。

---

## 实现记录：Slurm 迁移

本节记录调查完成后实际落地的主要改动。重点是资源模型、恢复语义和兼容性，不罗列格式调整等机械改动。

### 1. 新增 allocation 内的 `srun` pool

新增了独立的 `SrunPoolConfig`、Hydra launcher 配置、`SrunPoolLauncher` 和 `main_srun_worker.py`。原有 Submitit/Slurm batch launcher 继续保留，`main_runner_job_array` 根据 launcher dataclass 类型选择旧 batch 路径或新 pool 路径。

主要代码位置：

- `src/dojo/config_dataclasses/launcher/srun_pool.py::SrunPoolConfig`：step 资源、并发、重试、轮询和退出策略。
- `src/dojo/configs/launcher/srun_pool.yaml`：Hydra 默认值。
- `src/dojo/main_runner_job_array.py::launch_jobs`：旧 batch 与新 pool 的分派入口。
- `src/dojo/core/runners/slurm/srun_pool.py::SrunPoolLauncher`：allocation 校验、派发、监控和恢复。
- `src/dojo/main_srun_worker.py::main`：单个 step 的 worker 入口。

launcher 分派保持显式，不把两套资源语义塞进同一个 `SlurmConfig`：

```python
def launch_jobs(config_list, launcher_cfg):
    if isinstance(launcher_cfg, SrunPoolConfig):
        snapshot_path = SrunPoolLauncher.resume_snapshot_path(config_list, launcher_cfg)
        if snapshot_path is None:
            snapshot_path = create_snapshot()
        return launch_srun_pool(config_list, launcher_cfg, snapshot_path)
    if isinstance(launcher_cfg, SlurmConfig):
        return launch_batch_jobs(config_list, launcher_cfg, create_snapshot())
    raise ValueError(...)
```

新路径不负责申请资源。用户先手工执行 `salloc`，controller 从 `SLURM_JOB_ID` 发现 allocation，或通过 `launcher.allocation_job_id` 显式附着。启动前会用 `scontrol show job` 检查：

- allocation 仍为 `RUNNING` 且属于当前用户；
- 当前只使用单节点 allocation；
- `max_parallel * cpus_per_step` 和 `max_parallel * gpus_per_step` 不超过 allocation 资源。

每个 RunConfig 对应一个独立命令：

```text
srun --jobid=<allocation> --exclusive --nodes=1 --ntasks=1 \
  --cpus-per-task=<N> --gres=gpu:<N> ... dojo.main_srun_worker
```

controller 最多维持 `max_parallel` 个 step，任一步结束后立即从 pending 队列补位。step 不发送内存参数，以避开本集群错误的 `RealMemory` 登记。第一版明确不处理多节点放置。

allocation 发现和资源上限检查位于 `SrunPoolLauncher.allocation_job_id` 与 `_discover_allocation`：

```python
job_id = launcher_cfg.allocation_job_id or os.environ.get("SLURM_JOB_ID", "")
result = subprocess.run(["scontrol", "show", "job", job_id, "-o"], ...)
fields = _parse_key_values(result.stdout)

requested_cpus = self.cfg.max_parallel * self.cfg.cpus_per_step
requested_gpus = self.cfg.max_parallel * self.cfg.gpus_per_step
if requested_cpus > num_cpus or requested_gpus > num_gpus:
    raise ValueError(...)
```

实际 step 参数由 `_srun_prefix` 集中生成，刻意没有 `--mem`：

```python
return [
    "srun",
    f"--jobid={self.allocation.job_id}",
    "--exclusive",
    "--nodes=1",
    f"--ntasks={self.cfg.ntasks_per_step}",
    f"--cpus-per-task={self.cfg.cpus_per_step}",
    f"--gres=gpu:{self.cfg.gpus_per_step}",
]
```

### 2. 固定运行代码和 RunConfig 传递

`main_runner_job_array` 现在为一批任务创建一份共享 code snapshot。worker 的工作目录和 `PYTHONPATH` 只指向 snapshot，避免长时间采集期间修改 checkout 后，同一批任务加载到不同版本的代码。

代码位置是 `src/dojo/main_runner_job_array.py::create_snapshot` 和 `_snapshot_pythonpath`。关键配置为：

```python
with RsyncSnapshot(
    snapshot_dir=snapshot_path,
    root_dir=git_root,
    with_submodules=True,
    exclude=["*.ipynb", "*__pycache__", "*.mypy_cache"],
    include=glob.glob("./src/**", recursive=True),
):
    pass
```

原来的 snapshot 逻辑可能忽略未被 Git 跟踪的新模块，因此实现中显式包含整个 `src/`。这对刚新增但尚未提交的 launcher/worker 文件尤其重要。

RunConfig 不再依赖 Python callable pickle 传给 step，而是在 controller 侧写为 JSON。普通实验配置 JSON 仍保持原格式；供 worker 使用的 typed JSON 额外保存嵌套 dataclass 的具体类型，解决 `TaskConfig`、`SolverConfig`、`InterpreterConfig` 反序列化后丢失子类的问题，同时保留旧 JSON 缺少新字段时使用 dataclass 默认值的兼容性。

typed JSON 的入口在 `src/dojo/config_dataclasses/run.py::RunConfig.to_typed_dict`，递归实现位于 `src/dojo/config_dataclasses/utils.py::dataclass_to_dict` 和 `dataclass_from_dict`：

```python
DATACLASS_TYPE_KEY = "_dojo_dataclass_type"

def dataclass_to_dict(value):
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            DATACLASS_TYPE_KEY: f"{type(value).__module__}:{type(value).__qualname__}"
        }
        result.update(
            (field.name, dataclass_to_dict(getattr(value, field.name)))
            for field in fields(value)
        )
        return result
```

controller 在 `SrunPoolLauncher._load_or_create_manifest` 中为每个任务写配置：

```python
config_path = self.config_dir / f"{stem}.json"
_atomic_write_json(config_path, run_cfg.to_typed_dict())
```

worker 则在记录 step identity 后恢复同一个 RunConfig，并进入原有执行函数：

```python
run_cfg = RunConfig.load_from_json(args.config)
_main(run_cfg)
```

需要区分两个目录：snapshot 是固定的宿主源码副本；每个实验的 `workspace_agent/` 才是读写挂载到容器 `/workspace` 的 LLM 工作目录。MLE-bench public data 仍只读挂载到 `/workspace/data`。

### 3. manifest、step identity 和恢复

pool 使用 controller 单写者 manifest。worker 启动后只原子写 identity 文件，其中包含 run ID、attempt、allocation ID、step ID 和完整的 `<allocation>.<step>` ID；controller 再把它合并进 manifest。这样避免多个 worker 并发修改同一 JSON。

代码位置：

- `src/dojo/core/runners/slurm/srun_pool.py::_atomic_write_json`：manifest/config 原子写入。
- `src/dojo/main_srun_worker.py::_atomic_write_json`：worker identity 原子写入。
- `SrunPoolLauncher._load_or_create_manifest`：创建或续接 manifest。
- `SrunPoolLauncher._launch`：创建 attempt、日志路径并启动 `srun`。
- `SrunPoolLauncher._publish_identity`：把 worker identity 合入 manifest。
- `SrunPoolLauncher._recover`、`_poll_external`：恢复和监控旧 step。

原子替换的核心只有一个 writer-visible commit 点：

```python
temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
with temporary_path.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, sort_keys=True)
    file.flush()
    os.fsync(file.fileno())
os.replace(temporary_path, path)
```

worker 必须先发布 identity，再导入可能失败的运行模块：

```python
_atomic_write_json(
    args.identity,
    {
        "run_id": args.run_id,
        "attempt": args.attempt,
        "allocation_id": os.environ["SLURM_JOB_ID"],
        "step_id": os.environ["SLURM_STEP_ID"],
        "full_step_id": f"{allocation_id}.{step_id}",
    },
)

from dojo.main_run import _main
```

这样即使 `main_run` 或其依赖在 import 阶段失败，controller 仍能把错误日志关联到具体 step。

manifest 保存：

- 每个 RunConfig 的 typed config 路径和实验目录；
- `pending`、`launching`、`running`、`completed`、`failed`、`cancelled` 状态；
- 每次 attempt 的 step ID、stdout、stderr、退出码和 Slurm 状态；
- 使用过的 allocation 及节点历史；
- snapshot 和 controller Python 路径。

所有更新先写临时文件、`fsync`，再用 `os.replace` 原子替换。日志和 identity 文件名包含 run ID hash 与 attempt，重试不会覆盖前一次证据。

manifest 放在 meta-experiment 下的稳定路径：

```text
srun_pool/<sorted-run-id-hash>/manifest.json
```

路径不再绑定某个 allocation ID，所以相同任务集合可以在新的 allocation 中继续运行。恢复时：

- `completed` 不重跑；
- `pending` 重新排队；
- `running`、`launching`、`cancelled` 结合 identity、`sacct` 和 `scontrol show step` 判断实际状态；
- 已结束失败的 step 在 `max_retries` 范围内重试；
- 仍在运行的旧 step 作为 external running step 继续监控并占用 pool 并发槽。

稳定路径由排序后的 RunConfig ID 计算，而不是使用 allocation ID：

```python
batch_key = hashlib.sha256(
    "\n".join(sorted(cfg.id for cfg in run_configs)).encode()
).hexdigest()[:12]
self.pool_dir = self.meta_exp_dir / "srun_pool" / batch_key
```

恢复中的核心判定位于 `_recover`：

```python
if status == "completed":
    continue
elif state == "COMPLETED":
    self._finish_task(..., status="completed")
elif state in TERMINAL_STATES:
    self._finish_task(..., status="failed")
    if self._queue_retry(run_id):
        pending.append(run_id)
elif state in ACTIVE_STATES:
    external_running.add(run_id)
```

### 4. controller 退出和 allocation 时限

controller 捕获 SIGINT/SIGTERM 后停止派发，向它管理的 step 发送 TERM，等待有限时间后再强制结束，并把状态写入 manifest。它只取消 step，不取消用户手工申请的顶层 allocation。

allocation 的 `EndTime` 会转换为剩余秒数；低于 `min_remaining_seconds_to_launch` 时不再启动新任务。已经运行的 step 可以继续到 allocation 自身结束。

实现审查时额外修复了两个边界：

1. controller 异常或 `srun` 本地进程启动失败时，也会更新 manifest 并清理已经启动的 step，避免留下无人管理的任务。
2. 计算节点路径检查本身需要启动一个占资源的 `srun`。controller 恢复时如果旧 step 已占满 allocation，提前检查会一直排队并阻塞恢复；现在只在确实有空闲并发槽、即将启动第一个新任务时检查一次。

路径检查覆盖 snapshot、宿主 Python、日志/meta-experiment、MLE-bench 数据、SIF、overlay、bind 源以及容器 runtime 是否在计算节点可见。

相关实现集中在 `SrunPoolLauncher._remaining_seconds`、`_can_launch`、`_signal_handler`、`_cancel_running` 和 `run`。主循环的补位条件直接包含时间与并发限制：

```python
while (
    pending
    and not self._stop_requested
    and self._can_launch()
    and len(running) + len(external_running) < self.cfg.max_parallel
):
    if self.cfg.validate_paths_on_node and not self._paths_validated:
        self._validate_paths_on_node()
        self._paths_validated = True
    run_id = pending.popleft()
    running[run_id] = self._launch(run_id)
```

停止时只对完整 step ID 调用 `scancel`，不会对 allocation ID 调用取消：

```python
for step_id in step_ids:
    subprocess.run(["scancel", "--signal=TERM", step_id], check=False)
```

### 5. Slurm ID 和 19.05 accounting

原代码主要把顶层 job 或 array ID 当作实验 ID，在 pool 中不足以区分同一 allocation 内的多个 step。现在 metadata 记录：

- `slurm_id`：完整 job/step ID，例如 `7668.1`；
- `slurm_allocation_id`：例如 `7668`；
- `slurm_step_id`：例如 `1`；
- `launcher_type`：例如 `srun_pool`。

旧 Slurm array 的 `<array>_<task>` ID 行为继续保留。

ID 归一化位于 `src/dojo/utils/slurm.py::get_slurm_identity`，写入实验配置的位置是 `src/dojo/main_run.py::_main`：

```python
if job_id and step_id and step_id not in {"batch", "extern"}:
    return SlurmIdentity(
        full_id=f"{job_id}.{step_id}",
        allocation_id=job_id,
        step_id=step_id,
        launcher_type=launcher_type or "srun",
    )

slurm_identity = get_slurm_identity()
cfg.metadata.slurm_id = slurm_identity.full_id
cfg.metadata.slurm_allocation_id = slurm_identity.allocation_id
cfg.metadata.slurm_step_id = slurm_identity.step_id
cfg.metadata.launcher_type = slurm_identity.launcher_type
```

新增统一 accounting parser，使用 Slurm 19.05 支持的：

```text
sacct -P -n --format=JobIDRaw,JobName,State,ExitCode,Submit,Start,End,ElapsedRaw,NodeList
```

parser 会去掉 `COMPLETED+`、`CANCELLED by <uid>` 等状态注释，并统一 active/terminal 状态集合。分析 dataframe、错误汇总和 dashboard 遇到 srun pool 时优先读取 manifest，再用完整 step ID 补充 `sacct` 数据；旧 Submitit 实验仍走原来的读取路径。即使 accounting 已超过保留期，manifest 仍能提供任务、日志和最终状态映射。

Slurm 19.05 parser 位于 `src/dojo/core/runners/slurm/accounting.py`：

```python
def normalize_slurm_state(state: str) -> str:
    return state.strip().split(maxsplit=1)[0].rstrip("+")

result = subprocess.run(
    [
        "sacct", "-P", "-n", "-j", ",".join(ids),
        f"--format={','.join(SACCT_FIELDS)}",
    ],
    ...,
)
```

manifest reader 位于 `src/dojo/core/runners/slurm/manifest.py`；主要接入点是：

- `src/dojo/analysis_utils/meta_data_wrangling.py::prepare_meta_exp_slurm_dataframe`；
- `src/dojo/analysis_utils/meta_data_wrangling.py::prepare_srun_pool_dataframe`；
- `src/dojo/analysis_utils/meta_error_summary.py`；
- `src/dojo/ui/components/exp_analysis.py::analyze_meta_experiment`。

### 6. 移除宿主训练框架硬依赖

删除了 runner 对宿主 PyTorch/TensorFlow GPU 的启动诊断，以及仅为记录版本而存在的 Torch resolver。原因是候选训练发生在 Singularity 内，宿主框架状态既不代表容器环境，也不应成为调度 worker 的启动条件。

为了确保仅导入 runner/worker 不间接加载大型或可选依赖，task、solver、interpreter factory 改为实际构建对象时再惰性导入，W&B 也只在启用 logger 时导入。代码格式化路径中的 `black` 改为可选：缺失时跳过格式化而不是让 runner 导入失败。

这项改动只保证控制层的普通导入不加载 Torch、TensorFlow 或 W&B。真正运行 solver、容器或 vendored MLE-bench 数据准备时，仍会按功能需要加载对应依赖。

对应代码位置：

- `src/dojo/main_run.py::_main`：删除 `check_pytorch_gpu`、`check_tensorflow_gpu` 调用。
- `src/dojo/config_dataclasses/omegaconf/resolvers.py`：删除 Torch import 和版本 resolver。
- `src/dojo/utils/environment.py`：删除宿主框架 GPU 探测函数。
- `src/dojo/utils/config.py::LazyFactory`：统一惰性 factory。
- `src/dojo/config_dataclasses/{task,solver,interpreter}/__init__.py`：注册模块路径，而非顶层导入具体实现。
- `src/dojo/utils/logger.py::WandBLogger.__init__`：实际启用 W&B 时才 import。

惰性注册的形状如下：

```python
@dataclass(frozen=True)
class LazyFactory:
    module: str
    attribute: str

    def __call__(self, *args, **kwargs):
        factory = getattr(importlib.import_module(self.module), self.attribute)
        return factory(*args, **kwargs)

TASK_MAP = {
    "MLEBenchTaskConfig": LazyFactory("dojo.tasks.mlebench.task", "MLEBenchTask")
}
```

### 7. 验证结果和剩余验收

已完成的验证：

- Slurm 迁移和 Singularity 项目测试：`23 passed`；
- 固定并发、manifest、重试基础行为和跨 allocation 恢复模拟；
- typed RunConfig 往返、旧 JSON 默认值兼容和真实 AIRA Greedy Hydra 配置往返；
- runner、worker、`main_run` 导入时不加载 Torch、TensorFlow、W&B；
- snapshot 包含未跟踪的新源码文件；
- 真实 Slurm 19.05 accounting 能解析 `7668.0`、`7668.1` 为 `COMPLETED 0:0`；
- 全仓测试中项目测试通过，30 个失败均为 vendored MLE-bench 访问 Kaggle 时网络不可达，与本次迁移无关。

主要回归用例集中在 `tests/test_slurm_migration.py`，覆盖 typed JSON、Slurm ID、19.05 `sacct`、manifest reader、固定并发、跨 allocation 续跑、snapshot 和控制层无训练框架 import；已有容器行为测试在 `tests/test_singularity_jupyter_server.py`。

尚未完成的真实运行验收：

- 在新的 2 GPU allocation 中运行两个真实 AIRA RunConfig；
- 在 `gpu7` 做 8 个并发 step 的 GPU UUID 隔离测试；
- 至少一个目标 MLE-bench task 的完整 LLM -> Singularity -> 训练 -> submission -> private evaluation 链路。

因此当前实现已通过控制层和模拟调度测试，但在开始大规模采集前，仍应先完成短 Spaceship/轻量任务 smoke，再扩大到 8 GPU 和正式 Lite 数据采集。
