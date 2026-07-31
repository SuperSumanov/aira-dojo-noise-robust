# 基于 Chroot/Namespaces 的 Conda Python Interpreter 隔离计划

日期：2026-07-29

## 1. 最终目标与结论

这是一个实验性科研项目。本方案只解决一个核心问题：

> agent 可以正常使用 Conda/Python、读取数据并写自己的 workspace，但不能修改 workspace 之外的
> 任何宿主文件，从而不破坏同一 K8s Pod 中其他用户的数据。

CPU、内存、网络和 GPU 用量不在本方案的隔离范围内，明确不使用 cgroup，也不增加其他资源限制
或监控机制。

当前 Pod 具备 `CAP_SYS_CHROOT`、`CAP_SYS_ADMIN`、`SETUID` 和 `SETGID`，并且已经验证 mount/PID
namespace 可以创建。因此目标可行，推荐实现一个显式选择的 `ChrootPythonInterpreter`：

1. 主进程按现有逻辑创建本次 agent 的 workspace。
2. 为 agent 创建独立 mount namespace，使后续 mount 只影响该 agent。
3. 在 namespace 中将宿主文件系统映射为只读，再将该 workspace 单独映射为可写。
4. 使用 chroot 让这份文件系统视图成为 agent 的根目录。
5. 切换到临时低权限数字 UID/GID、清空附加组和 capabilities，然后执行 agent code。
6. 使用 PID namespace 管理 agent 的全部子进程，退出时一起清理。

不能只在现有 `child_proc_setup()` 中加一行 `chroot()`：chroot 只改变根目录，不会自动把文件变成
只读，也不会管理 agent 启动的后台进程。文件写隔离需要 chroot、mount namespace、只读 mount 和
低权限 UID 配合完成。

## 2. 本次仓库调查

主要调查文件：

- `src/dojo/core/interpreters/python.py`
- `src/dojo/config_dataclasses/interpreter/python.py`
- `src/dojo/configs/interpreter/python.yaml`
- `src/dojo/config_dataclasses/interpreter/__init__.py`
- `src/dojo/tasks/mlebench/task.py`
- `src/dojo/main_run.py`
- `tests/test_python_interpreter.py`
- `src/mle_critic/scripts/check_isolation.sh`
- `src/mle_critic/docs/runtime/interpreters/CONDA_DIRECT_INTERPRETER_SETUP.md`

本次只进行了代码阅读和不会影响其他任务的 namespace 能力探测，没有实际运行 agent，没有创建用户，
也没有在共享 mount namespace 中执行挂载。

当前环境关键事实：

| 项目 | 结果 | 影响 |
| --- | --- | --- |
| 当前身份 | `uid=0(root)` | agent 执行前必须降权 |
| Kernel | Linux 5.10.134 | 支持基础 mount/PID namespace |
| Mount + PID namespace | 创建成功 | 可以隔离 mount 视图并统一回收子进程 |
| User namespace | `user.max_user_namespaces = 0` | 不采用 rootless user namespace 方案 |
| Conda prefix | `/data/public/.../miniconda3/envs/aira-dojo` | chroot 内要保持原绝对路径只读可见 |
| Repo real path | `/public/hk-research/.../aira-dojo-noise-robust` | editable install 需要仓库只读可见 |
| Workspace | `${logger.output_dir}/workspace_agent` | 适合作为本次 agent 唯一可写目录 |

## 3. 当前 Python interpreter 的行为与问题

`interpreter=python` 当前执行链为：

```text
main_run
  -> PythonInterpreter.__init__()
  -> multiprocessing.Process(target=_run_session)
  -> child_proc_setup(): chdir(working_dir)
  -> exec(agent code, persistent global_scope)
```

可以继续复用的部分：

- 三个 `multiprocessing.Queue` 的代码、输出和状态协议；
- `reset_session=False` 时持久化 `global_scope` 的 session 语义；
- traceback、return value 和 `ExecutionResult`；
- 当前 wall-clock timeout 行为；
- Conda 环境及已经安装的 Python/CUDA 依赖。

需要解决的问题：

- `os.chdir(working_dir)` 只是改变当前目录，不阻止绝对路径、`..` 或 symlink 访问其他目录。
- 子进程继承当前 UID；本机当前是 root，agent 因而可能修改大量宿主文件。
- `cleanup_session()` 只终止直接的 `multiprocessing.Process`，agent 创建的孙进程可能继续运行。
- `main_run._main()` 没有用 `try/finally` 覆盖完整生命周期，中途异常可能跳过 cleanup。
- `working_dir/data` 默认可能是指向真实数据目录的 symlink，必须保证目标仍为只读。
- `file_name` 和 `fetch_file()` 应限制在 workspace 内，避免路径穿越。

## 4. 需要建立的文件系统视图

### 4.1 Mount namespace 的作用

Mount namespace 不复制文件，也不分配一块新磁盘。它只给 agent 一份独立的挂载视图：

```text
共享 Pod 中其他进程看到：
  /                         原来的读写状态
  /.../workspace_agent      可写

agent 的 mount namespace 中看到：
  /                         只读
  /.../workspace_agent      单独覆盖为可写
```

将根目录改成只读只对 agent namespace 生效，其他用户仍看到原来的文件系统，不会受到影响。

### 4.2 推荐构造顺序

1. 在宿主侧解析并检查 `working_dir`，确认它是本次运行专属的真实目录，不是 symlink。
2. 创建 agent supervisor 子进程。
3. Supervisor 创建独立 mount namespace，并立即执行 `mount --make-rprivate /`。
4. 在 sandbox runtime directory 下准备一个空的 `root/` 挂载点。
5. 将宿主 `/` recursive bind 到 `root/`，保留 Conda、系统库、仓库和数据的原绝对路径。
6. 将克隆根下的所有 mount point 递归 remount 为只读。
7. 将真实 `working_dir` 再 bind 到克隆根中的相同绝对路径，并 remount 为可写。
8. 为 `/tmp`、`/run`、`HOME` 和常用 cache 提供 workspace 内的可写目录，或使用 sandbox 私有
   tmpfs；它们不能指向共享宿主临时目录。
9. 检查最终 mount table，确认 writable 路径只有明确白名单中的 workspace、私有临时目录和新 PID
   namespace 的 `/proc`。
10. 进入 chroot、切换低权限 UID/GID，最后启动 agent session loop。

只 remount 顶层根目录是不够的，因为 `/data`、`/dev` 等可能是独立 submount。实现需要解析
`/proc/self/mountinfo`，从深到浅将克隆树里的 submount 分别设为只读，然后反向验证不存在意外的
可写 mount。

### 4.3 数据和 workspace

Workspace 可以继续由现有 runtime 动态创建，不要求使用固定路径。关键条件是：

- 每次 agent 使用独立 workspace；
- workspace 在启动 sandbox 前创建；
- workspace 本身不是 symlink，也不是 repo、data directory 或共享目录；
- workspace 是 agent 视角中唯一持久可写目录；
- `workspace/data` 即使是 symlink，其最终 data target 仍位于只读 mount；
- evaluator 在 agent 结束后继续从真实宿主 workspace 读取输出。

例如：

```text
宿主真实目录：
  logs/run-123/workspace_agent/

agent 视图：
  /.../logs/run-123/workspace_agent/   可写 bind mount
  /data/...                            只读
  /public/...repo...                   只读
  /data/.../miniconda...               只读
```

agent 写出的 `submission.csv` 会直接出现在真实 workspace 中，不需要从另一份文件系统复制出来。

### 4.4 路径安全

- `working_dir` 必须先 `resolve()`，并拒绝 `/`、repo root、data root 及它们的祖先。
- `file_name` 必须是 workspace 内的相对路径；拒绝绝对路径和解析后包含 `..` 的路径。
- `fetch_file()` 只允许访问 workspace 内的文件。
- Cleanup 和 ownership 处理不得跟随 symlink。
- Agent 启动前关闭不需要的继承 FD，尤其不能保留指向 chroot 外目录的 directory FD。

## 5. 低权限 UID/GID

不建议调用 `useradd/userdel`。修改共享 `/etc/passwd` 会带来并发冲突，进程异常退出时还可能留下
无用用户。

推荐直接使用数字 UID/GID：

1. 提前配置一小段不会与平台用户冲突的 UID/GID 范围。
2. 每次运行从中选择一个空闲编号，并用 runtime directory 中的锁文件避免两个并发 sandbox 选到
   同一编号。
3. 在 sandbox 内提供一份临时只读 `passwd/group` 文件，让需要用户名的工具能够正常工作；不修改
   宿主 `/etc/passwd`。
4. Agent executor 依次执行 `setgroups([])`、`setgid()`、`setuid()`，清空 capabilities，并设置
   `no_new_privs`。
5. Agent 退出后释放编号锁。

### 5.1 Workspace 写权限

临时 UID 必须能够写 workspace。由于当前环境没有 `setfacl/getfacl`，第一版使用简单做法：

- 仅接受 interpreter 专属的 `${logger.output_dir}/workspace_agent`；
- 启动前记录 workspace 原 owner，然后将该目录交给临时 UID/GID；
- Agent 全部进程退出后，再将 workspace 内容交还原 owner；
- 所有 ownership 操作只作用于经过校验的 workspace，且不跟随 symlink。

这样不会改变 data directory、repo 或其他用户目录的 owner。

## 6. 进程结构与清理

### 6.1 推荐结构

```text
Python 主进程
  -> Sandbox supervisor
       -> 新 PID namespace 的 init（PID 1）
            -> 低权限 Python executor
                 -> agent 创建的训练进程/DataLoader/subprocess
```

`ChrootPythonInterpreter` 可以继承 `PythonInterpreter`，但建议先把现有 session loop 抽成可复用函数，
而不是让子类复制整份 `_run_session()`。

职责划分：

- 主进程：保留现有 `run()` API、queues、timeout 和 `ExecutionResult`。
- Supervisor：创建 mount/PID namespace，管理 sandbox 生命周期。
- Namespace init：转发信号并回收孤儿进程；它不执行 agent code。
- Executor：完成 chroot、降权，然后运行现有 persistent Python session。

使用 PID namespace 的原因很直接：agent 可能 fork、双重 fork 或启动后台训练进程。namespace init
退出时，内核会一起终止该 namespace 内剩余进程，比按进程名或 UID 扫描安全，也不会误杀其他用户。

### 6.2 正常退出和 timeout

- `reset_session=False`：继续使用同一 executor 和 `global_scope`。
- `reset_session=True`：停止旧 sandbox session，再创建一个新的 session。
- 普通 timeout：保持现有语义，先向 executor 发送 `SIGINT`。
- Executor 未在 grace period 内结束：终止 namespace init，使整个 PID namespace 一起退出。
- `cleanup_session()` 可以重复调用，第二次调用应直接成功。

### 6.3 Cleanup 顺序

1. 停止接收新的代码执行请求。
2. 终止 executor 和 namespace init，并等待它们退出。
3. Private mount namespace 的最后一个进程退出后，其 mounts 由内核自动销毁；不在宿主执行模糊
   路径的全局 `umount`。
4. 确认 agent 已无存活进程后，恢复 workspace ownership。
5. 删除本次 sandbox runtime directory。
6. 释放临时 UID/GID 锁，关闭 queues。

`main_run._main()` 应使用 `try/finally` 确保 task/interpreter cleanup 在 solver 或 evaluation 抛异常时
仍然执行。可以增加 `atexit` 作为补充，但正常清理仍以显式 `finally` 为准。

如果主进程被强制杀死，private mount 会随 namespace 进程退出而消失，最多留下一个小的 runtime
directory 或 workspace 临时 owner。下一次启动只需根据 sandbox ID 和 workspace 路径做一次保守的
残留清理；不使用 `pkill -u`、通配符 `umount` 或批量删除其他 runtime directory。

## 7. Sandbox runtime directory

建议使用可配置的本地临时目录，例如：

```text
/tmp/dojo-python-sandboxes/<sandbox-id>/
├── root/          chroot 的临时 mount point
├── passwd         sandbox 内使用的临时用户记录
├── group
└── state.json     本次 sandbox 的 PID、UID 和 workspace 路径
```

它不是 agent workspace，也不会保存模型或实验结果。它只服务于隔离实现：

- `chroot()` 和 mount 需要真实目录作为挂载点；
- 锁文件用于多个 runner 进程之间分配临时 UID；
- 少量状态帮助 cleanup 找到本次 sandbox 的精确目标。

`root/` 只是挂载入口，不是复制出来的一份宿主文件系统。Runtime parent directory 应为 root/supervisor
专用的 `0700` 目录，每个 sandbox 使用随机唯一 ID。退出后删除本次子目录。

路径不必固定为 `/tmp`。若当前部署允许，也可以使用 `/run/dojo-python-sandboxes`。要求仅是：

- 位于本机文件系统；
- 不在 agent workspace 中；
- agent 无写权限；
- 不与其他用户的 runtime directory 混用。

## 8. 配置与代码改动

### 8.1 新配置

新增 `ChrootPythonInterpreterConfig(PythonInterpreterConfig)`，只保留直接需要的字段：

```python
@dataclass
class ChrootPythonInterpreterConfig(PythonInterpreterConfig):
    runtime_base_dir: str = "/tmp/dojo-python-sandboxes"
    allowed_working_root: str | None = None
    uid_min: int = 200000
    uid_max: int = 299999
    private_tmp: bool = True
```

新增 `src/dojo/configs/interpreter/chroot_python.yaml`，由实验显式选择：

```bash
python -m dojo.main_run ... interpreter=chroot_python
```

不改变现有 `interpreter=python` 的行为，便于单独调试和回退。

### 8.2 文件改动建议

| 文件 | 改动 |
| --- | --- |
| `src/dojo/core/interpreters/python.py` | 抽取 session loop；收紧 file path；完善 queue/process cleanup |
| `src/dojo/core/interpreters/chroot_python.py` | 新 interpreter 和 supervisor 生命周期 |
| `src/dojo/core/interpreters/linux_sandbox.py` | namespace、mountinfo、UID lock、降权和 cleanup 小工具 |
| `src/dojo/config_dataclasses/interpreter/chroot_python.py` | 配置和路径校验 |
| `src/dojo/config_dataclasses/interpreter/__init__.py` | 注册新 interpreter factory |
| `src/dojo/configs/interpreter/chroot_python.yaml` | Hydra 配置入口 |
| `src/dojo/main_run.py` | 用 `try/finally` 保证 cleanup |
| `tests/test_chroot_python_interpreter.py` | 必要的隔离、进程清理和并发测试 |
| `src/mle_critic/scripts/check_isolation.sh` | 使用唯一临时目录和 `trap`，只测试本方案需要的 namespace/chroot 能力 |

低层代码保持小而直接：所有 mount 命令使用参数数组，不拼 shell 字符串；所有路径先 resolve 和边界
检查；任一步骤失败都不进入 agent code。

## 9. 实施步骤

### Phase 1：整理现有 interpreter 生命周期

- 抽取可复用的 Python session loop，保持现有行为不变。
- 给 `file_name`、`fetch_file()` 增加 workspace 边界检查。
- 给 `main_run._main()` 增加 `try/finally` cleanup。
- 让 queues 和 `cleanup_session()` 可以可靠、重复地关闭。

### Phase 2：实现最小 sandbox

- 新增 `ChrootPythonInterpreterConfig` 和显式 Hydra 配置。
- 实现 runtime directory、临时数字 UID/GID 和锁。
- 实现 mount/PID namespace、只读根、可写 workspace、chroot 和降权。
- 实现 namespace init 和统一子进程清理。

### Phase 3：验证真实科研任务

- 验证 Conda imports、subprocess、NumPy/pandas/sklearn 和 PyTorch。
- 验证 data 可读不可写、workspace 正常写文件。
- 跑一个短 MLE-bench agent，确认 submission、checkpoint 和 cache 都落在 workspace。
- 与其他普通 Python interpreter 任务并发运行，确认 mount 和 cleanup 互不影响。

## 10. 测试计划

### 10.1 普通单元测试

- 危险 working directory 和路径穿越被拒绝。
- Mountinfo parser 能识别意外 writable mount。
- 临时 UID lock 并发分配不冲突。
- Cleanup 每一步重复执行不报错。
- 原 `PythonInterpreter` 的 persistent globals、traceback 和 timeout 不回归。

### 10.2 隔离 integration test

测试只使用唯一临时目录，并放在自己的 namespace 中：

1. Workspace 内创建、修改和删除文件成功。
2. Workspace 外准备一个 mode `0666` 的 sentinel；agent 对其 write、unlink、rename 和 chmod 均失败。
3. Workspace 内创建指向外部 sentinel 的 symlink，写入仍失败。
4. Data directory 可读但不可写；Conda prefix 和 repo 可以 import 但不可修改。
5. Agent 报告非 root、无附加组、无 capabilities。
6. Agent 创建普通子进程、双重 fork 和 `setsid()` 后，cleanup 能全部回收。
7. Sandbox 启动前后，宿主 mount table 没有新增 mount。
8. 多个 sandbox 并发启动时，UID、runtime directory 和 cleanup 不交叉。

### 10.3 验收标准

- Workspace 外 sentinel 测试全部通过。
- Writable mount verifier 只报告 workspace 和明确的私有临时目录。
- Agent 的全部派生进程能在 reset、timeout 和正常退出时清理。
- 多个 sandbox 并发运行不会改变其他任务的 mount、文件 owner 或进程。
- 一个短 MLE-bench 任务可以读取数据并输出有效文件。

## 11. 最终方案摘要

最终实现保持以下简单边界：

```text
宿主 Python 主进程（可信、root）
  -> 创建本次 workspace
  -> 创建 private mount/PID namespace
  -> 宿主根只读映射
  -> workspace 单独可写映射
  -> chroot
  -> 切换临时低权限 UID/GID，清空 capabilities
  -> 执行现有 Python session loop
  -> 退出时销毁 namespace、恢复 workspace owner、删除 runtime directory
```

这个方案不追求完整容器功能，只建立科研实验真正需要的边界：agent 能运行、能读取依赖和数据、能写
自己的 workspace，但不能破坏 workspace 之外的宿主文件。实现重点是 mount 白名单验证、降权顺序、
子进程统一回收和精确 cleanup；其余资源管理功能不进入本次设计。

## 12. 实现记录（2026-07-30）

Phase 1 和 Phase 2 已完成，Spaceship Titanic 端到端验证已通过。实现保持
`interpreter=python` 不变；只有显式设置 `interpreter=chroot_python` 才会进入本节的 Linux sandbox。
这既方便逐步部署，也保留了在不具备所需 capabilities 的环境中回退到原 interpreter 的能力。

### 12.1 实际进程与文件系统结构

实际结构与第 6 节的目标一致，但 supervisor 使用 `multiprocessing` 的 `spawn` 而非直接从主进程
`fork`：主进程常已启动 logger/HTTP 线程，直接 fork 会触发 Python 3.12 的多线程 fork 风险。spawn
产生一个干净的 supervisor；后续 namespace init 和 executor 的 fork 都发生在单线程子进程中。

```text
可信主进程（root）
  -> spawn sandbox supervisor（设置 parent-death signal）
       -> private mount namespace：/ 的 recursive bind clone 只读
       -> private PID namespace 的 init（PID 1，chroot 到 clone）
            -> executor（数字 UID/GID、无 capability）
                 -> agent 及其训练/DataLoader/subprocess 子进程
```

具体挂载顺序为：先 unshare mount namespace 并将 `/` 设为 private；recursive bind `/` 到 runtime 的
`root/`；按 mountinfo 从深到浅将 clone 内每个 mount remount 为只读；将 workspace、私有 `/tmp` 和
`/run` 显式 bind 回可写；最后用新的、带 `nosuid,nodev,noexec` 的 procfs 覆盖 clone 的
`/proc`，再 chroot。procfs 本身必须是读写挂载：NVIDIA CUDA driver 在设备枚举时需要 procfs operation，
只读 procfs 会使 `cudaGetDeviceCount()` 返回 Error 304。它是 PID namespace 内的新 procfs，
而 executor 已失去 root UID、groups 与 capabilities；因此该例外不提供对宿主文件系统的写入能力。这样
`/data`、Conda prefix、仓库和任何独立 submount 都不会因为只 remount 顶层 `/` 而意外保持可写。

### 12.2 各文件的代码改动和原因

以下按实现依赖顺序说明每个文件的职责、具体改动和它解决的问题。

#### 12.2.1 配置入口：dataclass、Hydra group 与 factory

- `src/dojo/config_dataclasses/interpreter/chroot_python.py` 新增
  `ChrootPythonInterpreterConfig`，并继承已有
  `PythonInterpreterConfig`。因此代码执行协议、超时、工作目录和输出格式仍沿用
  Python interpreter；仅增加隔离所必需的五项参数：
  `runtime_base_dir`（sandbox 瞬态目录的父目录）、
  `allowed_working_root`（workspace 的可信边界）、
  `uid_min`/`uid_max`（临时低权限数字 UID/GID 池）和
  `private_tmp`（是否覆盖 `/tmp`、`/run`）。
  `validate()` 额外拒绝空 runtime 路径和无效 UID 范围。这样 Linux 特有行为不会默默改变
  普通 `interpreter=python` 的语义。

- `src/dojo/configs/interpreter/chroot_python.yaml` 新增显式 Hydra config group。
  默认使用 `/tmp/dojo-python-sandboxes`、UID/GID 200000–299999，且开启私有 tmp。
  使用者必须通过 `interpreter=chroot_python` 选择它；没有该 override 时仍是原来的
  interpreter。这是 opt-in 的关键：缺少 mount/chroot capability 的 Pod 会在选择该 config 后明确失败，
  而不是静默退化为没有隔离的 Python。

- `src/dojo/config_dataclasses/interpreter/__init__.py` 在
  `INTERPRETER_MAP` 中注册配置类到
  `ChrootPythonInterpreter` 的 lazy factory。此处保持 lazy import，避免普通运行在
  导入配置时加载 Linux syscall 模块；同时让现有 `build(..., INTERPRETER_MAP)` 管线不需要
  特判新 interpreter。

#### 12.2.2 Linux 安全基元：`src/dojo/core/interpreters/linux_sandbox.py`

- 该文件将所有 Linux 特定逻辑集中起来，而不是散落在 interpreter 的会话代码中。它用
  `ctypes` 对 `unshare(2)`、`mount(2)`、
  `umount2(2)` 和 `prctl(2)` 做带 errno 的薄封装；所有路径作为 syscall
  参数传入，不经 shell 拼接或命令解释。这使 mount 行为可测试，也避免由空格、引号或 shell expansion
  引入额外语义。

- `parse_mountinfo()` 解析 Linux 的 `/proc/self/mountinfo`，包括其中的
  八进制转义，并将 mount point、mount option、filesystem 类型保存为结构化记录。
  `remount_tree_readonly()` 不是只 remount clone 的顶层 `/`：它筛出 clone
  下的每一个 mount，按路径深度从深到浅执行 bind-remount read-only。这样 Conda prefix、仓库、
  `/data` 及宿主本来就独立挂载的子树不会因嵌套 mount 而保留写权限。
  在切换 root 前，`verify_writable_mounts()` 再读取 mount table，要求可写 mount 的目标
  恰好等于 allowlist 中的 workspace、私有 `/tmp`/`/run` 或新 PID namespace
  的 `/proc`；任何意外 rw 挂载都会令启动失败。`/proc` 是 CUDA 可用性的必要
  例外，而不是宿主目录 bind；executor 无 capabilities，只能修改少量自身进程相关的 procfs 状态。

- `SandboxRuntime` 创建 owner-only（0700）的 runtime base 及每次运行独占的
  `sandbox-*` 目录，目录内分开保存 root clone、私有可写 tmp/run 和极小的状态文件。
  `UidLease` 对 UID 范围内的锁文件采用 non-blocking `flock`；父进程在整个
  sandbox 生命周期持有 lease。因此并发 run 不会把不同 agent 置为同一个 UID，从而不会意外共享彼此
  workspace 中的文件权限。

- `validate_workspace_path()` 在任何 `chown` 前检查 workspace：必须是
  非 symlink 的 `workspace_agent`，不能是 `/`、runtime 或其祖先；若配置
  `allowed_working_root`，workspace 必须是其真子目录，且该 root 不得为
  `/`。`ensure_uniform_ownership_no_follow()` 和
  `chown_tree_no_follow()` 均用 `lstat`/`followlinks=False`
  遍历：前者拒绝混合 owner 与预存的非目录 hard link，后者绝不沿 symlink 递归。这是为了使运行前交出
  workspace、运行后还原 owner 的过程不会意外修改 workspace 之外的 inode。

- `close_fds_except()` 枚举 `/proc/self/fd`，仅保留标准输入输出错误和三条
  multiprocessing Queue 的读写端。否则父进程先前打开的可写宿主 FD 即使对应路径在 chroot 中为只读，
  agent 也可直接写入。`drop_privileges()` 依次清空 supplementary groups、从 capability
  bounding set 删除 capability、将 real/effective/saved GID 与 UID 都切到租用数字 ID，最后设置
  `no_new_privs`；切换后 executor 不能借 setuid file 或保留 capability 回到 root。
  `set_parent_death_signal()` 还在设置信号后复查父 PID，消除“父进程恰在调用间死亡”的竞态。

#### 12.2.3 沙盒生命周期：`src/dojo/core/interpreters/chroot_python.py`

- `ChrootPythonInterpreter.__init__()` 只接受 Linux、`/proc/self/mountinfo`
  存在且启动者为 root 的场景。它首先调用 workspace 校验，随后拒绝仓库本身及其祖先作为 workspace、
  拒绝 workspace 与只读 data directory 重叠；当 `private_tmp=True` 时，还拒绝
  `/tmp`/`/run` 下的 workspace，因为这两个路径稍后会被私有挂载覆盖。
  它缓存 workspace 的 `(st_dev, st_ino)`，并在真正启动前再次比对，防止验证后被替换成
  symlink 或另一个目录的 TOCTOU。

- `create_process()` 保存原始 owner，取得 UID lease，建立 runtime，然后确认现有
  workspace 的 owner 一致、以不跟随链接的方式把整棵树交给临时 UID。若不使用私有 tmp，则只在
  workspace 内建立 `.tmp`。任一步失败都会调用
  `_cleanup_sandbox_resources()` 归还 owner、runtime 与 UID lock，避免半初始化状态。

- supervisor 使用 `multiprocessing.get_context("spawn")` 启动，而不是从可能已有 logger、
  HTTP client 等后台线程的主进程直接 fork。这样 supervisor 是干净的单线程 Python 进程；后续的
  `fork()` 仅发生在此进程或 PID namespace init 中，规避 Python 3.12 对多线程 fork 的
  风险。序列化钩子 `__getstate__()` 会清除 logger、process、Queue 和父进程资源，确保
  spawn 子进程只接收可安全重建的 executor 状态。

- `_sandbox_supervisor()` 设置 parent-death signal 后，先创建私有 mount namespace，
  将 `/` 设为 recursive private，recursive bind clone 到 runtime/root 并将 clone
  全部只读。之后仅将真正的 workspace bind 回可写；若启用私有 tmp，则另将 runtime 中的新
  `tmp`、`run` bind 到 clone 的同名位置。它还生成只含 sandbox 数字用户的
  最小 `passwd`/`group` 文件，并以只读 bind 覆盖 clone 的
  `/etc/passwd` 和 `/etc/group`。所有会失败的 mount 工作都在进入 PID
  namespace 前完成，以便错误仍可经 multiprocessing Queue 回传给可信主进程。

- supervisor 随后 unshare PID namespace 并 fork 出其 PID 1。
  `_namespace_init()` 先卸下 clone 中继承的 proc mount，在新 PID namespace 挂载带
  `nosuid,nodev,noexec` 的 procfs，并将这个唯一的 proc mount 精确加入可写 allowlist；
  之后才 `chroot()`。CUDA driver 的设备发现需要该 procfs 可写，读写 host clone 则仍被禁止。
  因此 agent 看到的是 namespace 内的进程视图，而不是继承的宿主 procfs。
  PID 1 fork executor，executor 把 `HOME`、`XDG_CACHE_HOME` 指向
  workspace，把 `TMPDIR`/`TMP`/`TEMP` 指向私有
  `/tmp`（或 workspace/.tmp），关闭继承 FD、降权后复用原有
  `PythonInterpreter._run_session()` 协议。executor 会在进入会话前把从 PID 1 继承的
  SIGINT/SIGTERM/SIGHUP 转发 handler 恢复为默认处理，确保空闲会话收到终止信号时会立刻退出，而非等到
  PID 1 的强杀升级。

- PID 1 对 SIGINT/SIGTERM/SIGHUP 转发给 executor，持续 `waitpid(-1)` 回收所有子进程。
  终止后先给 descendants SIGTERM、短暂 reap、再 SIGKILL，因而双重 fork、`setsid()` 等
  脱离普通 process group 的 agent 子进程也不能留在 namespace 内。supervisor 和 PID 1 都设置
  parent-death signal；可信主进程异常退出时，链条仍会杀掉 agent 并尝试恢复 workspace owner。
  `cleanup_session()` 无论普通 interpreter cleanup 成功与否，都会在 finally 中删除
  runtime、释放 UID lease、恢复原 owner。

- chroot 版本将 `cleanup_grace_seconds` 设为 5 秒，普通 Python interpreter 保持 2 秒。
  多出的时间用于 PID 1 转发 SIGTERM、回收 descendants，以及 supervisor 完成 owner 恢复；它避免正常的
  sandbox 级 shutdown 被过早升级成强杀。

#### 12.2.4 通用 Python interpreter 的收口：`src/dojo/core/interpreters/python.py`

- 新增 `resolve_workspace_path()`。agent 提供的 `file_name` 必须相对，
  不能含 `..`；解析后的真实路径还必须严格位于 workspace 内。会话循环写入、设置
  `__file__`、删除临时 agent 文件都统一使用该解析结果。这样普通 Python interpreter
  不会成为绕开 workspace 约束的较弱入口，chroot executor 复用它时也得到同一规则。

- `fetch_file()` 也改用这个 resolver，只返回 workspace 内的普通文件，不再按调用者给出的
  任意绝对路径取结果。这样任务侧获取 submission 或 artifact 时不能被 agent 诱导读取 workspace 外的
  文件。

- Queue 字段改为显式可空，`_close_queues()` 支持重复调用，并执行
  `cancel_join_thread()`、`close()` 和 `join_thread()`。
  process 创建前和 cleanup 后都会运行它，避免已退出 child 遗留的 Queue feeder 让父进程 cleanup
  卡住。cleanup 的 join 超时也从硬编码 2 秒改为类属性，以便 chroot 子类覆盖为 5 秒。

#### 12.2.5 顶层异常路径：`src/dojo/main_run.py`

`_main()` 现在把 task 创建、interpreter 创建、prepare、solver 和最终评估置于
`try/finally`。finally 中优先调用 `task.close(state)`，因为 task 最清楚
workspace 和 evaluator 的正常清理顺序；若 prepare 前便失败、尚无 state，则直接调用
`solver_interpreter.cleanup_session()`。最外层 finally 始终停止 logger。这样 LLM、
数据准备、评测或 solver 抛异常时，不会跳过 chroot 的进程终止、owner 恢复和 runtime 删除。

#### 12.2.6 运维诊断与回归测试

- `src/mle_critic/scripts/check_isolation.sh` 的 namespace probe 改为测试本实现实际所需的
  mount + PID namespace，不再把 user namespace 当作前提；chroot probe 使用每次 `mktemp`
  创建的目录，并以 `trap` 清理。脚本不再写死共享的
  `/tmp/chroot_test_dir`，避免多个用户/多次诊断互相覆盖。

- `tests/test_linux_sandbox.py` 覆盖 mountinfo 的 rw 识别及转义路径解析，验证 workspace
  必须为专属名称、不能是 symlink、allowlist 不能宽到 `/`，并验证两个并发 UID lease
  必然取得不同 UID、耗尽范围时明确报错。这些是无需特权即可快速回归的基础安全不变量。

- `tests/test_python_interpreter.py` 在原有 persistent globals、traceback 等 REPL 语义测试上，
  新增 `../escape.py` 与绝对 `file_name` 的拒绝用例，以及
  `fetch_file()` 对 workspace 内外路径的区分。它保证为 chroot 加的公共路径规则不会破坏
  原 interpreter 的会话契约。

- `tests/test_chroot_python_interpreter.py` 是需要 root、
  CAP_SYS_ADMIN 与 CAP_SYS_CHROOT 的集成测试。它实际创建 sandbox，验证：workspace 可写；外部 0666
  sentinel、指向外部文件的 workspace symlink 及继承的宿主可写 FD 都不能写；data 可正常读取；
  executor 的 UID、groups 与 effective capabilities 已降为预期值；NumPy、pandas、scikit-learn、
  PyTorch/CUDA、subprocess 可正常使用，其中 chroot 内 `torch.cuda.is_available()` 必须与
  宿主可见性一致；包含 `setsid()` 的双重 fork 后台子进程会在 cleanup
  后消失；宿主 mount table 与每次运行的 `sandbox-*` runtime 目录不会残留。该测试同时覆盖“能运行研究代码”与“退出后不污染
  Pod”的两个目标。

### 12.3 明确的安全边界和操作约束

- 启动端必须是 root，并具备 `CAP_SYS_ADMIN`、`CAP_SYS_CHROOT`、`SETUID`、`SETGID`；不满足时 sandbox 不会降级为不安全模式，而会在启动时失败。
- `allowed_working_root` 应设为本次 run 的 output directory 或其可信父目录。它不能是 `/`；workspace 必须叫 `workspace_agent`，并且是该 root 下的子目录。
- 本实现刻意不管理网络、CPU、内存或 GPU 用量；它不是 cgroup/network sandbox。共享 Pod 上应继续通过上层调度或 `CUDA_VISIBLE_DEVICES` 分配 GPU。
- agent 可读取 chroot 内可见且 POSIX permission 允许读取的宿主内容。因此该方案保证“不能修改 workspace 外文件”，不把它表述为保密数据隔离。
- 为兼容 NVIDIA CUDA，新 PID namespace 的 `/proc` 是唯一不只读的非 workspace mount；它不是宿主
  `/proc` 的 bind，且 executor 已移除 root UID、附加组与 capabilities。agent 因而可调整少数自身
  进程状态，但不能将该 procfs 例外变成宿主文件系统写权限。
- 正常退出和 parent-death 路径会恢复 workspace owner。若整个 Pod/内核强制 SIGKILL 所有进程，私有 mounts 会随进程消失，但 runtime 中可能留下很小的状态/锁文件；它们不包含 agent 工作结果，后续可保守清理。

### 12.4 验证结论

此前的 Spaceship Titanic 直接 interpreter 端到端验证已通过。批量验证现改用
`main_runner_job_array` 与单 worker 的 `local_gpu_pool`；其 Hydra 展开、源码 snapshot、
manifest 创建、GPU UUID 注入和 worker 启动均已验证。完整 pool run 必须只在独占空闲 GPU 上进行：最近一次启动时
8 张 Pod 可见 GPU 均已被其他用户占用，controller 已按 SIGTERM 路径将自己的 attempt 标记为
`cancelled`，没有继续竞争设备。因此本节不把该已取消 attempt 表述为完整 Spaceship pool 验证通过；
待有空闲设备后直接运行 12.5 的命令即可完成该最终验证。

### 12.5 可复现的 Spaceship Titanic demo 命令

本验证改用 `python -m dojo.main_runner_job_array`；它会先固定当前源码 snapshot、展开
`RunnerConfig`，再交给 `local_gpu_pool` 启动独立 worker。pool controller 为每个
worker 按 GPU UUID 写入 `CUDA_VISIBLE_DEVICES`、保存 manifest、attempt stdout/stderr 和
result JSON，并在 worker 完成后汇总状态。
以下命令适用于当前具备上述 capabilities、已准备 MLE-bench 数据、并在 `.env` 中配置有效 LLM key 的 Pod。
它是单 seed、单 GPU 的完整 pool smoke run；

```bash
python -m dojo.main_runner_job_array \
  +_exp=runner_example \
  'benchmark.tasks=[spaceship-titanic]' \
  'vars={metadata.seed:[42]}' \
  interpreter=chroot_python \
  'solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash' \
  'solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash' \
  metadata.git_issue_id=chroot-local-gpu-pool-spaceship \
  launcher=local_gpu_pool \
  '~launcher.qos' \
  launcher.gpus_per_task=1 \
  launcher.max_parallel=1 \
  launcher.max_retries=0 \
  launcher.debug=false \
  solver.step_limit=5 \
  logger.use_wandb=false
```

### 12.6 端到端运行后补充修复（2026-07-30）

`local_gpu_pool` 的真实 agent 日志进一步暴露了三项仅靠基础隔离测试没有覆盖的兼容问题，现已补齐：

- MLE-bench prompt 明确承诺 `/home/instructions.txt` 存在；数据的正式约定是 `./data`，但部分
  生成代码仍会沿用传统容器路径 `/home/data/*.csv`。sandbox 现在在 private mount namespace 中用
  只读 tmpfs 构造一个极小的
  `/home`，把真实 data directory 只读 bind 到 `/home/data`，并生成说明文件。该操作不会在共享宿主
  `/home` 中创建文件；workspace 中原有的 `./data` symlink 仍然可用。
- 当前 Pod 有 `libnvidia-opencl.so.1` 和匹配的 `libnvidia-nvvm.so.4`，但没有
  `/etc/OpenCL/vendors/nvidia.icd`。这不是 chroot 的必然要求，而是当前 K8s 驱动注入方式的兼容
  问题；默认 interpreter 不修改 OpenCL 环境。需要 LightGBM `device="gpu"` 时，可应用
  `src/mle_critic/patches/chroot_nvidia_opencl_runtime.patch`，在 workspace 中提供 NVIDIA ICD 并运行
  真实 OpenCL 训练测试。
- launcher 会继承提交者的 `XDG_CONFIG_HOME`、`XDG_DATA_HOME` 等绝对路径；只改 `HOME` 仍会让
  Matplotlib、Hugging Face、Torch、Numba、pip 和 Conda 尝试写宿主 cache。executor 现在把这些
  cache/config/package 目录统一指向 workspace，并设置 workspace-local Python user site；额外 pip
  package 因而可以安装到本次 agent 的 `.local`，Conda 的 package/env cache 也不会写共享 prefix。
  这里继续采用黑名单式兼容策略：父环境仍会继承，只覆盖已经确认会产生写入的变量。只读 mount 仍能
  阻止遗漏变量修改 workspace 外文件，但新的库若使用未覆盖的 cache/config 环境变量，仍可能出现
  `PermissionError`，应根据真实日志补充映射。该策略不等价于环境变量或凭据隔离。

默认集成断言同时验证 `/home/data` 可读不可写、`/home` 不可写、workspace user-site 可 import、
所有 cache 路径可写，以及宿主 mount table 和 workspace 外 sentinel 保持不变。OpenCL 训练断言仅由
上述可选 patch 增加。

### 12.7 PyTorch DataLoader 与 `/dev/shm`（2026-07-31）

Dog Breed Identification 的多 seed 真实任务稳定复现了
`multiprocessing.SemLock: OSError [Errno 30] Read-only file system`。Python 的 POSIX semaphore、
`multiprocessing.Queue`、`multiprocessing.shared_memory` 及 PyTorch 多 worker `DataLoader` 都依赖
`/dev/shm`；早期实现将 recursive bind clone 的全部 submount 设为只读，因此也错误地把克隆的宿主
`/dev/shm` 变成了只读。

sandbox 现在不会重新开放宿主 `/dev/shm`，而是在 private mount namespace 中将一个新的 tmpfs 精确
挂载到 clone 的 `/dev/shm`。该 tmpfs 使用 `mode=1777,nosuid,nodev,noexec`，容量沿用宿主
`/dev/shm` 的上限，并作为一个精确路径加入 writable mount allowlist。不同 sandbox 不共享 POSIX IPC
对象；namespace 最后一个进程退出后内容自动销毁。集成测试会实际创建 `multiprocessing.Queue`、运行
`DataLoader(num_workers=2)`，并确认 sandbox 的 shm marker 在宿主 `/dev/shm` 中不可见。

修复 `SemLock` 后，PyTorch tensor storage 的 worker-to-parent 传递还会使用
`multiprocessing.resource_sharer` 的 AF_UNIX socket。spawn supervisor 可能从可信父进程复制已经缓存的
`multiprocessing` resource-tracker FD 和临时目录；前者会被 executor 的 FD 清理关闭，后者可能位于
chroot 外或位于不支持 Unix socket 的共享文件系统。因此 executor 会同时清除这两类继承缓存，让
resource tracker 在降权后的 PID namespace 内重新启动，并把 resource-sharer 的小型控制目录固定到
private `/dev/shm/dojo-multiprocessing`。普通 `TMPDIR` 不变，训练过程的一般临时文件不会因此占用 shm。

### 12.8 `spawn` 与动态 `__main__` 的 pickle 语义（2026-07-31）

修复 IPC mount 后，Dog Breed Identification 的 8 个 seed 都进一步运行到 DataLoader worker 启动，
随后稳定报错 `Can't pickle <class '__main__.DogDataset'>: attribute lookup DogDataset on __main__ failed`。
这不是 chroot 文件可见性问题：chroot supervisor 由 multiprocessing `spawn` 创建，而该 start method
会被 executor 继承；DataLoader 因此需要 pickle 用户定义的 Dataset，并在 worker 中重新加载主脚本。

原 `PythonInterpreter` 只给一个普通 `exec()` globals dict 设置了 `__name__="__main__"`，但该 dict
并不是真正的 `sys.modules["__main__"].__dict__`。pickle 按模块名回查 `DogDataset` 时实际看到的是
Dojo/pytest launcher 的主模块，自然无法找到同一个类。executor 现在为 agent session 建立真实的
`ModuleType("__main__")`，同时维护 multiprocessing 约定的 `__mp_main__` alias，再用该模块的 dict
执行代码。这样带标准 `if __name__ == "__main__"` guard 的完整 solution script 可以由 spawn worker
安全重新加载；测试会实际通过 spawn 往返一个用户定义对象，并让 chroot DataLoader 使用定义在 agent
脚本中的自定义 Dataset，而不是只测试可 import 的 `TensorDataset`。
