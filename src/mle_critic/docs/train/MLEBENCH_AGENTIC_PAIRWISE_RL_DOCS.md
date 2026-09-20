# MLEBench Agentic Pairwise RL：方案、实现与验收

更新日期：2026-09-20。

本文按当前代码说明系统如何工作，并合入 2026-09-20 的真实训练验收结果。
构建数据、启动训练、修改参数和查看结果，请看
[中文操作文档](MLEBENCH_AGENTIC_PAIRWISE_RL_RUN.md)。底层机制可以与
[Chroot Python Interpreter 隔离说明](../runtime/interpreters/CHROOT_PYTHON_INTERPRETER_ISOLATION_PLAN.md)
第 12 节对照阅读；两套实现复用了 Linux 原语，但文件系统视图和执行协议不同。

## 1. 当前目标与完成状态

输入同一 MLEBench 任务的两个完整 solution，agent 读取代码和公开数据，执行少量 CPU
诊断，判断哪个 solution 的测试集表现更好。它不需要把两个 solution 完整训练一遍，
也不调用 MLEBench private evaluator。“更好”遵循原 pair 的 `better/worse` 标签，
包括 loss 越低越好的任务，不是简单比较原始分数的数值大小。

当前已跑通：

```text
selected pair + 原始 cards
  -> verl Parquet（prompt、代码字段、A/B 标签）
  -> 同一个 pair 采样 4 条独立 trajectory
  -> Qwen 多轮生成 <-> 本 trajectory 的 CPU sandbox
  -> 解析最后一轮 assistant 的 boxed A/B，得到 0/1 reward
  -> GRPO advantage -> old log probability -> 反向传播与 optimizer 更新
  -> checkpoint、标准 rollout dump、逐事件审查轨迹
```

2026-09-20 已完成真实 Qwen3.8-27B 的一个小批量 GRPO step，非零梯度、checkpoint
和轨迹均已验证，详见[第 12 节](#smoke-20260920)。这是单 step 验收，未完成全量
数据的一个 epoch，也不能据此宣称 judger 能力已经提升。

当前范围是 CPU-only 诊断、`bash` 和 `text_editor` 两个工具、每轮最多执行一个工具、
一次 trajectory 内持久保存文件。没有 Git/commit 工作流、GPU sandbox 开关或持久
Python globals，不保留 agent 创建的 workspace 文件作为训练产物。Prompt 禁止重型
训练和安装包；宿主系统与 Conda 环境只读，但没有识别并拒绝所有 pip/conda 命令的
过滤器，不能把 prompt 约束说成内核级禁令。

## 2. 与原 ChrootPythonInterpreter 的关系

原 interpreter 主要解决“agent 不能修改别人的文件”。Pairwise RL 还要求 agent
读不到标签和 private data，因此不能直接复用它对宿主 `/` 的整体只读克隆。
只读意味着“能看但不能改”；对于 reward leakage，“能看”本身就已经有问题。

| 项目 | 原 ChrootPythonInterpreter | 当前 ChrootBashSandbox |
| --- | --- | --- |
| 文件系统来源 | 宿主 `/` 的递归只读 bind clone | 空 tmpfs root，只挂载显式允许的目录 |
| 仓库与宿主数据 | 可能只读可见，受 POSIX 权限约束 | 仓库、pair/card、private、宿主 home/tmp 不挂入 |
| 执行单元 | 持久 Python exec session | 每次调用新建 bash 或 editor 进程 |
| 通信 | multiprocessing Queue | stdin/stdout 上的逐行 JSON 管道 |
| PID 1 | 独立 init，另有 executor | PID 1 兼任降权后的 command server |
| 网络与 GPU | 不属于原方案隔离目标 | 新 network namespace，不挂 NVIDIA device |
| 资源 | 原方案不限制 | 初始 CPU affinity、rlimit、tmpfs 大小、超时、slot |
| workspace | 保留供 evaluator 使用，恢复 owner | trajectory 专属，结束直接删除 |
| `/proc` | 为 CUDA 兼容保留可写新 procfs | CPU-only，新的 procfs 再设为只读 |

复用的是 [linux_sandbox.py](../../../dojo/core/interpreters/linux_sandbox.py) 中的
系统调用、挂载检查、数字 UID 租约、降权和 FD 清理函数。verl 没有进入 Dojo 的
Interpreter/task/solver 生命周期，也没有复用原 Python session loop。

### 2.1 按文件阅读实现

| 文件 | 职责 |
| --- | --- |
| [common.py](../../src/agentic/common.py) | task allowlist、公开数据路径校验、最终答案解析 |
| [build_dataset.py](../../src/agentic/build_dataset.py) | selected pairs/cards、随机 A/B 方向、prompt 与 Parquet |
| [mle_agent_loop.py](../../src/agentic/mle_agent_loop.py) | verl trajectory 生命周期、工具派发、reward、trace |
| [sandbox.py](../../src/agentic/sandbox.py) | 可信宿主 client：UID/slot、写代码、启动、异步通信与清理 |
| [sandbox_server.py](../../src/agentic/sandbox_server.py) | namespace/rootfs、降权、命令进程、限时限输出 |
| [editor.py](../../src/agentic/editor.py) | sandbox 内的低权限文本编辑程序 |
| [audit_traces.py](../../src/agentic/audit_traces.py) | trace 汇总成 audit.json 和逐条 Markdown |
| [agent_loop.yaml](../../recipes/agentic/agent_loop.yaml) | loop 注册、trace 路径、sandbox 配置 |
| [tools.yaml](../../recipes/agentic/tools.yaml) | Qwen 可见的工具 schema |
| [agentic launcher](../../../verl/my_scripts/train/mle_judge/8xh200/run_qwen3_8_27b_agentic.sh) | 在原单轮脚本上覆盖多轮和 smoke 参数 |

## 3. 数据怎么进入模型与 sandbox

### 3.1 输入、方向与 split

```text
data/augmented_mle_critic/batch_value_pairs_selected_filtered_runsplit.jsonl
data/augmented_mle_critic/augmented_cards_current.json
data/mlebench/<task>/prepared/public/
```

Builder 复用 `read_cards()` 建立 card ID 索引，不复用会过滤缺失 endpoint 的旧
`read_pairs()`。它逐行读取 pair，直接查 better/worse 对应 card；缺 card、未知
task/split、代码为空或 card 与 pair 的 task 不一致都会失败。

用 `random.Random(seed)` 选择 better 在 A 还是 B，默认 seed=7。代码和标签一起
交换：ground_truth=A 就意味着 solution_A 来自 better card。原始 execution_timeout
和 hardware 写进 user prompt，用来判断 solution 在原评测条件下是否可行，不能
覆盖 sandbox 的实际限制。不能因为诊断 sandbox 无 GPU 就判定原 GPU solution 不可行。

sample_uuid 是下面内容做 SHA-256 后取前 32 个十六进制字符：

```text
["agentic-v1", task, better_card_id, worse_card_id, A/B方向]
```

Builder 拒绝重复的这个 UUID，并检查 train/test 的 card endpoint 集合不相交。
方向同时依赖输入顺序和 seed；改变 pair 顺序可能改变方向。沿用 intask_split，
不重新随机切分，没有另行实现 LOTO。

### 3.2 一条记录的字段

```json
{
  "data_source": "mlebench_pairwise_agentic",
  "agent_name": "mle_agent",
  "prompt": [
    {"role": "system", "content": "工具使用、预算和最终答案约束"},
    {"role": "user", "content": "任务名、A/B位置、各自原始硬件和时间条件"}
  ],
  "ability": "mle_pairwise_judging",
  "reward_model": {"style": "rule", "ground_truth": "A"},
  "sample_uuid": "稳定的32位十六进制字符串",
  "task": "spooky-author-identification",
  "solution_A": "原始完整代码",
  "solution_B": "原始完整代码",
  "extra_info": {"index": 0, "tool_selection": ["bash", "text_editor"], "split": "train"}
}
```

只有 prompt 被渲染成初始模型输入。代码字段随 batch 送给可信 loop，由 sandbox
client 写文件；标签留在可信进程中用于打分。字段处于同一条 Parquet 记录不意味着
它们都会拼入 chat template。竞赛说明通过 `/mnt/data/description.md` 读取，
不预先塞入 prompt。

Prompt 要求阅读两份代码并做至少一次小型诊断，但 reward 当前只衡量最终判断是否
正确，没有额外实现“未调用工具就扣分”的规则。

### 3.3 当前构建结果

| task | train | test |
| --- | ---: | ---: |
| AI4Code | 566 | 96 |
| google-quest-challenge | 644 | 177 |
| learning-agency-lab-automated-essay-scoring-2 | 727 | 85 |
| spooky-author-identification | 1332 | 206 |
| petfinder-pawpularity-score | 1047 | 57 |
| whale-categorization-playground | 960 | 83 |
| chaii-hindi-and-tamil-question-answering | 643 | 59 |
| dog-breed-identification | 1164 | 197 |
| random-acts-of-pizza | 828 | 47 |
| tweet-sentiment-extraction | 420 | 10 |
| 合计 | 8331 | 1017 |

train 的 A/B 标签分别为 4199/4132，test 为 543/474，全部 9348 条 pair 被保留。
输出在 `src/verl/data/mle_agentic/`：完整 train/test Parquet、manifest，以及各
split 按原顺序取前 8 条的 smoke 文件；没有按 reward 或难度挑选 smoke 样本。

## 4. 底层操作分别解决什么问题

### 4.1 系统调用与 ctypes

mount、unshare、prctl 是 Linux 内核提供的操作。Python 通过 libc 的 C 接口
调用它们：linux_sandbox.py 使用 `ctypes.CDLL(None, use_errno=True)` 获取
接口，声明参数/返回类型，把内核 errno 转成 Python 异常。例如 EPERM 表示权限
不足，EROFS 表示目标在只读文件系统中。

挂载路径直接作为函数参数传给内核，不经过 shell 解释。真正执行任意 bash 的位置
只有已经完成隔离、降权后的命令子进程。

### 4.2 Mount namespace：独立挂载表

挂载表描述“某个路径接在哪个文件系统上”。`unshare(CLONE_NEWNS)` 让 supervisor
拥有自己的挂载表，子进程继承它，无需复制磁盘文件。随后执行
`mount(None, "/", flags=MS_REC | MS_PRIVATE)`，关闭挂载传播，避免 mount/unmount
事件影响 Pod 中其他进程。

这一步本身不隐藏宿主文件。建立新 rootfs 并进入 chroot 后，agent 才只看到选中的
目录。Namespace 的最后一个进程退出且相关引用释放后，内核回收私有挂载；正常
cleanup 不需要在宿主挂载表上逐个 umount。

### 4.3 Bind mount：同一份文件的另一个入口

把宿主当前任务的 prepared/public bind 到新 root 的 mnt/data，进入 chroot 后
就能通过 `/mnt/data/train.csv` 读取原 CSV。Bind 不复制数据，也不是冻结快照：
可信宿主若修改原文件，sandbox 仍可能看到变化。

只读来自 remount：`MS_BIND | MS_REMOUNT | MS_RDONLY` 修改的是这个 bind 入口
的属性，不应把宿主整个底层文件系统一起改成只读。子挂载各有属性，不能只处理
最外层目录；`remount_tree_readonly()` 根据 mountinfo 逐个处理树内挂载。

| 标志 | 作用 |
| --- | --- |
| MS_BIND / MS_REC | bind 文件或目录；递归带上已有子挂载 |
| MS_REMOUNT / MS_RDONLY | 修改挂载属性；禁止通过该入口写入 |
| MS_PRIVATE | 禁止挂载事件向其他 namespace 传播 |
| MS_NOSUID | 在该挂载上忽略 setuid/setgid 提权语义 |
| MS_NODEV | 不把该挂载上的设备节点作为可访问设备 |

`verify_writable_mounts()` 再从 `/proc/self/mountinfo` 读取真实结果，只允许
workspace、tmp、run、dev/shm 四个精确挂载点可写。发现额外可写挂载就启动失败，
不进入命令执行阶段。这是对最终状态的复核，防止构造顺序遗漏子挂载。

### 4.4 tmpfs 与 procfs 是两种不同的文件系统

tmpfs 创建空白临时文件系统，内容占用内存，并可在系统允许时使用 swap。
size=256m 是容量上限，不表示立刻预分配 256 MiB。本实现的 root、`/tmp`、`/run`、
`/dev/shm` 都使用新 tmpfs，其中 root 最后改为只读。

procfs 是内核动态提供的进程信息视图，挂载类型是 proc，**不是 tmpfs**。
必须在进入新 PID namespace 后新挂 `/proc`，才能让它对应本 namespace，不能
直接把宿主 procfs 搬进来。它不用于保存 agent 的普通输出文件。

### 4.5 chroot：改变路径起点

`os.chroot(root)` 后，进程看到的 `/` 是新 rootfs。紧接着
`os.chdir("/workspace")`，把 cwd 也移入新根，避免保留 chroot 外的工作目录。

chroot 不自动降权、限制网络或使文件只读；已经打开的文件描述符也不会自动失效。
因此还要关继承 FD、移除 root 权限和 capabilities。不能把全部隔离效果归因于
chroot 一行代码。

### 4.6 数字 UID/GID、capabilities 与 no_new_privs

UID/GID 是内核使用的数字身份，不需要先 useradd。默认 sandbox 使用
300000–300031，各自将专属 workspace chown 给对应编号。只在新 rootfs 内
生成最小 passwd/group，方便 id 等工具显示用户名，不修改宿主账户数据库。

`drop_privileges()` 先清除附加组、削减 capability bounding set，再用
setresgid/setresuid 替换 real/effective/saved ID，最后设置 no_new_privs。
Capability 是拆分后的 root 权能，例如 mount/chroot 权能；移除后，命令不能
自己重新挂入宿主目录。no_new_privs 禁止通过执行 setuid/file-capability 程序
重新获得权限。

这里没有创建 user namespace，UID 300000 在宿主看来仍是 UID 300000。部署时应
保留这段编号，避免与实际平台账户或不协调的其他 sandbox 池冲突。

### 4.7 PID namespace、进程组与父死亡信号

`unshare(CLONE_NEWPID)` 只影响随后创建的孩子，不改变调用者自己的 PID 视图。
所以 supervisor 紧接着 fork，孩子才成为新 namespace 的 PID 1；它在宿主另有
一个 PID，supervisor 保存这个宿主 PID 来定向终止它。

每条命令通过 start_new_session=True 建独立 session/进程组，超时用 killpg
终止该命令组。但后台后代可以再次 setsid 脱离它。PID namespace 是更外层的
结束边界：终止 PID 1 时，内核会杀掉其中剩余进程，包括已脱离原进程组的后代。

PR_SET_PDEATHSIG 要求父进程死亡时内核给自己发信号，是主进程异常退出的兜底。
Supervisor 和 namespace init 都设置它，默认 SIGKILL。setresuid 会清除这个
设置，所以降权后必须重设，不能只在 fork 后设置一次。

PID 1 还接管孤儿进程。这里 command server 每条命令结束后调用
`waitpid(-1, WNOHANG)` 回收已退出的孩子，不是原 interpreter 中始终阻塞在
waitpid 的独立 init 循环。后台进程可能跨工具调用存活，最终由 trajectory 清理结束。

### 4.8 flock：跨 Ray worker 的并发协调

asyncio.Lock 只协调进程内协程，不能单独限制整台节点。UidLease.acquire 对
`runtime_base/uid-locks/<uid>.lock` 申请非阻塞排他 flock；拿到锁才能用对应 UID，
也就占了一个 sandbox slot。

可信 client 全程持有锁 FD，子进程不继承；释放 lease 或持有者退出后锁释放。
锁文件长期存在，文件存在不代表 slot 被占用。所有要共享上限的 worker/run 必须
使用同一个 runtime_base 和一致的池配置；这是节点文件锁协调，不是多节点集群调度。

## 5. 一个真实 sandbox 的启动过程

### 5.1 进程树与权限位置

```text
AgentLoopWorker（可信宿主；持有标签、trace、UID lease）
  └─ supervisor：/usr/bin/python3 -m ...sandbox_server
       │  root；独立 stdlib Python；私有 mount/network namespace；等待孩子
       └─ fork -> 新 PID namespace 的 PID 1
            ├─ 以 root 建 rootfs、挂载、chroot、设资源限制
            ├─ 降权为 300000+，兼任 command server
            └─ 每次 Popen 一条命令（低权限 UID，独立进程组）
                 ├─ /bin/bash --noprofile --norc -c <command>
                 └─ 或 /usr/bin/python3 -I /opt/mle-editor.py <JSON>
```

独立启动系统 Python，让 supervisor 从干净进程开始；没有在包含 Ray/CUDA 线程的
训练进程中直接 fork 一个继续运行 Python 的 executor。Namespace fork 发生在只
导入标准库和 Dojo Linux 原语的 supervisor 中。

### 5.2 可信 client 准备目录和代码

构造 client 时检查 sample UUID 只能包含字母、数字、下划线和连字符，长度 1–128。
Task 必须在 allowlist；公开数据路径由可信 mlebench_data_root 推导，resolve 后
仍须在该 root 内并确实是目录。模型不能通过工具参数指定另一套数据根。

start 确保 runtime_base 是启动用户拥有的私有目录，取得 lease，再用 uuid4 为
每次采样生成 trajectory UUID：

```text
/tmp/mle-agent-sandboxes/                 可信宿主拥有，默认 0700
├── uid-locks/300000.lock ...             复用的锁文件
└── <sample_uuid>/                       同一个 pair 共享这一层
    └── <trajectory_uuid>/               每次采样独立，结束后删除
        ├── root/                       新 rootfs 挂载点
        └── workspace_agent/            agent 文件的宿主落点
            ├── candidate_A/solution.py
            ├── candidate_B/solution.py
            └── scratch/
```

两份代码用 `open("x", encoding="utf-8", newline="")` 独占创建，不覆盖已有文件，
不改换行。建立 data symlink 后，用不跟随 symlink 的 chown 交给租用 UID。
Workspace 是新建且事后删除的，不需要恢复原 owner。

### 5.3 supervisor 和 PID 1 建立隔离

1. Client 启动 supervisor，只传系统 PATH 和导入项目所需的 PYTHONPATH。第一行
   stdin 发送可信配置：root/workspace/public、UID、CPU 列表、Conda roots、输出上限。
2. Supervisor 设置父死亡信号，unshare mount、PID（供孩子）和 network namespace，
   将根挂载传播设为 private。
3. Fork 后父进程等待；孩子成为 PID 1，调用 make_root。
4. 在 root/ 上建空 tmpfs，按下表逐项挂入运行时、Conda、public 和 workspace。
5. 建私有临时 tmpfs、新 procfs；把 proc/root 改为只读，复核可写挂载白名单。
6. Chroot、chdir 到 workspace，设置 affinity、nice、rlimit，再降权。
7. 重新设置父死亡信号，只留 FD 0/1/2，清空环境变量并建立最小环境。
8. 输出 ready 握手。Client 最多等 60 秒；失败就清理上抛，不降级成宿主执行。

### 5.4 agent 实际能看见的路径

| sandbox 路径 | 来源与权限 |
| --- | --- |
| `/` | 新建 32 MiB tmpfs，最后只读；容量不含另挂的目录 |
| `/usr`、`/bin`、`/sbin`、`/lib`、`/lib64` | 存在的系统运行时只读挂入；宿主为 symlink 时保留链接布局 |
| `/etc/ld.so.cache`、`nsswitch.conf`、`ssl/certs`、`localtime` | 存在时逐项只读挂入，不挂整个 etc |
| `/etc/passwd`、`/etc/group` | 新 rootfs 内最小账户记录，随 root 只读 |
| `/public/hk-research/users/jiqian/miniconda3` | 配置允许的 Conda root，保留绝对路径，只读 |
| `/workspace` | 本 trajectory 的 workspace_agent，可写 bind |
| `/mnt/data` | 仅当前 task 的 prepared/public，只读 bind |
| `/opt/mle-editor.py` | 可信 editor 脚本，只读 bind |
| `/tmp`、`/run`、`/dev/shm` | 分别为 256 MiB、16 MiB、256 MiB 的独立可写 tmpfs，mode 1777 |
| `/dev/null`、`zero`、`random`、`urandom` | 仅四个基本 device，逐项 bind |
| `/proc` | 新 PID namespace 的新 procfs，只读挂载 |

workspace/data、candidate_A/data、candidate_B/data 都指向 `/mnt/data`。
宿主 workspace 位于 `/tmp` 下不会被 sandbox 私有 tmp 隐藏，因为它在内部挂载
到 `/workspace`，与内部 `/tmp` 是两个不同路径。

不挂入仓库根、pair/card、prepared/private、宿主 home/root/tmp、run/secrets 或
sys/fs/cgroup。为容纳 Conda 绝对路径而创建 `/public/...` 父目录，不意味着整个
宿主 public 已挂入。Allowlist 的 Conda root 中可读文件仍对 agent 可见，因此
不应把标签、凭据或私有材料存放在这些受信任的运行时目录中。

### 5.5 环境变量与 Conda

Server 降权后清空环境，重设 PATH、HOME、LANG、TMPDIR、Python user site、
HF/Torch/Matplotlib/XDG cache 和线程数。宿主 API key、代理、import 路径等
不传给命令。FD 0/1/2 是协议/诊断管道；命令 stdin 另外设为 DEVNULL，stdout/
stderr 使用自己的管道，Popen 还设置 close_fds=True。

保留 Conda 绝对路径让环境中依赖自身 prefix 的路径继续有效。模型可以执行：

```bash
source /public/hk-research/users/jiqian/miniconda3/etc/profile.d/conda.sh &&
conda activate aira-dojo &&
python -c 'import pandas as pd; print(pd.read_csv("/mnt/data/train.csv", nrows=2).shape)'
```

每次都是新的 bash --noprofile --norc -c，没有 login shell 的 -l。上次的 cd、
export、Conda 激活不延续，文件会延续。基础 PATH 不自动选择 aira-dojo Python，
需要其依赖时须在同一条 command 激活。依赖仓库 editable install 的包可能无法
导入，因为对应源码根没有挂入，这是稀疏文件系统视图的代价。

## 6. 工具调用、超时与清理

### 6.1 协议及两种工具

工具 YAML 用 verl 的 BaseTool 承载 schema；实际执行走 MLEAgentLoop._call_tool，
不调用 BaseTool 默认的 create/execute/release。每次工具调用复用同一 sandbox。

Client 检查工具名、JSON object、参数名和类型，拒绝 NUL 字符及序列化后超过
128 KiB 的参数。合法请求通过 stdin 一行 JSON 发送，stdout 一行 JSON 返回：

```text
request:  {id, operation, arguments, timeout_s}
response: {id, exit_code, timed_out, stdout, stderr, duration_s, truncated_bytes}
error:    {id, error}
```

Client 校验回复 ID，用 asyncio.Lock 串行化同一 sandbox 的请求。管道读取是
异步等待，不阻塞其他 trajectory。一次 assistant 生成多个工具调用时，父类只
执行第一个，loop 在 observation 中明确提示其他调用没有执行。

Bash 从 workspace 启动新 shell；text_editor 在 sandbox 内以同一低权限 UID
启动 editor.py，由它解析和打开路径，宿主 root client 不替模型打开文件。

| editor command | 当前行为 |
| --- | --- |
| view | 读取不超过 2 MiB 的文件，显示行号，输出字符串取前 60000 个字符 |
| create | 独占创建，不覆盖已有文件；内容来自 file_text |
| str_replace | old_str 非空且恰好匹配一次才替换，否则不修改 |
| insert | insert_line 是插入前已有行数，0 表示开头，范围 0 到总行数 |

Editor 路径 resolve 后必须位于 workspace。workspace/data 指向 `/mnt/data`，
所以通过 editor 看这个 symlink 下的数据也会被拒绝；查看公开数据应该使用 bash。
路径检查是工具级约束，不是消除所有并发 symlink race 的文件系统事务；底层
chroot、只读 mount 和低权限仍是宿主隔离的关键。

### 6.2 输出的三层限制

Server 用 selector 同时非阻塞读取 stdout/stderr。不能先等进程退出再读输出：
子进程可能在管道写满后卡住，导致父子双方互相等待。

每路最多保留 65536 字节，超出仍继续读出并丢弃，累计 truncated_bytes。
使用 UTF-8 errors=replace 解码，非法字节不会破坏 JSON 协议。Trace 的 result
也是这个已限字节的版本，不是无限原始输出。

返回模型前，loop 先将 JSON 文本取前 max_tool_response_length=16000 个字符并
加提示；再 tokenize，必要时保留 prompt_length-128 个 token 并加提示，给模板
留空间。当前 verl 对新渲染的每段工具消息也检查 prompt_length，提前截 observation
可以防止工具模板起始标记被左截掉。尾部提示有少量开销，16000 不是最终消息的
严格 token 上限。当前自定义 loop 保留开头，没有使用父类的 middle 截断策略。

### 6.3 不同时间限制

| 限制 | 起点与范围 | 超限处理 |
| --- | --- | --- |
| slot 等待，默认 1800 秒 | client 申请 UID lease | 每 0.1 秒异步重试，超时上抛，可取消 |
| ready，60 秒 | 等待 supervisor 握手 | 启动失败，清理并上抛 |
| command，默认 120 秒 | 一条 shell/editor 命令 | 终止命令进程组，返回 timed_out/exit_code |
| trajectory，YAML 为 1200 秒 | ready 后多轮生成和工具阶段 | 外层 asyncio.wait_for 取消 loop，清理并上抛 |

Command 实际预算取 command_timeout_s 与 trajectory 剩余时间的较小值，client
等回复额外给 5 秒通信/结束开销。源码没传 trajectory 参数时 fallback 为 600 秒，
训练 YAML 则显式传 1200 秒；slot 等待和启动握手不包含在这 1200 秒中。

单命令超时当前**直接 SIGKILL 进程组**，没有先 TERM 的软停止步骤。若脱离进程组
的后代仍持有输出管道，采集循环在预算后约 1 秒停止继续等待 EOF。因此单命令超时
不等于已经销毁整棵 namespace 进程树，后者发生在 trajectory 清理阶段。

工具参数错误、普通非零 exit 和可捕获的命令超时成为 observation，模型可继续。
整个 trajectory 超时或生成服务异常则会上抛到 verl，可能中止当前 batch；尚未
实现自动把这类失败转换成可训练的部分轨迹与 0 reward。

### 6.4 结束顺序

`async with sandbox` 覆盖正常返回和异常，进入阶段失败也调用 close；退出阶段
用 asyncio.shield 保护清理任务。正常 close 按以下顺序执行：

1. Client 向 supervisor 发 SIGTERM。
2. Supervisor handler 向其记录的 namespace PID 1 发 SIGKILL。
3. 内核终止 namespace 内剩余进程；supervisor 用 waitpid 等待孩子退出。
4. Client 最多等 supervisor 5 秒；超时则强杀 supervisor 所在进程组并等待退出。
5. 删除本次 trajectory runtime/workspace；sample_uuid 目录为空时也删除它。
6. 释放 UID lease；trace 最后写 closed 和 runtime_removed。

正常退出不保留 submission、探针文件和 cache。主进程异常强杀时，父死亡信号
负责尽量结束进程链，但目录删除逻辑可能来不及执行，仍可能残留磁盘目录。
当前没有 state.json、自动陈旧目录扫描器或原 interpreter 的 owner 恢复流程。

## 7. CPU、内存、网络与 GPU 的实际边界

### 7.1 CPU 与节点并发

默认 32 个 UID lease 对应最多 32 个活跃 sandbox。一个 batch 的 trajectory 总量
通常是 train_batch_size × rollout.n，再分发到各 agent worker；不能把这个总量
再乘 agent.num_workers。当前是 8×4=32，由 4 个 worker 处理。

Client 从自身 sched_getaffinity 的 CPU 列表按 slot 位置选取两个 CPU ID，server
设置初始 affinity，并降低 nice 优先级 10。CPU 数不足时索引回绕，slot 间不保证
互斥。CPU ID 是操作系统的逻辑 CPU，不保证对应独占物理核。OMP/MKL/OpenBLAS/
NumExpr 线程环境变量也设为 2。

Affinity 和线程变量用于约束普通科研代码的运行习惯，不是 CPU 配额。进程能修改
自身环境变量，并可能在宿主 cpuset 允许范围内扩大自身 affinity。本实现没有
per-agent cpuset/cpu cgroup，不能声称恶意代码绝对无法多用 CPU。

### 7.2 固定 rlimit 与存储

这些值目前写在 sandbox_server.py 中，不是已经实现的 YAML 配置键：

| 约束 | 值 | 限制对象 |
| --- | ---: | --- |
| RLIMIT_NPROC | 128 | 同一实际 UID 的进程/线程数量，包含 server |
| RLIMIT_NOFILE | 1024 | 单进程打开的 FD 数 |
| RLIMIT_FSIZE | 1 GiB | 单个普通文件大小 |
| RLIMIT_CORE | 0 | 不生成 core dump |

没有设置 RLIMIT_AS，它约束单进程虚拟地址空间，会误伤 mmap、PyTorch allocator，
也不能替代进程树的物理内存总量限制。当前节点 cgroup 挂载只读，本版没有
per-agent memory/pids/cpu cgroup backend。Tmpfs 容量只限制对应文件系统，不
限制 Python heap；单文件 1 GiB 也不限制整个 workspace 的多个文件累计大小。

### 7.3 网络与设备

CLONE_NEWNET 创建新的 network namespace，不配置外部网卡、路由或启用 loopback，
也不挂宿主 resolv.conf。普通 TCP/IP 请求不能访问外网或宿主训练服务；这不只是
清除 HTTP_PROXY。预训练模型下载会失败，当前也没有只读预热模型 cache 的专用挂载。

GPU 的实际阻断来自不挂入 `/dev/nvidia*`，并辅助设置空 CUDA/ROCR mask 和
NVIDIA_VISIBLE_DEVICES=void。重新设置 CUDA_VISIBLE_DEVICES 不会凭空创建
device node。没有已实现的 gpu_mode=env_mask 或 GPU 白名单开关。

这是共享宿主内核的 Linux 进程隔离，不是虚拟机；本版没有 seccomp、独立 IPC
namespace、聚合 RAM/磁盘配额或完整 syscall 安全审计。公开数据、系统目录和
Conda allowlist 由可信宿主管理。以上是短时科研诊断工作流的实际边界。

## 8. verl 多轮与训练 mask 如何接通

通过 actor_rollout_ref.rollout.agent.agent_loop_config_path 加载 YAML，注册
mle_agent 到 MLEAgentLoop。RLHFDataset 读取 prompt 得到 raw_prompt，代码、UUID、
task 和 reward_model 随样本进入 loop；每条采样实例独占 loop 和 sandbox。

父类 ToolAgentLoop 保留模板、工具 parser 和状态机：

```text
PENDING（初始 prompt 模板）
  -> GENERATING（模型生成 assistant token）
       -> 有工具调用：PROCESSING_TOOLS -> 拼接 observation -> GENERATING
       -> 无工具调用或达到预算：TERMINATED
```

项目主要覆写：

- run：打开 trace、建立 sandbox、带总超时调用父类，打分、清理。
- _handle_generating_state：将剩余 response 预算传给生成请求，保存本轮 assistant
  原文，避免生成预算之外的答案却拿它打分。
- _call_tool：校验参数、调用本实例 sandbox、限制 observation、记录事件。

模型明确为 Qwen/Qwen3.8-27B，与 Qwen3.5 共享结构，使用 qwen3_coder XML parser。
实际 tokenizer/parser 测试和真实模型多轮 rollout 已跑通。依赖 Qwen 正常轮次
终止行为，没有另外实现项目专属的 stop-token 协议。

模型生成 token 的 response_mask 为 1；工具 observation 及相应模板续接 token
为 0。Observation 仍作为后续上下文、占 response 预算，但不当成模型需要学习
生成的动作 token。Solution 字段不计入初始 prompt 长度，模型通过工具读取代码后，
代码文本才作为 observation 消耗上下文和显存。

## 9. Reward 的信任边界

final_answer 的输入仅为最后一次生成捕获的 assistant 文本。不能解码包含工具
observation 的整段 response 后搜索 boxed，否则读到代码/CSV 中的 boxed 也可能
被当成模型判断。

规则为：至少匹配一个 `\boxed{A}` 或 `\boxed{B}`，所有匹配到的 boxed 内容须
为同一合法答案，该轮不能含 `<tool_call>`。重复相同答案可接受；A/B 冲突、匹配
到其他 boxed 内容、缺答案或仍调用工具都无效。当前不单独剥离最后一轮 thinking，
因此该轮 thinking 中匹配到的 conflicting boxes 也会使答案无效。

合法答案与 ground_truth 相同给 1，否则给 0。Loop 直接设置
AgentLoopOutput.reward_score，由 verl 转成训练 reward，不让默认 reward manager
对混合文本重复评分。工具调用没有另加正奖励或成本惩罚。

GRPO 比较同 pair 多次采样的 reward；组内完全相同就没有这类相对优势信号。
验收除 loss 外同时检查组内 reward variance、非零 grad_norm 和 checkpoint。

## 10. 配置位置与草案差异

agent_loop.yaml 当前实际内容：

```yaml
- name: mle_agent
  _target_: src.mle_critic.src.agentic.mle_agent_loop.MLEAgentLoop
  trace_dir: ${oc.env:MLE_TRACE_DIR}
  sandbox:
    runtime_base: /tmp/mle-agent-sandboxes
    mlebench_data_root: ${oc.env:MLE_DATA_ROOT}
    conda_roots:
      - /public/hk-research/users/jiqian/miniconda3
    command_timeout_s: 120
    trajectory_timeout_s: 1200
    max_output_bytes: 65536
    max_concurrent_sandboxes: 32
    cpu_cores_per_sandbox: 2
```

可额外传 slot_timeout_s，默认 1800 秒。早期草案的 network、gpu_mode、nproc_limit、
nofile_limit、file_size_limit_bytes 没有实现为可调参数，不能只添加同名 YAML 键
就认为功能已生效。实际构造也没有 socketpair、独立 executor 和 owner 恢复步骤。

Launcher 沿用原单轮脚本的 FSDP2、TP4、SP2、gradient checkpointing 和 parameter/
optimizer offload，覆盖为 8 pair、n=4、4 workers、4K prompt + 24K response、
12 assistant turns、16000 字符 observation。完整 Hydra 参数名和命令覆盖方式
见[操作文档](MLEBENCH_AGENTIC_PAIRWISE_RL_RUN.md)。

## 11. Trace 与测试覆盖

每条轨迹生成 `<sample_uuid>-<trajectory_uuid>.jsonl`，每次写事件后 flush，
异常前的事件仍可审查。Flush 不是断电级 fsync 持久性保证。

| event | 主要内容 |
| --- | --- |
| start | sample/trajectory UUID、task、prompt、A/B 原代码 SHA-256 |
| sandbox_ready | setup_s，包含 slot 申请和启动时间 |
| assistant | 本轮原文、token 数、状态机返回状态 |
| tool | 工具名、参数、受字节限制的 result、实际返回模型的 observation |
| result | answer、ground_truth、reward、response_ids/mask、模型/observation token 数 |
| error | 上抛异常类型与文本 |
| closed | runtime_removed，表示本次 runtime 目录是否已删除 |

标签由可信 loop 在推理结束后写到 result，日志目录不挂入 sandbox。Extra_fields
只增加 trace 路径、工具次数/耗时、setup 时间和 answer，不重复放 solution。
Audit 统计工具错误、超时、有效答案、正确数、完成/清理数及 reward variance 分组。
它不读取训练日志，不能单靠 audit 证明 optimizer 已执行。

当前合计 14 项参数化测试用例：

| 文件 | 已验证内容 |
| --- | --- |
| [test_agentic_sandbox.py](../../test/test_agentic_sandbox.py)，11 项 | boxed 规则、UUID/task 路径；真实 namespace 下代码字节一致、公开数据只读、宿主路径/设备不可见、网络不可达、symlink/hardlink/继承 FD；editor；Conda/pandas；输出上限和非法 UTF-8；超时、同样本并发、setsid 后台进程清理、取消与启动失败后 lease 释放 |
| [test_agentic_loop.py](../../test/test_agentic_loop.py)，2 项 | 实际 Qwen tokenizer/parser + 确定性模型回复 + 真实 sandbox；连续工具共享文件、mask、长 observation、工具 boxed 不冒充答案、结束清理 |
| [test_agentic_dataset.py](../../test/test_agentic_dataset.py)，1 项 | 真实 selected 数据构建可复现、10 task/数量/UUID、A/B 基本平衡、代码/标签一致、split 和 prompt 信息检查 |

这些测试没有穷举草案中每一种攻击/异常组合。例如没有分别覆盖所有坏 JSON/未知
工具、所有生成服务异常、恶意扩大 affinity 或整个宿主被强杀的恢复流程。另一次
真实 32 并发 GPU 训练验证了真实模型生成与 optimizer 更新，结果如下。

<a id="smoke-20260920"></a>

## 12. 2026-09-20 真实训练验收结果

本节合入原 MLEBENCH_AGENTIC_PAIRWISE_RL_SMOKE_20260920.md 的完整验收记录。
原文件保留跳转入口，结果以本节为准。

### 12.1 配置与范围

模型 Qwen/Qwen3.8-27B，缓存 revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`。本机 8 GPU，vLLM TP4 × 2；
训练 FSDP2/SP2，parameter/optimizer offload。8 pair × 4 samples，4 agent
workers，32 sandbox，每个初始 affinity 为 2 个逻辑 CPU。

预算为 4096 prompt、24576 response token（含 observation）、12 assistant turns、
120 秒 command、1200 秒 trajectory。Smoke batch 是 train 原顺序前 8 个 pair，
全部来自 spooky-author-identification，没有按输出或 reward 筛选。本轮没有
validation，没有遍历完整 8331 条训练数据。

### 12.2 验收指标

| 指标 | 实际结果 |
| --- | ---: |
| 主训练进程退出码 | 0 |
| training/global_step | 1 |
| actor/grad_norm | 0.5661336779594421 |
| actor/pg_loss | 0.04608080070465803 |
| actor/lr | 1e-6 |
| reward mean | 0.53125 |
| 完成 / 清理的 trajectory | 32 / 32 |
| 工具调用 | 298 |
| 有效最终答案 / 正确答案 | 18 / 17 |
| 有非零 reward variance 的 GRPO 分组 | 6 / 8 |
| rollout 用时 | 328.51 秒 |
| old log probability 用时 | 53.37 秒 |
| actor update 用时 | 90.12 秒 |
| checkpoint 用时 | 48.88 秒 |
| step 总用时，不含初始化 | 530.54 秒 |
| actor 最大 allocated / reserved 显存 | 63.76 / 68.25 GiB |

最后一项是 actor 的 PyTorch 统计，不能当成 vLLM + actor 全部 GPU 进程的峰值。
完整 step 包含 rollout、reward、old log probabilities、advantage、反向传播、
optimizer 更新、保存和权重同步。

已确认 global_step_1/actor 中 model、optim、extra_state 各有 8 个非空 shard，
latest_checkpointed_iteration.txt 为 1，完整 checkpoint 约 306 GiB。标准 dump
32 行，逐事件 trace 32 份并都记录成功清理。结束后 8 张 GPU 显存回到 0 MiB，
没有活动 sandbox UID 进程，runtime 只剩可复用 UID lock 文件。

### 12.3 产物位置

以下是仓库相对路径，属于本地实验产物，不意味着全部已纳入 Git：

```text
src/verl/logs/qwen3_8-27b-20260920_085010.log
src/verl/outputs/agentic-smoke-20260920/audit.json
src/verl/outputs/agentic-smoke-20260920/traces/*.jsonl
src/verl/outputs/agentic-smoke-20260920/traces/*.md
src/verl/outputs/agentic-smoke-20260920/rollouts/1.jsonl
src/verl/checkpoints/MLEBENCH-AGENTIC-PAIRWISE/agentic-smoke-20260920/global_step_1/
src/verl/data/mle_agentic/manifest.json
```

可查看[轨迹汇总](../../../verl/outputs/agentic-smoke-20260920/audit.json)和
[一条成功判断的可读轨迹](../../../verl/outputs/agentic-smoke-20260920/traces/03fe6bd1dc0db20f57bc642850f8a20d-6860b7f0a3e04865884135b39e0bc291.md)。
模型确实用 bash/text_editor 阅读代码与数据，执行 schema、数值、代码 bug 和
小模型探针；原 solution SHA-256 可与 Parquet 字段对照，observation 的 mask 为 0。

### 12.4 本轮暴露的问题

14 条 trajectory 没有有效最终答案：8 条用尽 response token，6 条达到 assistant
turn 上限，均给 0。不能把 reward mean 0.53125 当跨任务准确率，也不能把 17/18
当成包含预算失败的整体性能；本轮仅验收单任务小样本闭环。后续优先为最终回答
预留 token/turn budget，减少重复读取代码和较重诊断。

298 次调用有 30 次工具错误，本轮均为非零 exit，包括探针代码错误、editor
越过 workspace 边界、离线模型加载失败等；server 记录 1 次命令超时。部分轨迹
仍尝试对整个小数据集做交叉验证，说明 prompt 的 tiny sample 指令不能保证完全
遵守。错误和超时反馈都已返回模型并落盘。

日志还出现 shared-memory resource tracker 的 KeyError、multiprocess 的
_recursion_count 清理异常、vLLM engine 关闭信息。已核实完整 step、checkpoint、
dump、退出码 0 和资源释放；本轮未改动这些依赖。后续出现相似日志仍需结合发生
阶段和产物判断，不能一律忽略。

### 12.5 启动时解决的兼容问题

原共享存储 TMPDIR 使 Ray Unix socket 路径超过 Linux 的 107 字节限制。Launcher
显式将 TMPDIR 和 RAY_TMPDIR 设为节点 /tmp。

Qwen3.8 缓存位于 /root/.cache/huggingface/hub，激活环境后的默认缓存可能不同。
Launcher 在未显式设缓存时识别此目录；未指定 MODEL_PATH 且找到对应 refs/main
和权重索引时，传入本地 snapshot 路径。这样也避开 vLLM 用 Hub ID 离线加载时
要求 README 等非模型文件齐全的问题，实际 checkpoint 未更换。

实现还对 observation 提前做 token 截断，防止工具模板开头丢失；降权后重设
PDEATHSIG，避免 setresuid 清除父死亡信号。前面的机制说明均已包含这些修正。

### 12.6 复现入口

从仓库根目录使用独立 run 名称，避免新轨迹混入原验收目录：

```bash
source /public/hk-research/users/jiqian/miniconda3/etc/profile.d/conda.sh
conda activate verl
HF_HUB_OFFLINE=1 RUN_NAME=agentic-repeat \
bash src/verl/my_scripts/train/mle_judge/8xh200/run_qwen3_8_27b_agentic.sh
python -m src.mle_critic.src.agentic.audit_traces \
  src/verl/outputs/agentic-repeat/traces
```

HF_HUB_OFFLINE=1 适用于已有完整模型文件的节点。数据构建、测试命令、全量训练和
参数修改见[中文操作文档](MLEBENCH_AGENTIC_PAIRWISE_RL_RUN.md)。
