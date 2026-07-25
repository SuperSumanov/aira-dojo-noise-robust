# 无 Slurm 环境下的本地 GPU Pool 与 Singularity 运行设计

日期：2026-07-24

## 1. 目标与结论

当前仓库已经支持两条外层作业启动路径：Submitit/`sbatch` 和 allocation 内的
`SrunPoolLauncher`；每个作业内的候选代码则由 `SingularityJupyterServer` 使用前台
`singularity exec --nv` 执行。本机没有 Slurm，GPU 直接暴露给宿主进程，但有 Singularity，
因此需要新增第三种外层 launcher：`LocalGpuPoolLauncher`。

推荐的运行模型是：

```text
main_runner_job_array 展开 RunConfig 并创建代码 snapshot
  -> LocalGpuPoolLauncher 发现并锁定允许使用的物理 GPU
  -> 每个 RunConfig 启动一个本地 worker 子进程
  -> worker 环境设置 CUDA_VISIBLE_DEVICES=<分配的 GPU UUID>
  -> main_run 构造 SingularityJupyterServer
  -> singularity exec --nv 启动候选代码的 Jupyter/训练环境
  -> 容器内显式继承同一 CUDA_VISIBLE_DEVICES
```

这套方案可以为该 launcher 管理的任务提供固定并发、GPU slot 分配、日志、重试和恢复。本文按
部署约束假设：同一时刻只有一个 `LocalGpuPoolLauncher`，其配置覆盖的 GPU 在 launcher 生命周期
内不会被其他进程使用。因此不需要实现跨 launcher 抢占仲裁或文件锁。它仍不能提供 Slurm
GRES/device cgroup 的强隔离：`CUDA_VISIBLE_DEVICES` 是 CUDA 运行时的
协作式过滤，`singularity --nv` 仍可能把所有 NVIDIA device node 带入容器；其他用户、未遵守
独占约定的宿主进程或主动忽略该变量的程序仍可能访问同一张卡。

因此本设计适用于可信的单机 research workload 管理，不应被描述为安全边界或多租户调度器。

## 2. 当前代码边界与可复用部分

现有调用链应区分“launcher 的管理范围”和“worker 的执行单位”：

| 层次 | 当前组件/对象 | 语义 |
| --- | --- | --- |
| 一批展开后的运行 | `SlurmConfig` / `SrunPoolConfig` | 描述 launcher 资源和并发策略；`SrunPoolConfig` 对应一个 pool，作用类似一个 job array 的管理外壳 |
| 一次完整 MLE task | 一个 `RunConfig` / worker | pool 中的单个调度单位，占用一个 GPU slot 并调用一次 `main_run._main()` |
| MLE task 内的候选代码执行 | `SingularityJupyterServer` | 在同一个 worker/slot 内反复启动或重置候选代码环境 |

因此 `SrunPoolConfig` 或新的 `LocalGpuPoolConfig` 都不对应单个 MLE task。它们描述整批
`RunConfig` 的调度外壳；展开后的每个 `RunConfig` 才对应一次完整 MLE task。旧 Submitit 路径会
把这些 RunConfig 提交成 array elements，`srun_pool` 把它们派发成 allocation 内的 steps，新的
local pool 则把它们派发成本机 worker 子进程。

主要可复用能力：

- `main_runner_job_array.py` 已负责 Hydra sweep、benchmark 展开和共享 snapshot。
- `RunConfig.to_typed_dict()` / `load_from_json()` 已能跨进程保留具体 dataclass 类型。
- `SrunPoolLauncher` 已验证固定宽度队列、原子 manifest、attempt 日志、重试、信号和恢复的整体
  模型。
- `SingularityJupyterServer` 已使用参数数组、前台 `exec`、独立进程组、显式 bind 和容器内
  `env`，不依赖 Slurm。
- `main_run._main()` 在没有 Slurm 环境变量时已经能运行，`get_slurm_identity()` 会返回
  `launcher_type=local` 和空 Slurm ID。

不能直接复用 `SrunPoolLauncher` 本身，因为它把 allocation 发现、`srun` 命令、`sacct` 恢复、
step ID 和 `scancel` 写进了生命周期核心。建议共享小型、无调度器语义的工具，而不是用大量条件
分支把 local 模式塞进 `SrunPoolLauncher`。

## 3. 本机基线

2026-07-24 在当前机器探测到：

- 未安装 `srun`，不能使用现有 `srun_pool`；
- `/usr/bin/singularity` 为 Singularity CE 3.10.1；
- 2 张 RTX 3090（24,576 MiB）和 2 张 RTX 2080 Ti（11,264 MiB）；
- GPU compute mode 均为 `Default`。

GPU 是异构的，但在调度层可以把四个 slot 视为等价：任一 pending RunConfig 都可以分配到任一
空闲 GPU。实际分到的 GPU 型号、数量和显存必须在 worker 启动前形成准确的 hardware description，
再通过现有 `HARDWARE` prompt 变量告知 agent。这样模型能针对 3090 或 2080 Ti 生成不同代码，
异构性还可能带来有价值的采样 diversity，无需按型号显式分池。

实现前还应在目标 SIF 上重新验证 Singularity 3.10.1 的 `--nv`、PyTorch CUDA 和容器内 GPU
UUID。本仓库之前记录的 Singularity 3.5.2 结果不能完全替代当前版本的 smoke test。

## 4. 配置设计

建议新增：

```text
src/dojo/config_dataclasses/launcher/local_gpu_pool.py
src/dojo/configs/launcher/local_gpu_pool.yaml
src/dojo/core/runners/local/gpu_pool.py
src/dojo/main_local_worker.py
```

首版配置建议为：

```yaml
_target_: dojo.config_dataclasses.launcher.local_gpu_pool.LocalGpuPoolConfig

await_completion: true
monitor_jobs: true
debug: true

# null 表示从父进程 CUDA_VISIBLE_DEVICES 解析；父进程也未设置时才发现全部 GPU。
devices: null
gpus_per_task: 1
max_parallel: null  # 默认 floor(len(devices) / gpus_per_task)

poll_interval_seconds: 2
max_retries: 1
fail_fast: false
task_timeout_seconds: null
shutdown_grace_seconds: 30

```

配置约束：

1. `devices` 接受物理 index 或完整 GPU UUID，但探测后统一保存为 UUID。生产命令推荐显式给出
   UUID，避免重启或驱动变化后 index 与物理卡的对应关系改变。
2. 若 controller 已有 `CUDA_VISIBLE_DEVICES`，`devices=null` 只能使用该 mask 内的卡，不能绕过
   父进程限制重新发现所有 GPU。
3. `gpus_per_task >= 1`，`max_parallel * gpus_per_task <= len(devices)`；首版可重点测试
   `gpus_per_task=1`，但数据结构不要假定一次 attempt 只有一个 UUID。
4. `await_completion` 和 `monitor_jobs` 必须为 true。没有外部 scheduler 时，controller 是状态、
   清理和重试的唯一管理者，不提供 fire-and-forget 模式。
5. launcher 启动前可以用 `nvidia-smi` 记录已有 compute process 并在非空时给出醒目警告，但按
   本文假设不实现等待、抢占或跨 launcher 仲裁；GPU 独占由部署约束保证。
6. launcher 不承诺 CPU、RAM 或 GPU 显存配额。`max_parallel` 仍需根据宿主 CPU/RAM 和总体负载
   手工设置。

`devices` 只定义该 launcher 覆盖哪些 GPU，不按型号分组。例如四张卡都加入同一个 pool：

```bash
python -m dojo.main_runner_job_array \
  +_exp=<config> \
  launcher=local_gpu_pool \
  launcher.debug=false \
  launcher.max_parallel=4 \
  'launcher.devices=[0,1,2,3]'
```

首版不增加 `minimum_gpu_memory_mb`、GPU class 或按型号队列，也不根据瞬时 free memory 选择任务。
设备差异只影响该 attempt 的 prompt context 和记录，不影响 FIFO 调度资格。

## 5. GPU 发现、归一化与 slot 管理

### 5.1 发现

launcher 启动时用参数数组执行：

```text
nvidia-smi --query-gpu=index,uuid,name,memory.total,compute_mode \
  --format=csv,noheader,nounits
```

解析得到不可变的本次 inventory，并写入 manifest。校验项包括：

- 配置的 index/UUID 存在且不重复；
- GPU UUID 唯一；
- `max_parallel` 与 `gpus_per_task` 可满足；
- `singularity`、SIF、snapshot、数据、overlay 和 bind source 均存在；
- 可选执行一个不占用训练资源的容器 feature probe。

若系统启用 MIG，应把 MIG device UUID 当作独立资源，并禁止在同一个 pool 中混用父 GPU UUID 与
其 MIG 子设备。首版若没有测试 MIG，可以检测到后明确报错，而不是静默错误分配。

### 5.2 slot 状态与分配

这里的 slot 是 launcher 进程内的一条 GPU 资源记录，不是文件锁、Slurm step 或额外守护进程。
每个 slot 绑定一个规范化 GPU UUID，并只有两种资源状态：

```text
available
  -> 分配给一个 RunConfig attempt
running(run_id, attempt, worker_pid)
  -> attempt 结束或被清理
available
```

`LocalGpuPoolLauncher` 是唯一的状态所有者，维护 `available_devices` 和 `running_workers`；派发与
回收都在 controller 主循环中完成。由于已假设只有一个 launcher 且覆盖 GPU 独占，不需要
`flock`、lock file、跨进程抢占检测或多 controller 公平协议。

如果 `gpus_per_task > 1`，一次从 available 集合取出固定数量的 UUID，attempt 完成时整体归还。
首版不需要考虑多个 launcher 以不同顺序取锁导致的死锁。

### 5.3 公平性

pending RunConfig 使用 FIFO。每当有足够空闲 slot 时启动队首任务；没有完整的
`gpus_per_task` 组合时等待，不为后续任务越过队首。可用设备使用 round-robin deque：初始化时按
配置顺序排列，从队首分配，attempt 结束后归还队尾。这样当 `max_parallel < len(devices)` 时也会
覆盖不同型号，为不同 RunConfig 提供自然的硬件条件 diversity。manifest 记录实际 UUID、启动时
物理 index、型号和显存。

## 6. worker 启动与 GPU mask 传递

每次 attempt 的命令形状为：

```text
<snapshot-host-python> -m dojo.main_local_worker \
  <typed-run-config.json> <identity.json> <result.json> \
  --run-id <id> --attempt <n>
```

controller 使用 `subprocess.Popen` 参数数组、独立 stdout/stderr 文件和新的进程组，不使用
`shell=True`。worker 环境至少设置：

```text
CUDA_DEVICE_ORDER=PCI_BUS_ID
CUDA_VISIBLE_DEVICES=GPU-uuid-a[,GPU-uuid-b]
DOJO_LAUNCHER_TYPE=local_gpu_pool
DOJO_GPU_UUIDS=GPU-uuid-a[,GPU-uuid-b]
DOJO_HARDWARE_DESCRIPTION=1 x NVIDIA GeForce RTX 3090 (24 GiB VRAM)
DOJO_ATTEMPT=<n>
PYTHONPATH=<snapshot paths>
PYTHONUNBUFFERED=1
```

使用 UUID 而不是物理 index 有两个好处：不会因父级 mask 的逻辑重编号选错卡，并且日志能与
`nvidia-smi` 稳定关联。进入 worker 后，CUDA 通常把获分配设备重新编号为 `cuda:0..N-1`，这是
预期行为。

### 6.1 把实际 slot 硬件写入 prompt

当前 `main_run._main()` 会执行：

```python
os.environ["HARDWARE"] = get_hardware()
```

`get_hardware()` 使用整机级 `nvidia-smi --query-gpu=name` 并对名称去重。在当前机器上，一个只分到
2080 Ti 的 worker 仍可能得到 `NVIDIA GeForce RTX 2080 Ti, NVIDIA GeForce RTX 3090`；这既没有
数量，也不能代表该 attempt 的实际 slot。`nvidia-smi` 本身也不适合作为
`CUDA_VISIBLE_DEVICES` 是否生效的判断依据。

launcher 已经在 inventory 阶段掌握 index、UUID、型号和总显存，因此应在派发 attempt 时生成
确定的描述，例如：

```text
1 x NVIDIA GeForce RTX 3090 (24 GiB VRAM)
1 x NVIDIA GeForce RTX 2080 Ti (11 GiB VRAM)
2 GPUs: NVIDIA GeForce RTX 3090 (24 GiB VRAM each)
```

通过 `DOJO_HARDWARE_DESCRIPTION` 传给 worker，`main_run` 改为优先采用 launcher 提供的值：

```python
os.environ["HARDWARE"] = os.environ.get("DOJO_HARDWARE_DESCRIPTION") or get_hardware()
```

现有 `instructions.txt` 的 `${HARDWARE}`，以及 draft、debug、improve、crossover operator 的
`{{hardware}}` 都会继续使用同一变量，因此不需要改 prompt 模板。这样每个 RunConfig 会根据实际
slot 得到不同硬件上下文，同时保留非 pool 入口的原有自动探测 fallback。

hardware description 至少包括数量、完整型号和单卡总显存；UUID/index 只写 metadata 和
manifest，不放进 prompt，因为它们对生成算法没有帮助。描述的是该 attempt 的稳定配额，而不是
启动瞬间的 free memory。

### 6.2 传入 Singularity 容器

当前 `SingularityJupyterServer` 使用 `--cleanenv`，并在镜像命令后通过容器内 `env` 显式注入
一组变量。实现 local pool 时必须让 `_build_container_environment()` 从宿主环境白名单式复制
`CUDA_VISIBLE_DEVICES` 和 `CUDA_DEVICE_ORDER`，不能依赖 Singularity 对普通宿主变量的隐式
继承。配置里的 `interpreter.env` 不应覆盖 launcher 分配的 mask；若用户配置了冲突值应报错。

预期命令语义为：

```text
CUDA_VISIBLE_DEVICES=<uuid> singularity exec --nv ... <SIF> \
  env CUDA_VISIBLE_DEVICES=<uuid> CUDA_DEVICE_ORDER=PCI_BUS_ID ... python ...
```

宿主侧 mask 让 Singularity/runtime helper 看到分配上下文，容器内显式 `env` 让 CUDA framework
在 `--cleanenv` 下仍得到同一 mask。验收应以容器内 PyTorch/CUDA 枚举和实际 UUID 为准，不能用
“容器内 `nvidia-smi` 只列出一张卡”作为条件：legacy `--nv` 可能挂载所有 device node，且
`nvidia-smi` 不一定遵守 `CUDA_VISIBLE_DEVICES`。

## 7. manifest、身份和结果分析

### 7.1 目录与 schema

建议使用与 srun pool 平行的目录：

```text
<meta-experiment>/local_gpu_pool/<sorted-run-id-hash>/
  manifest.json
  configs/<run-id>.json
  identities/<run-id>.attempt-<n>.json
  results/<run-id>.attempt-<n>.json
  logs/<run-id>.attempt-<n>.out
  logs/<run-id>.attempt-<n>.err
```

manifest 继续单 controller 写入并原子 rename，顶层至少记录：

```json
{
  "version": 1,
  "launcher_type": "local_gpu_pool",
  "host": "gpu-host",
  "host_boot_id": "...",
  "snapshot_path": "...",
  "inventory": [{"index": 0, "uuid": "GPU-...", "name": "RTX 3090", "memory_mb": 24576}],
  "tasks": {}
}
```

每个 attempt 记录 `status`、`pid`、`process_start_ticks`、`execution_id`、GPU UUID/index、stdout、
stderr、exit code、started/ended time 和 reason。状态沿用 `pending`、`launching`、`running`、
`completed`、`failed`、`cancelled`；本地模式不伪造 `allocation_id`、`step_id` 或 `slurm_state`。

建议 execution ID 为 `<hostname>:<pid>:<process-start-ticks>:a<attempt>`。单独的 PID 会复用，恢复时
必须同时检查 hostname、Linux boot ID 和 `/proc/<pid>/stat` start time。

### 7.2 metadata 兼容

`main_run` 当前把通用 launcher 身份也放在名为 `get_slurm_identity()` 的结构中。本地模式可以
保持已有 `slurm_*` 字段为空，并写 `metadata.launcher_type=local_gpu_pool`，同时新增通用字段：

- `execution_id`；
- `execution_host`；
- `gpu_uuids`；
- `launcher_type`。

较干净的后续重构是新增 `get_execution_identity()`，让 `get_slurm_identity()` 作为兼容 wrapper，
但这不是首版 launcher 的阻塞项。不要把本地 PID 填进 `slurm_id`。

### 7.3 分析读取

现有分析入口只寻找 `srun_pool/*/manifest.json`，并可能补查 `sacct`。应把 manifest reader 提取为
调度器无关的 `get_pool_tasks()`：

- `srun_pool` 任务继续按完整 step ID 查询 `sacct`；
- `local_gpu_pool` 只使用 manifest/attempt result，不调用任何 Slurm 命令；
- dashboard 和 error summary 使用 `execution_id` 或 run ID 关联日志；
- 旧 Submitit 实验保持原读取路径。

这样本地模式不会伪造 Submitit Job 或 Slurm accounting 数据。

## 8. 生命周期、退出与恢复

### 8.1 正常完成

worker 启动后先原子写 identity，再延迟 import `RunConfig` 和 `main_run`。`_main()` 正常返回后写
terminal result，controller 根据子进程退出码与 result 更新 manifest，归还 slot 并立即补位。
result 文件应包含成功/失败、退出码、结束时间和简短异常摘要；完整 traceback 保留在 stderr。

### 8.2 信号与清理

controller 收到 SIGINT/SIGTERM 时：

1. 停止派发；
2. 将 pending 保持为 pending 并写 reason；
3. 向 worker 发送 SIGTERM；
4. worker 的信号处理转为正常 Python 退出，使 `SingularityJupyterServer.stop()`/`atexit` 有机会
   停止独立的 Singularity 进程组；
5. 超过 grace period 后才 SIGKILL，并在 manifest 标记 cleanup 是否完整；
6. 不删除实验目录、attempt 日志、identity 或 result 文件。

仅杀 worker 进程组并不一定能杀掉 `SingularityJupyterServer`，因为后者当前使用
`start_new_session=True`。因此 worker 必须参与优雅清理，controller 还应在 identity/result 中记录
可验证的子容器 PID/PGID，超时后显式清理该进程组。不要用宽泛的 `pkill singularity`。

### 8.3 controller 崩溃与恢复

同一个 pool 由单 controller 写 manifest。恢复入口启动前先根据 identity 检查上次遗留进程；按
“不会并行启动第二个 launcher”的部署约束，恢复只发生在旧 controller 已退出之后。重启后：

- `completed` 不再运行；
- `pending` 重新排队；
- 有 terminal result 的 attempt 按 result 收敛状态；
- `running/launching` 根据 host boot ID、PID 和 process start time 检查原 worker；
- 原 worker 仍存活时不重复启动；要么等待它写出 result，要么先按记录的 PID/PGID 完成清理，
  再把对应 attempt 标记 interrupted；
- worker 不存在且没有成功 result 时标记 interrupted，并按 `max_retries` 决定是否重试；
- 机器重启后所有旧 PID 都失效，未完成 attempt 进入 interrupted/retry。

非父进程不能可靠获得另一个进程的 wait status，所以 terminal result 是恢复的事实来源；仅凭
`kill(pid, 0)` 只能判断“看起来还活着”。

极端情况下 worker 被 SIGKILL 而它启动的 Singularity/Jupyter 成为孤儿，孤儿仍可能占 GPU。
恢复时应根据 manifest 记录的精确 PID/PGID 尝试清理，并在重新派发前用 `nvidia-smi` 做一致性
检查；发现无法归属或清理的 compute process 时停止并提示人工处理，而不是在同一卡上叠加新任务。
若未来要求对 SIGKILL/宿主崩溃也自动强清理，应引入 systemd user scope 或受控 cgroup，而不是
继续堆 PID 猜测逻辑。

## 9. 代码组织与复用策略

建议按以下边界实现：

| 组件 | 职责 |
| --- | --- |
| `LocalGpuPoolConfig` | device 集合、并发和重试策略 |
| `LocalGpuPoolLauncher` | inventory、slot 分配、硬件描述、派发、监控、恢复、manifest |
| `main_local_worker.py` | identity/result、信号处理、调用 `main_run._main()` |
| pool common helpers | typed config、原子 JSON、batch key、文件名、公共状态 |
| `SingularityJupyterServer` | 单个 RunConfig 内 Jupyter 容器生命周期与 GPU mask 透传 |

`main_runner_job_array.launch_jobs()` 增加显式类型分派：

```python
if isinstance(launcher_cfg, LocalGpuPoolConfig):
    snapshot = LocalGpuPoolLauncher.resume_snapshot_path(config_list, launcher_cfg)
    return launch_local_gpu_pool(config_list, launcher_cfg, snapshot or create_snapshot())
if isinstance(launcher_cfg, SrunPoolConfig):
    ...
if isinstance(launcher_cfg, SlurmConfig):
    ...
```

主函数的完成处理应逐步从 `isinstance(SrunPoolConfig)` 改为 launcher 返回统一的 `PoolSummary`，
避免每增加一种同步 pool 就复制一次收尾逻辑。

实现时可以从 `SrunPoolLauncher` 提取纯工具（原子 JSON、run ID 文件名、meta experiment 路径、
typed config 写入），但 Slurm allocation/accounting 与本地 GPU inventory/slot 状态必须留在各自模块。
先保持两个 launcher 的生命周期代码清晰，即使存在少量重复，也比建立一个充满 scheduler hook 的
过度抽象基类更容易验证。

## 10. 不建议的替代方案

### 直接在 controller 中循环设置环境变量

`os.environ["CUDA_VISIBLE_DEVICES"]` 是进程全局状态。若 controller 并发启动任务，修改全局环境
会发生竞态。必须为每个 `Popen` 构造独立 `env` 字典。

### 只用 `nvidia-smi` free memory 选卡

free memory 是瞬时值，无法表达任务未来峰值；按它动态路由还会让调度和实验条件难以复现。它可以
用于启动诊断，但不参与 slot 资格或优先级计算。

### 让每个 Jupyter session 自己选 GPU

一个 RunConfig 会在搜索过程中反复创建/重置候选代码 session。若在内层分配 GPU，slot 会随
session 抖动，RunConfig 级日志、恢复和资源上限也难以保持一致。GPU 应在外层 worker attempt 的
整个生命周期内固定。

### 复用 `srun_pool` 并伪造 Slurm 环境变量

`SrunPoolLauncher` 还依赖 `scontrol`、`sacct`、`srun` 和 `scancel`。伪造 `SLURM_JOB_ID` 既不能
获得隔离，也会污染 metadata 和分析结果。

### 按 GPU 型号拆成多个 pool

当前硬件异构不要求把 3090 和 2080 Ti 拆成不同队列。调度器可以等价看待 slot，只需保证每个
attempt 的 prompt 收到准确型号和显存。显式拆池会减少自然的硬件条件 diversity，也会增加配置和
恢复复杂度，因此首版不采用。

## 11. 实施顺序

1. 增加 `LocalGpuPoolConfig`、Hydra 配置和 `main_runner_job_array` 类型分派，先支持 debug 展开。
2. 实现 GPU inventory/UUID 归一化、父级 mask 约束和进程内 slot 状态。
3. 实现单 GPU、单任务 worker，生成 per-attempt hardware description，并补齐宿主到
   `--cleanenv` 容器的 mask 显式透传。
4. 加入 typed config、独立日志、identity/result 和原子 local manifest。
5. 实现固定并发、slot 回收、重试和 fail-fast。
6. 实现信号、container PID/PGID 清理和 controller 重启恢复。
7. 将分析层扩展为通用 pool manifest reader，同时保持 srun accounting 行为不变。
8. 先在一张 2080 Ti 做最小 CUDA/Jupyter smoke，再在两张不同 GPU 上验证 UUID 隔离。
9. 用两张 3090 跑两个短真实 RunConfig，最后才扩大到目标采集规模。

## 12. 测试与验收条件

### 无 GPU 单元测试

- index、UUID、父级 `CUDA_VISIBLE_DEVICES` 和非法/重复 device 的归一化；
- 单/多 GPU slot 分配与回收，不会把同一 UUID 同时分给两个 running attempt；
- 3090/2080 Ti 的 hardware description 准确包含数量、型号和单卡显存；
- typed RunConfig、identity/result、manifest 和跨重启恢复；
- 固定并发、FIFO、重试、fail-fast、SIGTERM 和 timeout；
- Singularity 命令的容器环境包含准确 mask，且配置不能覆盖 launcher mask；
- local 分析路径不调用 `sacct`，旧 srun/Submitit 测试保持通过。

### 本机集成测试

- 每张 allowlisted GPU 分别运行 `torch.cuda.is_available()`、tensor 运算并记录真实 UUID；
- 两个并发 worker 各自看到 `torch.cuda.device_count()==1`，实际 CUDA UUID 不重复；
- 一个 worker 多次重置 Jupyter session 时始终使用同一物理 UUID；
- 3090 与 2080 Ti 混合运行时，manifest 的型号、显存、index 与 UUID 映射正确；
- 正常结束、异常、Ctrl-C 和 timeout 后无遗留 Singularity/Jupyter 进程；
- controller 被杀后，恢复逻辑不会把同一 slot 重复分配给仍存活的 worker，也不会重复运行已完成任务；
- 启动或恢复时发现独占假设不成立，launcher 会停止并报告占卡 PID/UUID；
- 至少两个真实短 RunConfig 完成完整的 LLM -> Singularity -> CUDA -> submission 链路。

开始大规模采集前，应明确接受以下残余限制：没有 Slurm/cgroup 级 GPU 安全隔离，没有 CPU/RAM
配额，没有跨用户强制仲裁，也没有节点故障迁移。若这些能力成为硬需求，应部署真正的本地调度器
或恢复 Slurm，而不是继续扩展 `CUDA_VISIBLE_DEVICES` 方案。

## 13. 实现记录：Local GPU Pool 与 Singularity

本节记录上述设计完成后实际落地的改动，组织方式与
`SLURM_MIGRATION_INVESTIGATION.md` 的“实现记录”一致。重点说明最终代码位置、关键实现、设计阶段
之外补充的可靠性处理，以及真实硬件和 Spaceship Titanic 的验收结果。

### 13.1 新增本地 GPU pool launcher

实现新增了独立的 `LocalGpuPoolConfig`、Hydra launcher 配置、`LocalGpuPoolLauncher` 和
`main_local_worker.py`。原有 Submitit/`sbatch` 与 allocation 内 `srun_pool` 路径均保持不变；
`main_runner_job_array` 根据 launcher dataclass 的具体类型显式分派。

主要代码位置：

- `src/dojo/config_dataclasses/launcher/local_gpu_pool.py::LocalGpuPoolConfig`：GPU 数量、并发、重试、
  timeout、fail-fast 和退出宽限期；
- `src/dojo/configs/launcher/local_gpu_pool.yaml`：Hydra 默认配置；
- `src/dojo/main_runner_job_array.py::launch_jobs`：三种 launcher 的统一选择入口；
- `src/dojo/core/runners/local/gpu_pool.py::LocalGpuPoolLauncher`：GPU inventory、slot、worker、manifest、
  恢复和清理；
- `src/dojo/main_local_worker.py::main`：单个 RunConfig attempt 的本地 worker 入口。

配置校验明确禁止 detached controller。没有 Slurm 等外部 scheduler 时，controller 是 worker 状态、
重试与资源回收的唯一所有者：

```python
def validate(self) -> None:
    super().validate()
    if self.gpus_per_task <= 0:
        raise ValueError("gpus_per_task must be positive")
    if self.max_retries < 0:
        raise ValueError("max_retries cannot be negative")
    if not self.await_completion or not self.monitor_jobs:
        raise ValueError(
            "local_gpu_pool must await and monitor its workers; "
            "detached pool controllers are not supported"
        )
```

入口分派先尝试恢复已有 pool 使用的 snapshot；只有第一次运行才创建新 snapshot。这样 controller
重启后继续使用同一份固定代码，而不会把当前 checkout 的新修改混入旧 batch：

```python
def launch_jobs(config_list, launcher_cfg):
    if isinstance(launcher_cfg, LocalGpuPoolConfig):
        snapshot_path = LocalGpuPoolLauncher.resume_snapshot_path(
            config_list, launcher_cfg
        )
        if snapshot_path is None:
            snapshot_path = create_snapshot()
        return launch_local_gpu_pool(config_list, launcher_cfg, snapshot_path)
    if isinstance(launcher_cfg, SrunPoolConfig):
        ...
    if isinstance(launcher_cfg, SlurmConfig):
        ...
```

`main()` 的同步 pool 收尾也同时接受 `LocalGpuPoolConfig` 和 `SrunPoolConfig`。pool 返回的 summary 中
只要存在未完成任务，入口就抛出异常并给出 manifest 路径，而不会再把本地 worker 伪装成 Submitit
Job 交给 `monitor_jobs()`。

### 13.2 GPU inventory、父级 mask 与 UUID 归一化

`discover_gpu_inventory()` 实际执行两次只读探测。第一次调用 `nvidia-smi -L` 检测 MIG；首版发现
MIG 后明确拒绝启动。第二次查询物理 GPU 的 index、UUID、型号、显存和 compute mode：

```python
result = run(
    [
        executable,
        "--query-gpu=index,uuid,name,memory.total,compute_mode",
        "--format=csv,noheader,nounits",
    ],
    check=False,
    capture_output=True,
    text=True,
)
```

解析结果保存为不可变的 `GpuDevice`：

```python
@dataclass(frozen=True)
class GpuDevice:
    index: int
    uuid: str
    name: str
    memory_mb: int
    compute_mode: str
```

`normalize_gpu_devices()` 支持配置物理 index、完整 UUID 或能唯一匹配的 UUID 前缀，但内部统一使用
完整物理 UUID。若 controller 自身已有 `CUDA_VISIBLE_DEVICES`，该 mask 会先被解析成 allowlist；
`launcher.devices` 只能进一步缩小它，不能逃逸父级限制：

```python
parent_devices = (
    tuple(_resolve_device_token(token, inventory) for token in parent_tokens)
    if parent_is_set
    else tuple(inventory)
)
selected = (
    tuple(_resolve_device_token(token, inventory) for token in configured_devices)
    if configured_devices is not None
    else parent_devices
)

if parent_is_set:
    allowed = {device.uuid for device in parent_devices}
    disallowed = [device.uuid for device in selected if device.uuid not in allowed]
    if disallowed:
        raise ValueError("launcher.devices cannot escape ...")
```

空 mask、`-1`、重复 index/UUID、不存在或歧义 UUID、重复物理卡都会在启动前失败。生产配置仍推荐
写 UUID；index 主要用于本机临时命令和易读配置。

实现还保留两个 inventory 视图：manifest 的 `inventory` 是 pool 初次创建时的不可变基线，
`current_inventory` 是本次 controller 发现结果，`inventory_history` 按 host、boot ID 和发现时间记录
变化。这样恢复不会悄悄改写最初实验条件，同时能诊断重启、换卡或驱动重新枚举后的环境差异。

### 13.3 FIFO、round-robin 与多 GPU slot

launcher 使用一个 `deque[GpuDevice]` 表示当前可用设备。pending RunConfig 也是 FIFO 队列；只有队首
任务能取卡。每次从设备队首取 `gpus_per_task` 张卡，attempt 结束后按原顺序归还队尾：

```python
def _allocate_devices(self) -> tuple[GpuDevice, ...]:
    if len(self.available_devices) < self.cfg.gpus_per_task:
        raise RuntimeError("Not enough available GPUs for a local worker")
    return tuple(
        self.available_devices.popleft() for _ in range(self.cfg.gpus_per_task)
    )

def _release_devices(self, devices: Sequence[GpuDevice]) -> None:
    in_queue = {device.uuid for device in self.available_devices}
    for device in devices:
        if device.uuid in in_queue:
            raise RuntimeError(f"GPU {device.uuid} was released twice")
        self.available_devices.append(device)
        in_queue.add(device.uuid)
```

这既实现了设备 round-robin，也通过 double-release 检查保护内部资源账本。并发上限在构造阶段
验证：

```text
max_parallel * gpus_per_task <= len(selected devices)
```

`max_parallel=null` 时自动使用 `floor(len(devices) / gpus_per_task)`。实现与测试没有把一个 attempt
硬编码成一张 GPU；两张 GPU 的 slot 会获得逗号连接的 UUID mask，并生成对应的双卡 hardware
description。

主循环只在同时满足 pending、未停止、并发未满以及有完整 GPU 组合时补位：

```python
while (
    pending
    and not self._stop_requested
    and len(running) + len(external) < self.max_parallel
    and len(self.available_devices) >= self.cfg.gpus_per_task
):
    run_id = pending.popleft()
    devices = self._allocate_devices()
    running[run_id] = self._launch(run_id, devices)
```

`external` 是恢复后仍存活、但已不是当前 controller 子进程的 worker；它与新启动的 `running`
worker 一样占用并发和 GPU slot，因此恢复过程中不会重复分配同一张卡。

启动第一个新 worker 前，launcher 还会验证 snapshot、宿主 Python、实验目录、MLE-bench 数据、SIF、
overlay、bind source 和 Singularity runtime。`nvidia-smi --query-compute-apps` 若发现所选 GPU 已有
compute process，会输出醒目 warning。这里按本文的单 launcher/独占部署假设只警告，不擅自终止
或抢占无法归属的外部进程。

### 13.4 每个 worker 的独立 CUDA 环境与硬件 prompt

controller 不修改自身全局 `os.environ` 来轮流选卡，而是为每次 `Popen` 复制并构造独立环境。
核心环境如下：

```python
assigned_mask = ",".join(device.uuid for device in devices)
env = os.environ.copy()
env.update(
    {
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        "CUDA_VISIBLE_DEVICES": assigned_mask,
        "DOJO_LAUNCHER_TYPE": "local_gpu_pool",
        "DOJO_GPU_UUIDS": assigned_mask,
        "DOJO_HARDWARE_DESCRIPTION": format_hardware_description(devices),
        "DOJO_ATTEMPT": str(attempt),
        "DOJO_EXECUTION_HOST": self.host,
        "DOJO_WORKER_IDENTITY_PATH": str(identity_path),
        "PYTHONUNBUFFERED": "1",
    }
)
```

worker 由 snapshot 对应的宿主 Python 启动，以 snapshot 为工作目录，使用参数数组、独立 stdout/
stderr 文件和新 session：

```python
process = subprocess.Popen(
    command,
    cwd=self.snapshot_path,
    env=env,
    stdout=stdout_file,
    stderr=stderr_file,
    start_new_session=True,
)
```

`format_hardware_description()` 按获分配设备而不是整机生成 prompt 文本。例如：

```text
1 x NVIDIA GeForce RTX 3090 (24 GiB VRAM)
2 GPUs: NVIDIA GeForce RTX 3090 (24 GiB VRAM each)
2 GPUs: 1 x NVIDIA GeForce RTX 3090 (24 GiB VRAM); 1 x NVIDIA GeForce RTX 2080 Ti (11 GiB VRAM)
```

`main_run._main()` 优先采用 launcher 的描述，其他 launcher 和直接运行方式仍保留原来的自动探测：

```python
os.environ["HARDWARE"] = (
    os.environ.get("DOJO_HARDWARE_DESCRIPTION") or get_hardware()
)
```

因此 `instructions.txt` 和各 solver operator 使用的 `${HARDWARE}`/`{{hardware}}` 能准确反映当前
attempt 的卡型、数量和单卡显存；异构机器上分到 2080 Ti 的任务不会再误以为自己同时拥有 3090。

如果 `interpreter.env` 配置了与 launcher 不同的 `CUDA_VISIBLE_DEVICES` 或非 `PCI_BUS_ID` 的
`CUDA_DEVICE_ORDER`，launcher 会在启动前拒绝该配置，避免内外两层出现互相矛盾的资源声明。

### 13.5 `--cleanenv` 下显式传入 Singularity

`SingularityJupyterServer` 原本使用 `--cleanenv`，所以不能依赖普通宿主变量被隐式保留。现在
`_build_container_environment()` 将 `CUDA_VISIBLE_DEVICES` 和 `CUDA_DEVICE_ORDER` 作为受保护的
白名单变量从 worker 环境复制到容器内 `env`：

```python
for name in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER"):
    host_value = host_env.get(name)
    configured_value = configured_env.get(name)
    if host_value is not None:
        if configured_value is not None and str(configured_value) != host_value:
            raise ValueError(
                f"interpreter.env cannot override launcher-assigned {name}"
            )
        container_env[name] = host_value
```

最终同一个 UUID mask 同时存在于启动 Singularity 的宿主环境和镜像后的容器命令中：

```text
CUDA_VISIBLE_DEVICES=GPU-... singularity exec --cleanenv --nv ... image.sif \
  env CUDA_VISIBLE_DEVICES=GPU-... CUDA_DEVICE_ORDER=PCI_BUS_ID ... python ...
```

验证标准使用容器内 `torch.cuda.device_count()`、CUDA tensor 运算和实际物理 UUID，而不是要求
容器内 `nvidia-smi` 只打印一张卡。Singularity CE 3.10.1 的 legacy `--nv` 可能仍把所有 NVIDIA
device node 带入容器；真正限制 CUDA framework 可见性的仍是 UUID mask。

### 13.6 worker identity、结果文件与 metadata

`main_local_worker` 在导入 `RunConfig`、solver 和 `main_run` 之前先安装 SIGINT/SIGTERM handler 并
原子写 identity。即使后续 import 失败，controller 也能得到 worker 的精确身份与 GPU 归属：

```python
execution_id = (
    f"{host}:{pid}:{ticks if ticks is not None else 'unknown'}:a{args.attempt}"
)
_atomic_write_json(
    args.identity,
    {
        "run_id": args.run_id,
        "attempt": args.attempt,
        "execution_id": execution_id,
        "host": host,
        "host_boot_id": _host_boot_id(),
        "pid": pid,
        "pgid": os.getpgid(pid),
        "process_start_ticks": ticks,
        "gpu_uuids": ...,
        "container_pid": None,
        "container_pgid": None,
        "container_process_start_ticks": None,
    },
)

from dojo.config_dataclasses.run import RunConfig
from dojo.main_run import _main
```

`execution_id` 使用 hostname、PID、Linux `/proc/<pid>/stat` start ticks 和 attempt 号。controller 的
恢复判断还同时检查 boot ID，解决单独使用 PID 时的 PID 复用和机器重启误判。

worker 正常完成写 `status=completed`、`exit_code=0` 的 result；异常或信号退出写 failed/cancelled、
exit code、异常摘要、结束时间和 termination signal，完整 traceback 留在 stderr。controller 只把
“成功 result 且进程退出码为 0”收敛为 completed；进程消失但没有成功 terminal result 会明确记为
failed，而不会猜测成功。

为了能清理 worker 之外独立 session 中的 Singularity，`SingularityJupyterServer` 在容器启动和
停止时更新同一个 identity 文件，发布精确的 container PID、PGID 和 start ticks：

```python
self._subprocess = subprocess.Popen(..., start_new_session=True, ...)
_publish_container_identity(self._subprocess.pid)
...
self._subprocess = None
_publish_container_identity(None)
```

实验 metadata 新增 scheduler-independent 字段：

- `execution_id`；
- `execution_host`；
- `gpu_uuids`。

`main_run` 从 `DOJO_EXECUTION_ID`、`DOJO_EXECUTION_HOST` 和 `DOJO_GPU_UUIDS` 写入这些字段。本地模式
的 `launcher_type` 为 `local_gpu_pool`，原有 `slurm_id`、`slurm_allocation_id` 和 `slurm_step_id`
保持为空；没有用本地 PID 冒充 Slurm job ID。

### 13.7 manifest、重试、信号、timeout 与恢复

pool 目录最终采用设计中的稳定结构：

```text
<meta-experiment>/local_gpu_pool/<sorted-run-id-hash>/
  manifest.json
  configs/<run-id-hash>.json
  identities/<run-id-hash>.attempt-<n>.json
  results/<run-id-hash>.attempt-<n>.json
  logs/<run-id-hash>.attempt-<n>.out
  logs/<run-id-hash>.attempt-<n>.err
```

batch key 由排序后的 RunConfig ID 计算，因此与派发顺序、PID 和某次 controller 生命周期无关。
每个 RunConfig 配置使用 `to_typed_dict()` 写入独立 JSON；重试复用同一 typed config，但 identity、
result 和日志都带 attempt 号，历史证据不会被覆盖。

manifest 和 worker JSON 均使用“同目录临时文件 + flush + fsync + `os.replace`”提交：

```python
temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
with temporary_path.open("w", encoding="utf-8") as file:
    json.dump(data, file, indent=2, sort_keys=True)
    file.flush()
    os.fsync(file.fileno())
os.replace(temporary_path, path)
```

controller 是 manifest 的唯一 writer；worker 只写自己的 identity/result。manifest 为每个 attempt
保存 GPU UUID/index/完整 device metadata、hardware description、PID/start ticks、execution ID、
日志、结果、状态、退出码和原因。

失败 attempt 数未超过 `max_retries` 时重新进入 pending 队尾；`fail_fast=true` 时第一个用尽重试的
失败会停止后续派发，尚未启动的任务保留为 pending。`task_timeout_seconds` 同时适用于当前子进程和
恢复发现的 external worker。

controller 收到 SIGINT/SIGTERM 后：

1. 停止派发并保留 pending 任务；
2. 向 worker 进程组发 SIGTERM；
3. 等待 `shutdown_grace_seconds`；
4. 必要时精确核对 start ticks 后向 Singularity 容器组和 worker 组发 SIGKILL；
5. 将 attempt 标记 cancelled，保留全部日志与状态文件。

恢复时按以下顺序收敛：

- completed task 直接跳过；
- 已存在 terminal result 的 task 以 result 为事实来源；
- running/launching task 用 host、boot ID、PID 和 start ticks 判断 worker 是否仍为原进程；
- 原 worker 仍存活时登记为 external，保留其 GPU slot并等待 result，不重复启动；
- worker 已消失但记录的 Singularity 子进程仍精确匹配时，先 TERM/KILL 该 container process group，
  再允许回收 GPU；
- 没有成功 result 的中断 attempt 标记 failed，并按重试策略处理；
- manifest 引用当前 inventory 中不存在、当前 `launcher.devices` 不允许或数量与 `gpus_per_task`
  不一致的 GPU 时停止恢复，而不是在错误设备上继续。

孤儿清理只针对 identity 中精确记录且 start ticks 匹配的 PID/PGID，不使用 `pkill singularity`。这项
处理是在实现审查中针对 `SingularityJupyterServer(start_new_session=True)` 补强的，比只清理 worker
进程组更可靠，但仍不是 cgroup/systemd scope 提供的强生命周期边界。

### 13.8 结果分析改为通用 pool manifest

原分析代码只发现 `srun_pool/*/manifest.json`，并默认可用 `sacct`。现在
`src/dojo/core/runners/slurm/manifest.py` 提供 scheduler-independent 的：

```python
POOL_LAUNCHER_TYPES = {"srun_pool", "local_gpu_pool"}

def find_pool_manifests(...): ...
def load_pool_manifests(...): ...
def get_pool_tasks(...): ...
```

旧的 `find_srun_pool_manifests()`、`load_srun_pool_manifests()` 和 `get_srun_pool_tasks()` 保留为只筛选
srun 的兼容 wrapper，现有调用方不会因改名立即失效。

`prepare_pool_dataframe()` 对两类 pool 使用同一张任务表，但只为 `launcher_type=srun_pool` 且具有
step ID 的记录查询 accounting：

```python
step_ids = [
    task["step_id"]
    for task in tasks
    if task.get("launcher_type") == "srun_pool" and task.get("step_id")
]
```

本地任务的 `JobID` 展示 `execution_id`，并额外提供 `LauncherType` 与 `GPUUUIDs`；不会调用
`sacct`。error summary 和 dashboard 同样改为优先使用 `step_id`、其次 `execution_id`、最后 run ID
关联日志。dashboard 新增通用 `has_pool_logs`、`pool_job_count` 和 `pool_status`，同时保留纯 srun
实验的旧字段。

### 13.9 测试与真实运行验收

新增的主要无 GPU 测试位于 `tests/test_local_gpu_pool.py`，覆盖：

- `nvidia-smi` inventory 解析与 MIG 拒绝；
- index、UUID、UUID 前缀、父级 mask、重复设备和空 mask；
- 单卡、同型号双卡和异构多卡 hardware description；
- 固定并发、FIFO/round-robin slot、独立 CUDA mask 与 manifest；
- 多 GPU attempt；
- 失败重试、fail-fast 和成功 result 恢复；
- 存活 external worker 恢复时不重复运行；
- worker 消失后的孤儿 container process group 清理；
- timeout、controller shutdown 与 GPU slot 回收；
- local manifest 分析不调用 Slurm；
- local config 必须由同步监控 controller 管理。

运行 Spaceship Titanic 单 seed demo 

```bash
conda activate aira-dojo
set -a
source .env
set +a
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
```

可以先查看物理 index、UUID、型号和显存：

```bash
nvidia-smi --query-gpu=index,uuid,name,memory.total --format=csv,noheader
```

下面的命令使用物理 GPU index 2、一个并发 worker、seed 42 和 `step_limit=5` 运行本文验收的
Spaceship smoke。`runner_example` 原本直接写入了 Slurm launcher 的 `qos` 字段，所以切换到
`local_gpu_pool` 时需要用 `~launcher.qos` 删除它：

```bash
python -m dojo.main_runner_job_array \
  +_exp=runner_example \
  'benchmark.tasks=[spaceship-titanic]' \
  'vars={metadata.seed:[42]}' \
  'solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash' \
  metadata.git_issue_id=local-gpu-pool-spaceship-demo \
  launcher=local_gpu_pool \
  '~launcher.qos' \
  launcher.debug=false \
  'launcher.devices=[2]' \
  launcher.max_parallel=1 \
  logger.use_wandb=false
```

`launcher.devices=[2]` 应替换为准备使用的 GPU；生产运行更推荐填上一条命令查询到的完整 UUID，
例如 `'launcher.devices=[GPU-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx]'`。若只想检查 Hydra 展开而不
创建 snapshot、worker 或容器，把 `launcher.debug=false` 改成 `launcher.debug=true`。相同
`metadata.git_issue_id`、seed 和其余配置再次运行会命中同一稳定 manifest：completed task 会直接
跳过；要启动一次全新的实验，应更换 `metadata.git_issue_id`。