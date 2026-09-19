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

## 12. 实现记录（2026-07-30 起，含后续修复）

Phase 1 和 Phase 2 已完成，Spaceship Titanic 端到端验证已通过。实现保持
`interpreter=python` 不变；只有显式设置 `interpreter=chroot_python` 才会进入本节的 Linux sandbox。
这既方便逐步部署，也保留了在不具备所需 capabilities 的环境中回退到原 interpreter 的能力。

下面按"原语 → 结构 → runtime 目录 → private tmp → 一次运行的过程 → 文件改动 → 安全边界 →
踩过的坑 → 验证"组织。代码位置写成 `chroot_python.py:288` 时指的是
`src/dojo/core/interpreters/chroot_python.py:288`，`linux_sandbox.py` 同理。

### 12.1 先补概念：这份实现用到的 Linux 原语

这一节只讲后面读代码需要的部分。每条的写法是：它是什么、在这里干什么、代码在哪。

**系统调用与 ctypes（`linux_sandbox.py:17-89`）**

`mount`、`umount2`、`unshare`、`prctl` 都是内核系统调用，glibc 提供了同名 C 函数；Python 标准库
只封装了其中一小部分（`os.chroot`、`os.setuid` 有，3.12 起还有 `os.unshare`，但
`mount`/`umount2`/`prctl` 一直没有）。`ctypes` 是 Python 调 C 函数的通用入口：

- `ctypes.CDLL(None)` 打开的是"当前进程自己"，在 Linux 上等于拿到 libc 的符号表，
  于是 `_libc.mount(...)` 就是调 libc 的 `mount()`。
- `use_errno=True` 配合 `ctypes.get_errno()`：出错后读 `errno`，像 C 一样拿到 `EROFS`、`EPERM`
  这种具体原因，再由 `_check_syscall()` 包成 Python 异常。
- `argtypes`/`restype` 是显式的参数和返回类型声明。不声明的话 ctypes 会把 Python int 当 C int
  传，指针或长整型参数在 64 位平台上就会出错。

不用 `subprocess` 跑 `mount` 命令的原因：路径作为 syscall 参数原样传入，不经过 shell 解释空格、
引号和通配符；每个失败点都带 errno 和确切的操作名；也不依赖镜像里装了 util-linux 的 `mount`。
（namespace 是进程属性，子进程执行命令时仍在同一张挂载表里，所以"必须用 syscall"不是硬限制，
主要是可控性和错误信息。）

**mount 和 bind mount（`linux_sandbox.py:65-81, 142-157`）**

`mount(source, target, fstype, flags, data)` 把 source 上的文件系统挂到 target 上。target 叫挂载点，
必须是已存在的目录（或文件）；挂上之后 target 目录原本的内容被遮住（没有被删除），umount 之后
重新露出来。

bind mount 是 `fstype = NULL` 的特例：source 不是设备而是另一个目录，效果是"把那个目录原样接到
target 上"。本方案"给 agent 一份同路径的宿主文件系统视图"就是一次
`mount("/", runtime/root, MS_BIND | MS_REC)`（`chroot_python.py:288`），**不复制任何文件**。

用到的 flag：

| flag | 含义 |
| --- | --- |
| `MS_BIND` | 这次挂载是 bind mount |
| `MS_REC` | 递归，把 source 下已有的子挂载（`/data`、`/dev`、`/proc` 等）也一起接过去 |
| `MS_REMOUNT` | 改一条已存在挂载的属性，而不是新建挂载 |
| `MS_RDONLY` | 只读 |
| `MS_NOSUID` / `MS_NODEV` / `MS_NOEXEC` | 忽略 setuid/setgid 位 / 不允许访问设备节点 / 不允许执行 |
| `MS_PRIVATE` | 这条挂载的传播属性，见下一段 |

两个容易踩的点：

1. 每条挂载有自己独立的属性。把 `/` 设成只读**不会**连带把 `/data` 这个子挂载设成只读，所以
   代码要遍历整张挂载表逐条处理（`remount_tree_readonly()`）。顺序是先深后浅，但每条挂载都是
   独立对象，先处理哪条不影响结果。
2. 改一条已有挂载的属性要用 bind 技巧。单独 `mount(NULL, target, MS_REMOUNT | MS_RDONLY)` 改的是
   底层文件系统（superblock，宿主和其他 namespace 共用），会把宿主一起改成只读；
   `MS_BIND | MS_REMOUNT` 只改本次 namespace 里这一个挂载点自己的属性。`bind_mount()` 就是这个
   两步：先 `MS_BIND[|MS_REC]` 建立新挂载，再 `MS_BIND | MS_REMOUNT[|MS_RDONLY]` 设属性。

**mount namespace（`chroot_python.py:286-288`）**

`unshare(CLONE_NEWNS)` 把当前进程的挂载表复制一份；此后这个进程和它 fork 出来的孩子看到的挂载表
与宿主其他进程无关，改动只影响自己。复制之后还要 `mount(NULL, "/", MS_REC | MS_PRIVATE)`：默认的
挂载带 propagation 属性，mount/umount 事件会沿父子关系传播，标成 private 才彻底和宿主断开。

为什么必须有它：同一个 Pod 上有别的用户和任务，直接在宿主挂载表上把 `/` 改成只读会把所有人一起
搞坏。

生命周期：namespace 里最后一个进程退出后，内核把它挂载表里的所有挂载销毁。所以这些挂载不需要、
也不应该在宿主上手动 umount（`umount()` 只在 PID 1 替换 `/proc` 时用过一次）。

**chroot（`chroot_python.py:84-85`）**

`chroot(dir)` 把当前进程的 `/` 换到 dir，之后所有绝对路径都从 dir 开始解析。两个要点：

- chroot 只改"路径怎么解析"，**不提供写保护，也不复制文件**。写保护来自只读 mount，进程回收来自
  PID namespace，降权来自 setuid/setgroups/prctl，四件事是分开做的。
- chroot 本身不是安全边界：进程自己保留的 cwd 和已经打开的目录 fd 仍然能走到新根之外。所以代码在
  chroot 之后立刻 `chdir("/")`，并在降权前用 `close_fds_except()` 关掉除 stdio 和 Queue 之外的
  所有继承 fd。

为什么是"把整个 `/` bind 到同路径再 chroot"，而不是"只 bind 需要的几个目录"：Conda prefix、仓库
路径、`/data` 在代码里都是绝对路径（例如 `/data/public/.../miniconda3/envs/aira-dojo`），保持同路径
存在就不需要改 `PATH`、`sys.path` 或任何路径映射；`working_dir` 也一样，宿主和 sandbox 里是同一个
字符串，agent 写出的文件直接落在真实 workspace 里，事后不需要搬运。

**PID namespace（`chroot_python.py:53-57, 350-353`）**

`unshare(CLONE_NEWPID)` 有个反直觉点：**它不改变调用者自己，只影响之后 fork 出来的孩子**。所以代码
是先 unshare 再马上 fork，孩子就是新 namespace 里的 PID 1。

PID 1 在三件事上和其他进程不同，正好是这里需要的：

- 它退出时，内核把它这个 namespace 里剩下的所有进程一起杀掉，天然完成统一回收。
- namespace 内的孤儿进程会被重新挂到 PID 1 上，所以它必须持续 `waitpid` 回收，否则会积累僵尸。
- 内核不给 PID 1 应用信号的默认动作。它收到 SIGTERM 不会自己退出，必须显式装 handler 转发给
  executor（`forward_signal`）。

为什么不能只记下 pid 再 kill：agent 会 fork、double-fork、`setsid()`，进程会脱离进程组和父进程，
按 pid、进程组或进程名清理都会漏；按 UID 清理会误伤同一 Pod 上其他用户。`_kill_namespace_descendants()`
里 `os.kill(-1, sig)` 的含义是"给我在这个 namespace 里能看到的每个进程发信号"，namespace 外的进程
根本不在它的视野里，所以这个"广播"是安全的。

**prctl：三个进程开关（`linux_sandbox.py:320-336`）**

`prctl(2)` 是"杂项进程属性"的系统调用，这里用了三个选项：

- `PR_SET_PDEATHSIG`：父进程死的时候给我发信号。它是"主进程被强杀时不留野进程"的兜底。
  设置完要复查一次 `getppid()`：检查和设置之间存在竞态，父进程可能刚好在这中间死了。注意 PID 1
  的父进程在新 namespace 之外，它看到的 `getppid()` 是 0，所以判断写成 `not in (0, parent_pid)`。
- `PR_CAPBSET_DROP`：从 capability bounding set 里删掉一个 capability。只 setuid 是不够的：宿主 `/`
  本身是只读可见的，里面有 setuid-root 程序（`/bin/su`、`/usr/bin/passwd` 之类），也有带 file
  capability 的程序，执行它们就可能把 root 权限拿回来。清空 bounding set 之后这些程序拿不到
  capability。
- `PR_SET_NO_NEW_PRIVS`：保证 exec 不带来任何新权限（setuid 位、file capability 全部失效）。

`drop_privileges()` 的顺序不能乱，每一步都依赖上一步还没丢掉的权限：

1. `setgroups([])` 清空附加组（必须是 root 才能调）。
2. 逐个 `PR_CAPBSET_DROP` 清空 capability 上限。
3. `setresgid`/`setresuid` 把 real/effective/saved 三个 ID 一起切成租用的数字 ID。只改 effective
   的话进程随时能 `setuid` 回 root。
4. `PR_SET_NO_NEW_PRIVS` 收尾。

**`/proc/self/mountinfo` 和 tmpfs（`linux_sandbox.py:92-169`）**

mountinfo 是内核给出的当前 namespace 的挂载表，一行一条挂载，字段包含 mount id、父 id、挂载点、
挂载选项（`rw`/`ro`）和文件系统类型。路径里的空格、制表符、换行、反斜杠被转义成八进制写法
（`\040` 是空格），所以 `parse_mountinfo()` 要解码。代码用它做两件事：找出 clone 里所有挂载并逐条
设成只读；装完之后复核"还有没有意外的可写挂载"（`verify_writable_mounts()`）。后者是自我检查：
任何没有被白名单**精确**覆盖的可写挂载都会让启动直接失败，而不是安静地留个洞。

tmpfs 是内容放在内存/swap 的文件系统，不落地磁盘。这里用它造三种"全新的一块地盘"：sandbox 私有的
`/home`（1MB，放说明文件和 `/home/data`）、`/dev/shm`（给 PyTorch DataLoader 和 multiprocessing
用），以及新 PID namespace 里的 `/proc`。tmpfs 的内容在最后一个引用它的挂载消失时丢掉。

**flock 和数字 UID 租约（`linux_sandbox.py:188-227`）**

不用 `useradd/userdel`：改 `/etc/passwd` 是全局共享状态，并发会冲突，异常退出还会留下垃圾用户。
直接用一个数字 UID（默认池 200000–299999，UID 和 GID 取同一个值）。唯一需要协调的是"两个并发
sandbox 不要选到同一个号"，用 `flock` 就够了：对 `runtime_base_dir/uid-locks/<uid>.lock` 做非阻塞
排他锁，抢到就归自己用，进程死掉内核自动释放。父进程在整个 sandbox 生命周期持有这个 fd；它带
`O_CLOEXEC`，所以 spawn 出来的子进程不会继承。

### 12.2 整体结构和文件系统视图

进程树（带权限标注）：

```text
可信主进程（root，有 CAP_SYS_ADMIN / CAP_SYS_CHROOT）
  └─ spawn: sandbox supervisor（root；单线程；持有 UID 锁；PDEATHSIG=SIGTERM）
       ├─ 私有 mount namespace（自己的挂载表）
       └─ unshare(CLONE_NEWPID) + fork
            └─ namespace init（新 namespace 的 PID 1；chroot 后是 root，但只转发信号和回收子进程）
                 └─ fork
                      └─ executor（数字 UID/GID 20 万+、无附加组、CapEff 为 0、no_new_privs）
                           └─ agent 代码、DataLoader worker、subprocess …
```

agent 看到的文件系统：

| 路径 | agent 视角 | 怎么做的 |
| --- | --- | --- |
| `/` 及其下所有目录 | 只读 | 宿主 `/` 的 recursive bind clone，逐条 remount 成只读 |
| `working_dir`（宿主同路径） | **可写** | 单独 bind 回可写，这是唯一持久可写的目录 |
| `/tmp`、`/run`（`private_tmp=True`） | 可写 | runtime 下新建的目录 bind 过去，见 12.4 |
| `/dev/shm` | 可写 | 新 tmpfs，容量取宿主 `/dev/shm` 的上限 |
| `/home` | 只读 | 1MB tmpfs，放 `/home/data`（真实 data 目录只读 bind）和 `instructions.txt` |
| `/etc/passwd`、`/etc/group` | 只读 | runtime 下生成的最小文件 |
| `/proc` | 可写 | 新 PID namespace 里的新 procfs，只包含本 namespace 的进程 |

磁盘上的实际布局（与第 7 节的草图略有出入，以下面这份代码产生的为准）：

```text
${runtime_base_dir}/                     默认 /tmp/dojo-python-sandboxes，0700 root
├── uid-locks/
│   └── 200000.lock …                    flock 锁文件，长期存在；文件存在 ≠ 号被占用
└── sandbox-XXXXXX/                      每次运行一个，退出时整个删掉
    ├── root/                            空目录，chroot 的挂载点（宿主 / bind 到它上面）
    ├── writable/
    │   ├── tmp/                         私有 /tmp 的落点（chown 给租用的 UID）
    │   └── run/                         私有 /run 的落点
    ├── passwd / group                   sandbox 内的假用户记录
    └── state.json                       workspace、uid、supervisor pid，供残留排查
```

`root/` 里没有文件。运行中它是宿主 `/` 的镜像（`du` 会跟着挂载点一路走进宿主文件系统），sandbox
退出、namespace 消失之后又变回空目录，所以创建和删除成本都接近 0。

### 12.3 runtime_base_dir：为什么要一个瞬态目录

这个目录不是工作区，也不是缓存，它只用来放"隔离机制需要、但既不能放进 agent 的 workspace、也不能
放进共享宿主目录"的东西。逐条对应上面的布局：

1. **mount 和 chroot 需要真实存在的目录当挂载点**。bind mount 的 target 必须存在，chroot 的目标
   也必须存在。它们不能建在 workspace 里：workspace 是 agent 可写的地方，挂载点被改名或删除就会
   把挂载变成悬空；何况把宿主 `/` 挂上去正好会盖住 workspace 自己。所以要在别处准备一个空目录，
   也就是 `sandbox-XXXX/root/`。
2. **它同时是 namespace 的"外壳"**。所有 mount 都发生在它之上，namespace 消失时挂载也一起消失。
   目录本身是一次性的：每次运行随机名字，退出时 `SandboxRuntime.cleanup()` 整个 `rmtree`
   （`chroot_python.py:535-545`）。这也是它不放在 repo 或数据目录里的原因——那里要求长期存在，
   而这里天生是垃圾。
3. **私有 `/tmp`、`/run` 需要真实可写的落点**（见 12.4）。它们必须落在宿主某个真实目录上，而那个
   目录绝不能是共享的宿主 `/tmp`，于是放在 `sandbox-XXXX/writable/{tmp,run}`，再 bind 到
   sandbox 内的 `/tmp`、`/run`。
4. **需要一小块 agent 摸不到、宿主 root 进程能用的小空间放元数据**：给 sandbox 用的假
   `passwd`/`group`（稍后只读 bind 到 `/etc/passwd`）、`state.json`（记录 workspace/uid/pid，
   出问题时用来判断残留），以及跨 run 协调 UID 的 `uid-locks/`。这些既不能放在 workspace（agent
   可写等于可改），也不能放在 `/etc`（不能污染宿主）。

约束在 `ensure_runtime_base()`（`linux_sandbox.py:172-185`）：必须是本机文件系统上的目录、权限
`0700`、owner 是启动者；目录已存在但不是 0700 或 owner 不符就直接报错。agent 从 clone 里也进不去，
因为 runtime_base 是 0700 且属于 root。

两个隐含代价值得知道：

- 私有 `/tmp` 落在 runtime_base_dir 所在的文件系统（默认就是 `/tmp`）上，agent 往 `/tmp` 写多少
  就占多少。本方案不做磁盘配额也不监控。
- `uid-locks/` 里的锁文件不会被删除（每个几十字节）。占用状态由 `flock` 表示，"文件存在"不代表号
  被占用。

### 12.4 private_tmp：为什么要私有 /tmp 和 /run

1. **不私有就会直接坏掉**。clone 之后宿主 `/tmp` 也是只读的，任何写 `/tmp` 的代码都直接拿到
   `EROFS`。写 `/tmp` 的库很多：matplotlib 的字体缓存、pip、torch、numba、`multiprocessing` 的
   临时目录，以及各种"先把结果 dump 到 /tmp"的脚本。
2. **不能简单把宿主 `/tmp` 重新挂成可写**。`/tmp` 是同一个 Pod 上所有用户共享的：agent 可以覆盖
   别人的临时文件、抢别人的文件名（symlink 攻击），也可以读到别人留在 `/tmp` 里的东西。
3. **做法**：在 runtime 里准备两个真实目录，chown 给本次租用的 UID，bind 到 sandbox 的 `/tmp` 和
   `/run` 并设成可写（`chroot_python.py:329-333`）。agent 写的 `/tmp` 是它自己的一份，namespace
   外看不到，退出时随 runtime 目录一起删掉。executor 里 `TMPDIR`/`TMP`/`TEMP` 也都指到 `/tmp`
   （`chroot_python.py:101-114`），代码写临时文件自然落到这里。
4. **为什么连 `/run` 一起**：同一个模式，不少程序会往 `/run`、`/var/run` 写 pid 文件、socket 和锁
   文件，不私有的话它们同样会撞上只读。
5. **workspace 不能位于 `/tmp` 或 `/run` 之下**：私有 `/tmp` 会盖在 clone 的 `/tmp` 上，正好把
   workspace 藏起来，所以配置校验直接拒绝这种组合（`chroot_python.py:410-414`）。
6. `private_tmp=False` 是留给调试的退路：不挂 `/tmp`、`/run`，executor 把 `TMPDIR` 指到
   `workspace/.tmp`，sandbox 里的 `/tmp` 仍然是宿主 `/tmp` 的只读副本。

### 12.5 一次 sandbox 启动的完整过程

**第 0 步：可信主进程的检查和准备（`chroot_python.py:398-510`）**

1. `__init__` 确认是 Linux、`/proc/self/mountinfo` 存在、`geteuid() == 0`。然后做路径校验
   （`linux_sandbox.py:258-284`）：workspace 必须是真目录（不是 symlink），目录名必须是
   `workspace_agent`，不能是 `/`、runtime 目录、仓库或其祖先，不能和只读 data 目录互相包含；配了
   `allowed_working_root` 时还必须是它的真子目录。通过后记下 `(st_dev, st_ino)` 作为身份指纹。
2. `create_process()` 先复核 workspace 还是那个 inode、还不是 symlink（从校验到启动之间可能被换
   掉，也就是 TOCTOU），再记录 workspace 原本的 owner。
3. 取一个 UID 租约，在 runtime_base 下建 `sandbox-XXXX/`，写 `state.json`。
4. `ensure_uniform_ownership_no_follow()` 拒绝 workspace 里预存的混合 owner 和 hard link（hard
   link 会让后面的 `chown` 改到 workspace 之外的 inode）；然后预建 `.cache`、`.config`、
   `.local`、`.conda` 等目录，最后把整棵 workspace 树 chown 给租用的 UID/GID——降权后的 executor
   就是靠这个数字 UID 写 workspace 的。
5. 用 `multiprocessing.get_context("spawn")` 起 supervisor，而不是直接 fork：主进程这时通常已经
   起了 logger、HTTP 线程，Python 3.12 里多线程 fork 会出问题（子进程可能卡死、锁状态被复制），
   spawn 出来的则是干净的、单线程的 Python 进程。三条 Queue 也由这个 context 创建，启动阶段的
   错误才有通道回传主进程。
   `__getstate__()` 会把 logger、process、Queue、runtime、UID 租约从序列化状态里清掉，保证 spawn
   的子进程只拿到能安全重建的 executor 状态。

**第 1 步：supervisor 构建文件系统视图（`chroot_python.py:282-345`）**

| 顺序 | 操作 | 代码 | 为什么 |
| --- | --- | --- | --- |
| 1 | `PDEATHSIG = SIGTERM` | 285 | 主进程异常退出时，supervisor 还能停下来恢复 owner |
| 2 | `unshare(CLONE_NEWNS)`，再把 `/` 设为 `MS_REC\|MS_PRIVATE` | 286-287 | 独立挂载表，且不让改动传播到宿主 |
| 3 | bind 宿主 `/` 到 `runtime/root` | 288 | 同路径的文件系统视图 |
| 4 | `/home`：1MB tmpfs + `/home/data` 只读 bind + 写 `instructions.txt` | 295-303 | MLE-bench 提示词里写的是 `/home/data` |
| 5 | `remount_tree_readonly(root)` | 304 | 逐条把 clone 里每个挂载设成只读 |
| 6 | workspace 按同路径 bind 回可写 | 307-309 | 唯一持久可写的目录 |
| 7 | `/dev/shm` 换成新的 tmpfs | 315-327 | 见 12.8.2 |
| 8 | `private_tmp`：把 `writable/{tmp,run}` bind 到 `/tmp`、`/run` | 329-333 | 见 12.4 |
| 9 | 生成 `passwd`/`group` 并只读 bind 到 `/etc/` | 335-343 | 让需要用户名的工具能用 |
| 10 | `verify_writable_mounts()` | 344 | 白名单复核：除 workspace/shm/tmp/run 外还有可写挂载就直接失败 |

这一步整体放在 PID namespace 之前：等所有可能失败的 mount 都做完再切 namespace，出错时还能通过
Queue 把失败原因送回主进程。顺序本身也是设计的一部分：`/home` 的 tmpfs 挂在第 5 步**之前**，
所以它随后被一起设成只读（这就是 `/home` 可读但不可写的来源）；workspace、`/dev/shm`、`/tmp`、
`/run` 都挂在第 5 步**之后**，所以它们保持可写。

**第 2 步：进入 PID namespace 并 chroot（`chroot_python.py:347-367, 60-89`）**

- `unshare(CLONE_NEWPID)` 之后立刻 `fork()`：父进程（supervisor）等结果，子进程成为新 namespace
  的 PID 1。
- PID 1 先 `umount` 掉 clone 里继承来的宿主 `/proc`，再挂一个新的 procfs。换掉它的原因：agent
  应该看到自己 namespace 的进程视图，而不是宿主全部进程；而 procfs 的内容由读它的进程所在的 PID
  namespace 决定，所以必须在进入新 namespace 之后重新挂载。
- 这个 procfs 是唯一非只读的例外，而且必须可写：NVIDIA 驱动枚举设备时会做 procfs 操作，只读
  procfs 会让 `cudaGetDeviceCount()` 返回 Error 304，从而 `torch.cuda.is_available()` 变成 False。
  它是 PID namespace 自己的新 procfs，不是宿主 `/proc` 的 bind，而 executor 已经没有 root UID、
  附加组和 capability，所以这个例外拿不到宿主文件系统的写权限。把它加进白名单后再复核一次。
- 最后 `chroot(root)` + `chdir("/")`，此后一切按新根解析。

**第 3 步：executor 降权运行 agent（`chroot_python.py:91-188`）**

1. 把 SIGINT/SIGTERM/SIGHUP 恢复成默认行为。不恢复的话会继承 PID 1 的转发 handler：空闲会话收到
   SIGTERM 只会把它转发给自己然后继续活着，直到被强杀。
2. `chdir(working_dir)`（宿主和 sandbox 同路径），把 `HOME`、`XDG_*`、`MPLCONFIGDIR`、`HF_HOME`、
   `TORCH_HOME`、`NUMBA_CACHE_DIR`、`PIP_CACHE_DIR`、`PYTHONUSERBASE`、`CONDA_PKGS_DIRS`、
   `CONDA_ENVS_PATH` 全部指到 workspace 或私有 `/tmp`，并打开 `PIP_USER=1`
   （`chroot_python.py:101-140`）。这些都是库会写文件的位置，不重定向就会撞上只读挂载。
3. `close_fds_except()` 只留 stdio 和三条 Queue，其余继承 fd 全关。否则主进程早些时候打开的宿主
   文件 fd 可以绕过只读挂载直接写；集成测试专门验证了这条。
4. 清掉 multiprocessing 继承下来的缓存：父进程的 resource-tracker fd/pid，以及缓存过的临时目录
   （见 12.8.2）。
5. `drop_privileges()`：附加组、capability、UID/GID 依次丢掉。
6. 把 multiprocessing 默认启动方式强制回 `fork`（`spawn` 是 supervisor 自己用的，不该泄漏给
   agent，见 12.8.3），然后调用原有的 `PythonInterpreter._run_session()`——会话协议、持久
   globals、traceback、timeout 全部复用，agent 看不出区别。

**第 4 步：退出和回收（`chroot_python.py:190-238, 372-387, 529-545`）**

- PID 1 平时阻塞在 `waitpid(-1)`：一边回收孤儿，一边等 executor。收到信号就转发；SIGTERM/SIGHUP
  之后 2 秒内没等到 executor，升级成 SIGKILL。
- executor 退出后，先给 namespace 内剩余进程 SIGTERM，短暂回收，再 SIGKILL，最后把还活着的全部
  `waitpid` 收干净。double-fork + `setsid()` 的后台进程也逃不掉。
- supervisor 等到 PID 1 退出，把 workspace 的 owner 交还原 owner，然后退出。
- 主进程侧 `cleanup_session()` 无论正常与否都会在 `finally` 里恢复 owner（幂等）、删除 runtime
  目录、释放 UID 锁。
- 主进程被强杀时，PDEATHSIG 让 supervisor 收到 SIGTERM，链条照走一遍；如果连 supervisor 都没机会
  跑完，私有挂载会随 namespace 消失，最多留下一个小 runtime 目录和一个临时 owner，下次按
  `state.json` 保守清理。

### 12.6 各文件的代码改动和原因

12.1 和 12.5 讲的是机制和流程，这一节按文件列出改动明细；两者对照看，代码里的每个
syscall 都能在前面找到它对应的概念。以下按实现依赖顺序说明每个文件的职责和它解决的问题。

#### 12.6.1 配置入口：dataclass、Hydra group 与 factory

- `src/dojo/config_dataclasses/interpreter/chroot_python.py` 新增
  `ChrootPythonInterpreterConfig`，并继承已有
  `PythonInterpreterConfig`。因此代码执行协议、超时、工作目录和输出格式仍沿用
  Python interpreter（并把 `startup_timeout` 从 10 秒改成 60 秒）；新增隔离所必需的五项参数：
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

#### 12.6.2 Linux 安全基元：`src/dojo/core/interpreters/linux_sandbox.py`

- 该文件将所有 Linux 特定逻辑集中起来，而不是散落在 interpreter 的会话代码中。它用
  `ctypes` 对 `unshare(2)`、`mount(2)`、
  `umount2(2)` 和 `prctl(2)` 做带 errno 的薄封装；所有路径作为 syscall
  参数传入，不经 shell 拼接或命令解释。这使 mount 行为可测试，也避免由空格、引号或 shell expansion
  引入额外语义。

- `parse_mountinfo()` 解析 Linux 的 `/proc/self/mountinfo`，包括其中的
  八进制转义，并将 mount point、mount option、filesystem 类型保存为结构化记录。
  `remount_tree_readonly()` 不是只 remount clone 的顶层 `/`：它筛出 clone
  下的每一个 mount，各自执行一次 bind-remount read-only。每一条挂载都是独立对象（把父挂载设成
  只读不会传给子挂载），所以必须逐条处理，Conda prefix、仓库、`/data` 及宿主本来就独立挂载的
  子树才不会保留写权限。
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

#### 12.6.3 沙盒生命周期：`src/dojo/core/interpreters/chroot_python.py`

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

#### 12.6.4 通用 Python interpreter 的收口：`src/dojo/core/interpreters/python.py`

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

#### 12.6.5 顶层异常路径：`src/dojo/main_run.py`

`_main()` 现在把 task 创建、interpreter 创建、prepare、solver 和最终评估置于
`try/finally`。finally 中优先调用 `task.close(state)`，因为 task 最清楚
workspace 和 evaluator 的正常清理顺序；若 prepare 前便失败、尚无 state，则直接调用
`solver_interpreter.cleanup_session()`。最外层 finally 始终停止 logger。这样 LLM、
数据准备、评测或 solver 抛异常时，不会跳过 chroot 的进程终止、owner 恢复和 runtime 删除。

#### 12.6.6 运维诊断与回归测试

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

### 12.7 明确的安全边界和操作约束

- 启动端必须是 root，并具备 `CAP_SYS_ADMIN`、`CAP_SYS_CHROOT`、`SETUID`、`SETGID`；不满足时 sandbox 不会降级为不安全模式，而会在启动时失败。
- `allowed_working_root` 应设为本次 run 的 output directory 或其可信父目录。它不能是 `/`；workspace 必须叫 `workspace_agent`，并且是该 root 下的子目录。
- 本实现刻意不管理网络、CPU、内存或 GPU 用量；它不是 cgroup/network sandbox。共享 Pod 上应继续通过上层调度或 `CUDA_VISIBLE_DEVICES` 分配 GPU。
- agent 可读取 chroot 内可见且 POSIX permission 允许读取的宿主内容。因此该方案保证“不能修改 workspace 外文件”，不把它表述为保密数据隔离。
- 为兼容 NVIDIA CUDA，新 PID namespace 的 `/proc` 是唯一不只读的非 workspace mount；它不是宿主
  `/proc` 的 bind，且 executor 已移除 root UID、附加组与 capabilities。agent 因而可调整少数自身
  进程状态，但不能将该 procfs 例外变成宿主文件系统写权限。
- 正常退出和 parent-death 路径会恢复 workspace owner。若整个 Pod/内核强制 SIGKILL 所有进程，私有 mounts 会随进程消失，但 runtime 中可能留下很小的状态/锁文件；它们不包含 agent 工作结果，后续可保守清理。
- 私有 `/tmp` 和 `/run` 用的是 `runtime_base_dir` 所在文件系统上的真实目录，不是 tmpfs（只有 `/dev/shm`、`/home` 和 `/proc` 是 tmpfs）。agent 在 `/tmp` 写的量会占这块盘，方案本身不做配额和监控。
- runtime_base_dir、UID 池和 workspace 路径都属于部署约定：同一台机器上的并发 run 必须用同一个 runtime_base_dir 才能通过 `uid-locks/` 协调。

### 12.8 端到端跑起来之后补的修复

真实 agent 跑起来之后暴露了几个基础隔离测试覆盖不到的兼容问题。每条按"症状 → 原因 → 修复"写。

**12.8.1 `/home` 路径、OpenCL 和 cache 环境变量（2026-07-30）**

症状：MLE-bench 的 prompt 承诺 `/home/instructions.txt` 存在，数据的正式约定是 workspace 下的
`./data`，但部分生成代码仍会写传统容器路径 `/home/data/*.csv`；需要 LightGBM `device="gpu"` 的
任务起不来；另外 Matplotlib、Hugging Face、Torch、Numba、pip、Conda 会尝试写宿主 cache。

原因：

- 同路径视图里的 `/home` 是宿主 `/home`，那是别人的目录，不能往里写东西。
- `/etc/OpenCL/vendors/nvidia.icd` 在当前 Pod 里不存在。这不是 chroot 的必然要求，而是当前 K8s
  驱动注入方式的兼容问题，跟隔离机制无关。
- launcher 会把提交者的 `XDG_CONFIG_HOME`、`XDG_DATA_HOME` 等绝对路径原样继承给 executor，只改
  `HOME` 挡不住这些库。

修复：

- supervisor 在私有 namespace 里用 1MB tmpfs 造一个极小的 `/home`，把真实 data 目录只读 bind 到
  `/home/data`，再写一个说明文件；它随后和其他挂载一起被设成只读（`chroot_python.py:295-303`）。
  宿主 `/home` 一个文件都不会被创建；workspace 里原有的 `./data` symlink 照常可用。
- OpenCL 默认不动。需要时应用 `src/mle_critic/patches/chroot_nvidia_opencl_runtime.patch`，在
  workspace 里提供 NVIDIA ICD 并跑真实的 OpenCL 训练测试。
- executor 把 cache/config/package 目录统一指向 workspace，并设置 workspace 内的 Python user
  site（`chroot_python.py:101-140`，见 12.5 第 3 步）。额外的 pip package 因此可以装进本次
  agent 的 `.local`，Conda 的 package/env cache 也不会写共享 prefix。这是**黑名单式**兼容：父
  环境其他变量仍然继承，只覆盖已经确认会产生写入的那些。只读挂载仍能阻止遗漏变量改到 workspace
  之外，但新库如果用没覆盖的 cache/config 变量，还是可能出现 `PermissionError`，按真实日志补映射。
  它不等价于环境变量或凭据隔离。

**12.8.2 PyTorch DataLoader 和 `/dev/shm`（2026-07-31）**

症状：Dog Breed Identification 的多 seed 真实任务稳定报
`multiprocessing.SemLock: OSError [Errno 30] Read-only file system`。

原因：Python 的 POSIX semaphore、`multiprocessing.Queue`、`multiprocessing.shared_memory` 和
PyTorch 多 worker 的 `DataLoader` 都依赖 `/dev/shm`。早期实现把 recursive bind clone 里的所有
submount 一律设成只读，于是克隆过来的宿主 `/dev/shm` 也变成只读了。

修复：

- 不重新开放宿主 `/dev/shm`，而是在 private mount namespace 里把一个新的 tmpfs 挂到 clone 的
  `/dev/shm`（`chroot_python.py:315-327`）：`mode=1777,nosuid,nodev,noexec`，容量沿用宿主
  `/dev/shm` 的上限，并作为一个精确路径加进 writable 白名单。不同 sandbox 不共享 POSIX IPC
  对象，内容随 namespace 消失。集成测试会真的建 `multiprocessing.Queue`、跑
  `DataLoader(num_workers=2)`，并确认 sandbox 的 shm marker 在宿主 `/dev/shm` 里看不到。
- 修完 SemLock 之后还有下一层问题：PyTorch 把 tensor storage 从 worker 传回父进程时会用
  `multiprocessing.resource_sharer` 的 AF_UNIX socket。spawn 出来的 supervisor 可能从主进程继承
  了已经缓存的 resource-tracker fd 和临时目录：前者被 `close_fds_except()` 关掉了（正好不能再用），
  后者可能指向 chroot 之外，也可能落在不支持 Unix socket 的共享文件系统上。所以 executor 把这两类
  缓存都清掉（`resource_tracker` 的 `_fd`/`_pid` 和
  `current_process()._config["tempdir"]`），让 resource tracker 在降权后的 PID namespace 内重新
  启动，并把 resource-sharer 的小控制目录固定到 `/dev/shm/dojo-multiprocessing`。普通 `TMPDIR`
  不变，训练过程的一般临时文件不会因此挤占 shm。

**12.8.3 spawn 和动态 `__main__` 的 pickle 语义（2026-07-31）**

症状：8 个 seed 都能跑到 DataLoader worker 启动，然后稳定报
`Can't pickle <class '__main__.DogDataset'>: attribute lookup DogDataset on __main__ failed`。

原因：和文件可见性无关。DataLoader 需要把用户定义的 Dataset 类 pickle 给 worker，而 spawn 出来的
worker 会重新加载主脚本，再按模块名 `__main__` 回查这个类。原 `PythonInterpreter` 只是给一个普通
`exec()` 的 globals dict 设了 `__name__ = "__main__"`，这个 dict 并不是真正的
`sys.modules["__main__"].__dict__`；pickle 回查时看到的其实是 Dojo/pytest launcher 的主模块，自然
找不到同一个类。另外 spawn 是 supervisor 自己用的启动方式，会顺着 executor 泄漏成 agent 的默认
值，这和普通 Linux Python 进程不一样，不带 `if __name__ == "__main__"` guard 的脚本会被反复
重新执行一遍。

修复：executor 为 agent session 建一个真正的 `ModuleType("__main__")`，同时维护 multiprocessing
约定的 `__mp_main__` alias，用这个模块的 dict 执行 agent 代码；并把默认启动方式强制改回 `fork`
（12.5 第 3 步第 6 条）。这样带 guard 的完整 solution script 可以被 spawn worker 安全重新加载；
agent 显式要求 spawn context 时仍然按 spawn 的语义走，也就仍然需要 guard。测试会真的通过 spawn
往返一个用户定义的对象，并让 chroot 里的 DataLoader 使用定义在 agent 脚本中的自定义 Dataset，
而不是只测可以 import 的 `TensorDataset`。

### 12.9 验证结论和 demo 命令

已经通过的部分：

- `tests/test_linux_sandbox.py`（不需要特权）：mountinfo 解析（含转义路径）、rw/ro 识别、workspace
  必须是专属名字且不能是 symlink、白名单不能宽到 `/`、两个并发 UID 租约必然拿到不同 UID、
  范围耗尽时明确报错。
- `tests/test_python_interpreter.py`：原有的 persistent globals 和 traceback 语义；新增
  `../escape.py`、绝对 `file_name` 被拒绝，`fetch_file()` 只认 workspace 内的普通文件。
- `tests/test_chroot_python_interpreter.py`（需要 root + `CAP_SYS_ADMIN` + `CAP_SYS_CHROOT`）：
  agent 视角的 uid/groups/`CapEff`；workspace 可写；外部 0666 sentinel、workspace 内指向外部文件
  的 symlink、data 目录（`./data` 和 `/home/data`）以及继承来的宿主可写 fd 全部写失败；
  `/home/data` 可读而 `/home` 不可写；XDG/cache/user-site 可写且能 import；NumPy、pandas、
  scikit-learn、PyTorch 可用，`torch.cuda.is_available()` 与宿主一致；subprocess、
  `multiprocessing.Queue`、`DataLoader(num_workers=2)` 正常；sandbox 的 `/dev/shm` marker 在宿主
  `/dev/shm` 里不可见；`setsid()` 双重 fork 的后台进程在 cleanup 后消失（测试把它的宿主 PID 写进
  workspace 文件，再轮询确认）；宿主 mountinfo 前后一致，runtime 下不留 `sandbox-*`。
- Spaceship Titanic 的直接 interpreter 端到端验证已通过。

还没完成的部分：批量验证改用 `main_runner_job_array` 加单 worker 的 `local_gpu_pool`，其 Hydra
展开、源码 snapshot、manifest 创建、GPU UUID 注入和 worker 启动都已验证。完整 pool run 必须只在
独占空闲 GPU 上跑：最近一次启动时 8 张 Pod 可见 GPU 都被其他用户占用，controller 按 SIGTERM 路径
把自己的 attempt 标成 `cancelled`，没有继续竞争设备。所以这里不把那次已取消的 attempt 说成完整
pool 验证通过；等有空闲设备时直接跑下面的命令即可补上。

`python -m dojo.main_runner_job_array` 会先固定当前源码 snapshot、展开 `RunnerConfig`，再交给
`local_gpu_pool` 启动独立 worker。pool controller 为每个 worker 按 GPU UUID 写
`CUDA_VISIBLE_DEVICES`，保存 manifest、attempt 的 stdout/stderr 和 result JSON，并在 worker 完成后
汇总状态。以下命令适用于具备上述 capabilities、已准备 MLE-bench 数据、并在 `.env` 里配好 LLM key
的 Pod；它是单 seed、单 GPU 的完整 pool smoke run：

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
