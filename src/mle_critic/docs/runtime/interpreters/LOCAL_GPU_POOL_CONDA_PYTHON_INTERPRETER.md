# 使用 `local_gpu_pool` 调度 Conda Python interpreter

日期：2026-07-27

本文记录在没有可用 Singularity/Apptainer（或 Docker NVIDIA Container Toolkit）时，如何让
`local_gpu_pool` 直接调度当前 `aira-dojo` Conda 环境中的 `PythonInterpreter`，并给出一次
Spaceship Titanic launcher smoke test 的实测命令和结果。

## 1. 适用范围与执行链

`interpreter=python` 使用当前环境的 Python 子进程，不需要 superimage 或容器；但
`local_gpu_pool` 仍然需要宿主机能运行 `nvidia-smi`，因为它用该命令发现 GPU、分配 GPU UUID，
并通过 `CUDA_VISIBLE_DEVICES` 限制 worker 可见的设备。执行链为：

```text
dojo.main_runner_job_array
  -> create_snapshot
  -> LocalGpuPoolLauncher
  -> CUDA_VISIBLE_DEVICES=<assigned GPU UUID>
  -> dojo.main_local_worker
  -> dojo.main_run._main()
  -> PythonInterpreter
```

相较于直接执行 `python -m dojo.main_run`，launcher 额外提供 GPU 槽位分配、并发限制、worker
进程、attempt/retry、snapshot、manifest 以及 stdout/stderr 日志。它不提供容器级隔离；候选代码
仍以当前用户权限访问宿主文件、网络和已安装的 Python 包。

## 2. 代码改动

修改文件：[src/dojo/core/runners/local/gpu_pool.py](../../dojo/core/runners/local/gpu_pool.py)

原实现无条件要求 `singularity` 出现在 `PATH`，因此即使 run config 使用
`PythonInterpreterConfig` 也会在 launcher 启动前失败。`LocalGpuPoolLauncher._required_paths()`
现在仅在 interpreter 配置了 `container_runtime` 时检查容器运行时：

```python
runtime = getattr(run_cfg.interpreter, "container_runtime", "")
if runtime:
    if runtime != "singularity":
        raise ValueError(...)
    if shutil.which("singularity") is None:
        raise RuntimeError(...)
```

因此：

- `interpreter=python` 不再需要 Singularity；
- Jupyter/superimage interpreter 仍要求 `container_runtime=singularity` 和可执行的
  `singularity`，避免误把容器任务静默地当成宿主 Python 任务运行；
- `nvidia-smi`、GPU 独占部署和 launcher 的设备校验保持不变。

新增测试位于 [tests/test_local_gpu_pool.py](../../../tests/test_local_gpu_pool.py)：分别验证 Python
interpreter 在没有 Singularity 时可以通过路径校验，以及容器 interpreter 仍会拒绝缺少
Singularity 的环境。

## 3. Spaceship Titanic launcher smoke test

在仓库根目录、已激活 `aira-dojo` 环境，并准备好 `.env`、MLE-bench 数据和 CUDA PyTorch 后执行：

```bash
set -a
source .env
set +a
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost

python -m dojo.main_runner_job_array \
  +_exp=runner_example \
  launcher=local_gpu_pool \
  '~launcher.qos' \
  interpreter=python \
  'benchmark.tasks=[spaceship-titanic]' \
  'vars={metadata.seed:[42]}' \
  'solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash' \
  metadata.git_issue_id=local_gpu_pool_conda_smoke_20260727 \
  solver.step_limit=2 \
  launcher.debug=false \
  'launcher.devices=[0]' \
  launcher.max_parallel=1 \
  launcher.gpus_per_task=1 \
  launcher.max_retries=0 \
  logger.use_wandb=false
```

`~launcher.qos` 很重要：`runner_example` 继承的配置包含 Slurm-only 的 `qos` 字段，而本地
launcher 不使用该字段；删除它即可避免配置校验失败。`launcher.devices=[0]` 选择物理 GPU
索引，`gpus_per_task=1` 为每个 run 分配一张卡，`max_parallel=1` 让 smoke test 串行执行。

本次命令输出：

```text
Local GPU pool finished:
manifest_path:
  logs/aira-dojo/user_zjchen_issue_local_gpu_pool_conda_smoke_20260727/local_gpu_pool/c05566bdf977/manifest.json
launcher_type: local_gpu_pool
counts: completed=1
successful: True
```

manifest 中的关键事实：

```text
snapshot_path: logs/aira-dojo/snapshots/2026-07-27-21-31-15-806933
run status: completed
attempt: 1
exit_code: 0
gpu_indices: [0]
gpu_uuids: [GPU-be49f866-af61-482b-a249-9ce8c7a1eddb]
```

worker prompt 正确报告了 `1 x NVIDIA GeForce RTX 2080 Ti (11 GiB VRAM)`，说明 GPU inventory、
UUID 分配和环境传递均已生效。该次 smoke 中模型生成的候选代码随后因
`KeyError: 'LastName'` 失败，未产生有效 submission；这是候选 agent 代码错误，不是 launcher、
Python interpreter 或 GPU 分配错误。launcher 本身已正常完成并写出成功 manifest。

## 4. 与直接 `main_run` 的关系

如果只需要验证 Conda interpreter 和任务逻辑，可使用
[CONDA_DIRECT_INTERPRETER_SETUP.md](./CONDA_DIRECT_INTERPRETER_SETUP.md) 中的直接命令：

```bash
python -m dojo.main_run \
  +_exp=mlebench/aira_greedy_deepseek_flash_spaceship \
  interpreter=python \
  metadata.seed=42 \
  logger.use_wandb=false
```

直接路径不创建 launcher snapshot/manifest，也不做多任务 GPU 排队；`local_gpu_pool` 适合需要
本机多 GPU 槽位管理、并发控制和可恢复 attempt 记录的场景。两条路径都绕过容器，均不应被视为
不可信代码的安全沙箱。

## 5. 验证

本次改动已通过：

```bash
python -m pytest -q tests/test_local_gpu_pool.py tests/test_slurm_migration.py
# 29 passed

python -m compileall -q \
  src/dojo/core/runners/local/gpu_pool.py \
  src/dojo/tasks/mlebench/task.py \
  tests/test_local_gpu_pool.py
git diff --check
```
