# AIRA-Dojo 从 Apptainer 迁移到 Singularity 的代码库调查

## 1. 调查目标与结论

本文记录在真正修改代码前，对仓库中 Apptainer 使用位置、调用方式、封装程度，以及迁移到当前 HPC Singularity 环境的初步方案调查。

结论先行：

- Apptainer 的**运行时依赖比较集中**，核心集中在
  `src/dojo/core/interpreters/jupyter/apptainer_jupyter_server.py` 和
  `src/dojo/core/interpreters/jupyter/sand` 两个文件中；上层 solver、task 和 Jupyter client
  基本不知道容器运行时的存在。
- 目前只有“模块位置上的集中”，还没有真正的容器运行时抽象。Python 类名、环境变量、
  shell 命令、instance 生命周期、overlay 创建和日志路径都直接绑定 Apptainer。
- 镜像构建侧使用标准 definition file 和 SIF，整体可继续复用；
  `superimage/apptainer.def` 的文件名和文档偏向 Apptainer，但内容并不是迁移的主要障碍。
- **不能只做 `apptainer` → `singularity` 的文本替换。** 当前机器安装的是
  `Singularity 3.5.2+ds1`，与现有 wrapper 至少有 `instance run`、`overlay create`、
  `--env`、环境变量前缀、日志目录和 `--fakeroot` 行为等差异。
- 推荐先把运行时相关参数收口为一个小型 backend/wrapper，再实现 Singularity 3.5 backend；
  对本项目而言，优先考虑用前台 `singularity exec` 启动 Jupyter Kernel Gateway，避免继续依赖
  两套版本差异较大的 instance/log 机制。

本次调查只新增本文档，没有修改容器运行代码。

## 2. 调用链

正式实验使用 Jupyter interpreter 时，启动链路如下：

```text
Hydra 配置
  src/dojo/configs/interpreter/jupyter.yaml
        |
        v
JupyterInterpreterConfig
  src/dojo/config_dataclasses/interpreter/jupyter.py
        |
        v
JupyterInterpreter / JupyterInterpreterFactory
  src/dojo/core/interpreters/jupyter/jupyter_interpreter.py
        |
        v
ApptainerJupyterServer
  src/dojo/core/interpreters/jupyter/apptainer_jupyter_server.py
        |
        | subprocess.Popen([sand, python, -m, jupyter, kernelgateway, ...])
        v
sand shell wrapper
  src/dojo/core/interpreters/jupyter/sand
        |
        | apptainer instance run ... <SIF> <instance-name> <Jupyter command>
        v
SIF 内的 Jupyter Kernel Gateway
        |
        v
JupyterClient / JupyterCodeExecutor
```

其中，Python 进程通过读取 `sand` 的 stderr，匹配
`is available at http://<host>:<port>`，取得 Kernel Gateway 地址。停止时，
`ApptainerJupyterServer.stop()` 向整个 `sand` 进程组发送 `SIGTERM`；`sand` 的 trap 再停止
instance 并清理临时目录。

这意味着迁移主要影响 `ApptainerJupyterServer` 和 `sand` 之间的启动协议，不需要改 solver
与 Jupyter RPC/代码执行部分。

## 3. Apptainer 使用位置清单

### 3.1 运行时关键代码

| 文件 | 当前用途 | 耦合点 | 迁移优先级 |
| --- | --- | --- | --- |
| `src/dojo/core/interpreters/jupyter/sand` | 创建临时写层、缓存 SIF、启动/停止 instance、转发日志 | `apptainer` 命令、`instance run`、`overlay create`、`--fakeroot`、`APPTAINER_BIND`、`~/.apptainer/instances/logs` | 最高 |
| `src/dojo/core/interpreters/jupyter/apptainer_jupyter_server.py` | 组装 bind、overlay、镜像和容器环境，启动 `sand` | 类名、`APPTAINER_BIND`、日志字段名；没有 runtime/backend 参数 | 最高 |
| `src/dojo/core/interpreters/jupyter/jupyter_interpreter.py` | 构造容器化 Jupyter server | 直接 import/实例化 `ApptainerJupyterServer` | 高，但修改量小 |

`sand` 中具体使用包括：

1. `apptainer instance list -a -j`：启动前打印实例列表用于诊断。
2. `apptainer instance stop "$INSTANCE_NAME"`：在 signal/exit trap 中清理实例。
3. `apptainer overlay create --fakeroot --sparse --size 1048576 ...`：当
   `IMAGE_OVERLAY=1` 时创建约 1 TiB 的 sparse overlay 文件。
4. 读取并重写 `APPTAINER_BIND`：对 MLE-bench public data 做本地 scratch 缓存后，替换 bind
   source。
5. `apptainer instance run ...`：使用 `--containall`、`--cleanenv`、`--no-home`、
   `--overlay`、多组 `--env`、`--nv` 和 `--fakeroot` 启动 SIF。
6. `tail -f ~/.apptainer/instances/logs/.../<instance>.err`：把 instance stderr 转发给
   Python 父进程，使其能看到 Jupyter ready 信息。

`apptainer_jupyter_server.py` 做了部分参数整理：

- 将输入数据 bind 到 `/root/data:ro`；
- 将 `read_only_binds` 拼成 `APPTAINER_BIND`；
- 将只读 overlay 拼成 `BASE_OVERLAYS="--overlay ...:ro"`；
- 将配置中的容器环境先改名为 `RAD_<NAME>`，再由 `sand` 逐项变成 `--env NAME=value`；
- 通过 `SUPERIMAGE_DIR` 和 `SUPERIMAGE_VERSION` 把镜像位置传给 `sand`。

### 3.2 配置和间接入口

| 文件 | 作用 | 是否需要迁移 |
| --- | --- | --- |
| `src/dojo/config_dataclasses/interpreter/jupyter.py` | 定义 superimage、bind、overlay 和 env 配置 | 建议新增 runtime/backend 与 writable-layer 策略，但当前没有 Apptainer 字符串 |
| `src/dojo/configs/interpreter/jupyter.yaml` | Jupyter interpreter 默认配置 | 建议显式选择 `singularity` 或 `auto` |
| `src/dojo/utils/environment.py` | 从 `SUPERIMAGE_DIR` 读取镜像目录 | 与运行时无关，可保留 |
| `src/dojo/grade_code.py` | 直接构造 `JupyterInterpreterConfig` | 若 backend 有合理默认值，通常无需改动 |

当前配置抽象的是“镜像放在哪里、挂载什么”，没有抽象“用哪个容器运行时、该运行时支持哪些
能力”。

### 3.3 镜像构建

| 文件 | 当前用途 | 判断 |
| --- | --- | --- |
| `superimage/apptainer.def` | 从 NVIDIA CUDA Docker base 构建 SIF | definition file 的主要 section 可被 Singularity 3.5 理解，内容可继续作为单一镜像定义 |
| `superimage/pip.requirements.txt` | 注释提到 `apptainer.def` | 仅命名/说明问题 |
| `superimage/README.md` | 给出 `apptainer build` 命令 | 需要补充 Singularity 构建方式及集群限制 |
| `docs/BUILD_SUPERIMAGE.md` | 主构建说明 | 需要改为 runtime-neutral 或分别列出两套命令 |

`apptainer.def` 中真正与名称相关的内容主要是 label/comment。`Bootstrap: docker`、`From:`、
`%environment`、`%files`、`%post` 等是两边共有的 definition file 结构。SIF 也是共同格式；
本机已能用 Singularity 3.5.2 对当前 SIF 执行 `python --version`。

需要注意，文件中的 `%runscript` 与 `%startscript` 当前都被注释掉。现有 Apptainer
`instance run` 可以把 Jupyter 命令作为 payload 运行，但 Singularity 3.5 只有
`instance start`，后者的附加参数是传给 `%startscript` 的。直接替换命令后，启动语义并不等价。

### 3.4 文档和注释

以下位置是说明性引用，不直接影响程序运行：

- `README.md`
- `docs/INSTALLATION.md`
- `docs/BUILD_SUPERIMAGE.md`
- `superimage/README.md`
- `superimage/pip.requirements.txt`
- `superimage/apptainer.def` 中的 label/comment
- `src/mle_critic/docs/runtime/containers/BUILD_SUPERIMAGE_ON_MACOS.md`
- `src/mle_critic/docs/workflows/AIRA_DOJO_MLEBENCH_SPACESHIP_WORKFLOW.md`

其中 `BUILD_SUPERIMAGE_ON_MACOS.md` 已经明确区分“用 Apptainer builder 生成 SIF”和“在
Singularity 集群运行 SIF”，并指出当前 Jupyter wrapper 仍硬编码 Apptainer。这份文档应在
运行时迁移完成后同步更新，而不是简单删除所有 Apptainer 内容：macOS/Docker 中继续使用
Apptainer builder 仍可能是合理方案。

## 4. 现有抽象程度评估

### 已经做得较好的边界

- 上层统一面向 `JupyterConnectable`、`JupyterClient` 和 `JupyterCodeExecutor`，容器细节没有
  泄漏到 solver/task。
- 容器启动集中在一个 Python server 类和一个可执行 shell wrapper，改动面可控。
- 镜像目录、版本、只读 bind、只读 overlay 和容器环境已有配置入口。
- SIF 缓存、MLE-bench 数据缓存和临时目录清理由 wrapper 统一负责。

### 缺失的抽象

- 没有 `container_runtime`/backend 配置，也没有自动探测 `apptainer` 或 `singularity`。
- `ApptainerJupyterServer` 同时负责通用 Jupyter 生命周期和 Apptainer 专属环境编码。
- shell 中没有统一的 `$CONTAINER_RUNTIME` 命令变量，所有操作均直接写死。
- bind 使用运行时专属的 `APPTAINER_BIND` 作为 Python 与 shell 之间的内部协议。
- `BASE_OVERLAYS` 保存的是已经拼接好的 CLI 字符串，而不是结构化路径列表，难以按 backend
  生成不同参数，也存在路径含空格时的 shell 拆词问题。
- 容器环境只支持一组写死的变量；`cfg.env` 虽然是字典，到了 `sand` 后仍逐项硬编码。
- instance 启动、日志读取和 cleanup 是一个整体，无法单独替换其中某项能力。
- 没有覆盖 wrapper 命令生成、bind 改写、backend 探测或启动/停止生命周期的测试。

因此可评价为：**调用位置集中，但运行时抽象尚未形成。** 迁移工作量不会扩散到整个代码库，
但核心 wrapper 需要有意识地重构，不能依赖全局字符串替换。

顺带发现两个与迁移相关的健壮性问题：

- `apptainer_jupyter_server.py` 只有在 bind 非空时才设置 `APPTAINER_BIND`，但日志代码无条件
  读取 `env['APPTAINER_BIND']`，空 bind 配置可能触发 `KeyError`。
- Python 已用 `os.path.join(cfg.superimage_directory, "")` 补目录分隔符，但 `sand` 仍通过
  字符串拼接镜像路径；后续宜直接传完整、已解析的 SIF 路径。

## 5. 当前 HPC 上已确认的 Singularity 3.5.2 差异

以下结果来自本仓库所在机器上的实际 CLI 探测，版本为 `3.5.2+ds1`。

| 现有 Apptainer 用法 | Singularity 3.5.2 情况 | 影响 |
| --- | --- | --- |
| `apptainer instance run` | 不存在；只有 `instance start/list/stop` | 不能直接替换命令名；需改启动模型或增加 `%startscript` |
| `apptainer overlay create` | 顶层 `overlay` 子命令不存在 | 不能用现有方式动态创建 sparse overlay |
| 运行时 `--overlay` | `exec` 和 `instance start` 均支持 | 已有 overlay 文件可能可复用，但格式/权限仍需 smoke test |
| 多个 `--env NAME=value` | `singularity exec --env` 报 unknown flag | 必须改用 `SINGULARITYENV_<NAME>` 或容器内 `env NAME=value ...` |
| `APPTAINER_BIND` | 实测被 Singularity 3.5.2 忽略 | bind 会静默丢失，必须使用 `SINGULARITY_BIND` 或 `--bind` |
| `SINGULARITY_BIND` | 实测会被读取 | 可作为 3.5 backend 的 bind 入口 |
| `APPTAINERENV_*` | 不是当前 wrapper 的直接用法 | Singularity 3.5 应使用 `SINGULARITYENV_*` |
| `~/.apptainer/instances/logs/...` | 路径显然不适用于 Singularity | 现有 `tail -f` 无法工作 |
| `--fakeroot` + 约 19 GB SIF | 探测时触发 `Convert SIF file to sandbox...`，短时间内未完成 | 每次 Jupyter 启动可能产生不可接受的转换成本；必须验证并尽量移除 |
| `--nv`、`--containall`、`--cleanenv`、`--no-home` | CLI 帮助中均存在 | 参数名层面可继续使用，仍需 GPU 节点 smoke test |
| SIF 执行 | `singularity exec --cleanenv <SIF> ... python --version` 成功 | 镜像基本格式不是阻塞点 |

此外，当前用户在 `/etc/subuid` 和 `/etc/subgid` 中没有查到映射条目。不能仅凭这一点断言
fakeroot 完全不可用，但结合实际触发整镜像 sandbox 转换的行为，现有 `--fakeroot` 路径不适合
直接投入大规模数据采集。

## 6. 推荐迁移方案

### 6.1 第一阶段：保留 Apptainer 实现，按 server 路由

第一版不把现有实现重命名或强行抽成通用 backend，而是保留已经工作的 Apptainer 路径，新增
一套平行的 Singularity 实现：

```text
JupyterInterpreterConfig.container_runtime
                    |
             JupyterInterpreter
              /              \
ApptainerJupyterServer   SingularityJupyterServer
         |                         |
        sand                singularity_sand / exec
```

具体方案如下：

1. 在 `JupyterInterpreterConfig` 增加 `container_runtime`，第一版只支持
   `apptainer | singularity`。默认值保留为 `apptainer` 以兼容原仓库，本环境的
   `src/dojo/configs/interpreter/jupyter.yaml` 显式配置为 `singularity`。暂不加入 `auto`，避免
   同一实验因节点环境不同而静默选择不同运行时。
2. 在 `JupyterInterpreter` 中根据 `container_runtime` route 到对应 server。两个 server 都继续
   实现 `JupyterConnectable`，因此上层 `JupyterCodeExecutor`、solver 和 task 不需要感知运行时。
3. 保留 `ApptainerJupyterServer`、`APPTAINER_BIND` 和现有 `sand`，避免 Singularity 迁移影响
   原 Apptainer 行为。
4. 新建 `SingularityJupyterServer`，在其内部使用 `SINGULARITY_BIND`、
   `SINGULARITYENV_<NAME>` 和 Singularity 专属命令，不复用 `APPTAINER_BIND` 作为内部协议。
5. Singularity server 需要额外接收 `working_dir`，并传入完整、已解析和检查过的 SIF 路径。
6. 第一版允许两个 server 之间存在少量生命周期代码重复。待 Singularity smoke test 稳定后，再
   提取 token、ready-line 解析、connection info 和 stop 等公共逻辑，避免过早把 Apptainer
   instance 语义抽进公共层。

为了保持两条路径隔离，Singularity 最好使用独立的 `singularity_sand`，或者直接由
`SingularityJupyterServer` 构造参数数组并启动 `singularity exec`；不建议在现有 `sand` 中加入
大量 runtime 分支。

### 6.2 第二阶段：使用前台 `singularity exec`

Singularity 3.5 首版不使用 instance。当前 Python 父进程已经通过独立进程组管理 server 生命周期，
Jupyter 通信也只依赖 Kernel Gateway 的 HTTP/WebSocket 地址，因此 instance 不是必要条件：

```text
SingularityJupyterServer
    -> Popen(singularity_sand ...)
        -> singularity exec <flags> <binds> <SIF>
             python -m jupyter kernelgateway ...
```

这样可以：

- 避开 Singularity 3.5 缺失的 `instance run`；
- 不依赖镜像中的 `%startscript`；
- 直接读取 Jupyter stdout/stderr，不再 tail `~/.singularity/instances/logs`；
- 继续由 `ApptainerJupyterServer.stop()`/`SingularityJupyterServer.stop()` 对各自进程组发送信号；
- 避免 instance 名称、日志路径和异常清理在不同版本之间的差异。

Singularity 3.5 不支持现有 wrapper 使用的 `--env NAME=value`。Singularity server 应在启动前
设置 `SINGULARITYENV_<NAME>=<value>`。bind 可使用参数数组形式的重复 `--bind`，或设置
`SINGULARITY_BIND`；第一版优先使用显式 `--bind` 参数，便于日志记录、路径校验和测试。

### 6.3 第三阶段：首版不启用 fakeroot 和 overlay

首轮 smoke test 明确不使用 `--fakeroot`、`--overlay` 或 `--writable-tmpfs`。本机已经用当前镜像
`build/superimage/superimage.root.2026-07-macos-v1.sif` 验证：在无 fakeroot、无 overlay 的
`singularity exec --containall --cleanenv --no-home` 中，只要将 `HOME` 和 Jupyter runtime
指向可写目录，Kernel Gateway 3.0.1 可以正常启动并输出 ready 地址。

fakeroot 和 overlay 不是运行 Jupyter、Python、只读数据 bind 或 `--nv` 的硬需求。它们在原实现
中的主要作用是让 `/root`、`/opt/conda` 等 root-owned 镜像目录可写。单独使用
`--writable-tmpfs` 也不能解决 Unix 权限问题：本机实测普通宿主 UID 仍无法写入 `/root` 和
`/opt/conda`。

Singularity 首版改为显式挂载可写工作区：

```text
宿主 working_dir  -> /workspace:rw
宿主 data_dir     -> /workspace/data:ro
kernel cwd        -> /workspace
HOME              -> /workspace/.home
Jupyter runtime   -> /workspace/.home/.local/share/jupyter/runtime
Python user base  -> /workspace/.local
```

对应命令形态大致为：

```bash
singularity exec \
  --containall \
  --cleanenv \
  --no-home \
  --nv \
  --bind "$WORKING_DIR:/workspace:rw" \
  --bind "$DATA_DIR:/workspace/data:ro" \
  --pwd /workspace \
  "$SIF" \
  python -m jupyter kernelgateway ...
```

其中通过 `SINGULARITYENV_HOME`、`SINGULARITYENV_JUPYTER_RUNTIME_DIR` 和
`SINGULARITYENV_PYTHONUSERBASE` 设置上述容器环境。这样 `./data`、`submission.csv`、模型文件、
Jupyter runtime 和普通用户缓存都有明确的可写位置，并且输出直接持久化到宿主 working directory。

这一方案与原环境的主要行为差异是：学生代码不能在运行时修改系统 Conda 环境、写
`/opt/conda` 或执行 `apt install`。普通 Python 依赖优先通过 `pip install --user` 安装到
`/workspace/.local`；是否设置全局 `PIP_USER=1` 应通过实际任务 smoke test 决定。若高频任务缺少
系统级依赖，优先将依赖加入下一版 superimage，而不是立即恢复 fakeroot。

只有出现无法通过 writable workspace、user-site 或重建 SIF 解决的真实任务后，再评估由管理员
预生成 ext3 overlay、集群支持的目录 overlay 或其他方案。fakeroot/overlay 不作为首版迁移的
阻塞项。

### 6.4 第四阶段：暂缓构建和文档命名调整

当前 SIF 已经构建完成，并能被本机 Singularity 3.5.2 读取和执行。首轮迁移不重命名
`superimage/apptainer.def`，不重写 Dockerfile，也不全面修改构建文档。

待以下条件满足后再统一处理构建与文档：

1. `SingularityJupyterServer` 能启动 Kernel Gateway；
2. 一个无 GPU 的代码执行/文件输出 smoke test 通过；
3. GPU 节点上的 `--nv` 和完整 MLE-bench smoke task 通过；
4. writable workspace、user-site 安装和异常清理行为已经稳定。

## 7. 建议的测试矩阵

### 不需要 GPU 的快速测试

1. 显式 backend 选择能路由到 `singularity`，且版本信息进入日志。
2. 当前 SIF 能执行 Python、导入 Jupyter Kernel Gateway 和关键 Python 包。
3. `/workspace/data:ro` 和额外 `read_only_binds` 在容器内路径、权限正确。
4. `cfg.env` 任意键值可进入 `--cleanenv` 容器，而不是只支持当前硬编码列表。
5. writable strategy 能在 session 内创建文件和安装一个小包。
6. Kernel Gateway ready 行能被 Python 解析，代码执行与文件拉取正常。
7. 正常关闭、超时、`SIGTERM` 和启动失败都不会遗留进程或 scratch 目录。
8. 两个并发 Jupyter session 的进程/工作目录/端口互不冲突。

### GPU 节点测试

1. `--nv` 后容器内 `nvidia-smi`、PyTorch 和 CUDA driver 可见。
2. 一个最小 CUDA tensor 运算成功。
3. RAPIDS/FAISS GPU 的 build variant 与运行时匹配。
4. 多 GPU job 中可见设备与 Slurm 分配一致，不泄漏其他 GPU。

### 大规模采集前的性能与稳定性测试

1. 冷/热缓存下的 SIF staging 时间和共享存储带宽。
2. writable layer 的每 job 磁盘、inode 和内存占用。
3. 10/50/目标并发数下的启动成功率、启动 P50/P95 和清理成功率。
4. job 被 Slurm 强杀后是否残留容器进程、mount 或临时文件。
5. MLE-bench public data 本地缓存改写在 Singularity bind 语义下是否仍正确。

## 8. 建议的实施顺序

1. 先补 runtime 配置、feature probe 和 wrapper 单元/命令生成测试。
2. 实现 Singularity 3.5 的前台 `exec` 最小路径，暂时关闭动态 image overlay 和 fakeroot。
3. 跑一个不依赖 GPU 的 Jupyter smoke task。
4. 选择并验证 writable-layer 方案。
5. 在 GPU 节点跑完整 MLE-bench smoke task。
6. 做并发和异常清理测试。
7. 再保留或恢复 Apptainer backend，并统一更新文档。

这个顺序能先证明“Jupyter + bind + env + SIF”主链路，再处理 overlay/fakeroot 这一最依赖 HPC
管理员配置的部分，便于定位问题和控制大规模采集风险。

## 9. 实现状态（2026-07-19）

迁移已经按“保留 Apptainer、增加平行 Singularity backend”的方案落地：

- `JupyterInterpreterConfig.container_runtime` 支持 `apptainer | singularity`，仓库默认 Hydra
  配置显式选择 `singularity`。
- 新增 `SingularityJupyterServer`，使用前台 `singularity exec`，由 Python 父进程组直接管理
  生命周期和日志；不使用 instance、fakeroot 或动态 writable overlay。
- 宿主工作目录挂载为 `/workspace:rw`，数据目录挂载为 `/workspace/data:ro`；HOME、Jupyter
  runtime 和 Python user base 都位于持久化工作区。
- 任意 `cfg.env` 通过容器内 `env NAME=value ...` 参数数组注入。实测 Singularity 3.5.2 的
  `SINGULARITYENV_HOME` 会被当前 SIF `%environment` 中的 `HOME=/root` 覆盖，因此这里没有采用
  调查阶段最初建议的 `SINGULARITYENV_*` 方案。
- 已保留只读 overlay 支持，转换为重复的 `--overlay <path>:ro`；没有恢复 writable overlay。
- 原 Apptainer server 的空 bind 日志 `KeyError` 同时得到修复。

使用 `superimage.root.2026-07-macos-v1.sif` 的本机 smoke test 已验证：Kernel Gateway 启动、
kernel 创建和代码执行、工作区文件持久化、只读数据 bind、自定义环境变量、同一 kernel 内的
`pip install --user` 和立即 import、进程清理、两个并发 server 自动选择 8888/8889 端口，以及
RTX 3090 上的 PyTorch CUDA tensor 运算。尚未进行目标 Slurm 作业规模下的 10/50 并发压力测试
和共享 SIF/data staging 性能测试。
