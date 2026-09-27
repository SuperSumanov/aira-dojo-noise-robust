# 跨节点本地 vLLM server（proj54 两块 3090 → 同时服务 proj54 与 proj55）

本文记录怎么在 **proj54** 上用 `build/vllm/vllm.sif` 在它的两块 RTX 3090 上起一个 OpenAI
兼容的 Qwen3.8-27B 4bit server，让 **proj54 自己**和 **proj55** 同时用这一个 server 跑
MLE-bench 的 MCTS 任务，以及两端各自要改哪些配置。

它是 `LOCAL_VLLM_SERVER.md` 的跨节点版本。那篇写的是 CUHK HPC（`salloc`/`srun`/`gpu27`）上的
单节点用法，**下面这些前提在这两台机器上不成立**，照抄会踩坑：

| | LOCAL_VLLM_SERVER.md（HPC） | 本文（proj54 / proj55） |
| --- | --- | --- |
| 调度 | Slurm `salloc` + `srun` | **没有 Slurm**，`sinfo`/`squeue`/`srun` 都不存在，直接前台/`setsid` 起进程 |
| 缓存与权重路径 | `/research/d2/gds/zzchen2/...` | 节点本地盘，`/home/zjchen/...`（= `/data/home/zjchen/...`） |
| 仓库 | 共享的一份 checkout | **两台机器各有一份独立的 checkout**（`/data` 是不同物理盘，不共享） |
| server 可达性 | 只给同节点用，`--host 0.0.0.0` 但客户端走 `127.0.0.1` | proj55 要跨机器访问，客户端必须用 **proj54 的 LAN IP** |

本文所有命令都在仓库根目录 `/home/zjchen/aira-dojo-noise-robust` 执行。

## 0. 拓扑

```text
        proj54 (192.168.50.54)                        proj55 (192.168.50.55)
  ┌──────────────────────────────┐            ┌──────────────────────────────┐
  │ GPU0 3090 ┐                  │            │ GPU0..3  2080Ti              │
  │ GPU1 3090 ┘ vLLM TP=2 :8000  │◀── LAN ────│ 4 × worker                   │
  │ GPU2 2080Ti ┐ 2 × worker     │  (no proxy)│ interpreter=python           │
  │ GPU3 2080Ti ┘ (singularity)  │            │ max_parallel=4               │
  └──────────────────────────────┘            └──────────────────────────────┘
            127.0.0.1:8000                        192.168.50.54:8000
```

- server 用 `--host 0.0.0.0` 监听，proj54 走 `127.0.0.1`，proj55 走 `192.168.50.54`。
- 两台机器都**不要**用 `srun`；proj54 的任务走 `interpreter=jupyter`（singularity + superimage），
  proj55 的任务走 `interpreter=python`（直接用 conda 环境）。
- proj54 一共只有 4 张卡，server 吃掉两块 3090 后只剩两块 2080Ti，所以它的
  `launcher.max_parallel` 必须是 **2**、并且要用 `launcher.devices=[2,3]` 把 3090 排除掉
  （见第 6 节）。

## 1. 前提

- `build/vllm/vllm.sif`（vLLM 0.29.0，CUDA 13.0）与 `build/superimage/superimage.root.2026-07-macos-v1.sif`
  都已经在 proj54 上；proj55 只需要仓库 + conda 环境（它不跑容器）。
- `conda activate aira-dojo`（本文里环境在 `/home/zjchen/miniconda3/envs/aira-dojo`）。
- **每台机器的 `/etc/hosts` 里都已经有对端的记录**，可以直接用 `proj54` / `proj55` 互相 ssh：

  ```text
  192.168.50.54  proj54.cse.cuhk.edu.hk  proj54
  192.168.50.55  proj55.cse.cuhk.edu.hk  proj55
  ```

### 1.1 下载权重（只在 proj54 上做）

proj54 本地没有这份权重，先拉下来（26.9 GB，未量化部分保留 bf16，两卡 TP=2 用这份；
单卡的 `AWQ-INT4` 版本见 `LOCAL_VLLM_SERVER.md`）：

```bash
export HF_HOME=/home/zjchen/hf_cache
mkdir -p "$HF_HOME"
hf download cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4
```

实测约 4 分钟下完（走集群代理，~27 GB）。缓存落在 `/home/zjchen/hf_cache/hub/`。

### 1.2 建缓存目录

```bash
mkdir -p /home/zjchen/vllm_cache /home/zjchen/triton_home /home/zjchen/torchhome
```

注意**不要**用 `/data/...` 这种绝对路径传给容器：`singularity` 默认只 bind 了 `$HOME`
（`/home/zjchen`）、`/tmp`、`/proc` 等，容器里 `ls /data` 是不存在的。
`/home/zjchen` 和 `/data/home/zjchen` 是同一份数据，但只有 `/home/zjchen` 这条路径在容器里可见。

## 2. 在 proj54 上启动 server（两卡 TP=2）

和 `LOCAL_VLLM_SERVER.md` 第 2.1 节的参数一致，去掉 `srun` 那层（本机没有 Slurm），
换成 `setsid nohup ... &` 直接后台起：

```bash
cd /home/zjchen/aira-dojo-noise-robust
mkdir -p tmp

setsid nohup singularity exec --nv --cleanenv \
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
  --env VLLM_CACHE_ROOT=/home/zjchen/vllm_cache \
  --env TRITON_HOME=/home/zjchen/triton_home \
  --env TORCH_HOME=/home/zjchen/torchhome \
  --env HF_HOME=/home/zjchen/hf_cache \
  --env HF_HUB_OFFLINE=1 \
  build/vllm/vllm.sif \
  vllm serve cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4 \
    --served-model-name qwen3.8-27b \
    --host 0.0.0.0 \
    --port 8000 \
    --api-key sk-vllm-proj54-qwen38-27b \
    --tensor-parallel-size 2 \
    --max-model-len 131072 \
    --gpu-memory-utilization 0.95 \
    --kv-cache-dtype fp8_e5m2 \
    --limit-mm-per-prompt '{"image":0,"video":0}' \
    --max-num-seqs 6 \
  > tmp/vllm_server.log 2>&1 < /dev/null &
```

要点：

- `--tensor-parallel-size 2` 会把权重切成每卡 12.9 GiB，落到 GPU0/GPU1（两块 3090）上；
  剩下的 2080Ti 不受影响。启动日志里会有一条
  `Detected different devices in the system: ... 3090, 3090, 2080 Ti, 2080 Ti` 的 **WARNING，
  这是正常的**（机器是混插的），只要后面看到 `Model loading took 12.9 GiB` 两次即可。
- `--max-num-seqs 6` 是为「proj54 两个 + proj55 四个」并发留的；KV cache 有 54 万 token，
  远用不满。
- `> tmp/vllm_server.log` 的**重定向在宿主机 shell 里发生**，所以容器 cwd 是什么都无所谓。
- 启动成功的标志（实测）：

  ```text
  Model loading took 12.9 GiB memory and 11.511181 seconds   （两张卡各一条）
  Available KV cache memory: 8.91 GiB
  GPU KV cache size: 541,764 tokens, Maximum concurrency for 131,072 tokens per request: 4.13x
  Application startup complete.
  ```

- 从第一次写日志到 `Application startup complete.` 实测 **约 6 分钟**（12:01:57 → 12:08:07），
  其中权重加载只有 11.5 秒，其余是 torch.compile / CUDA graph capture。
- 确认在监听：

  ```bash
  ss -ltnp | grep 8000        # 0.0.0.0:8000 ... users:(("vllm",...))
  curl -s -H 'Authorization: Bearer sk-vllm-proj54-qwen38-27b' \
    --noproxy '*' http://127.0.0.1:8000/v1/models
  ```

  起 server 前记得先确认 8000 没被别的进程占了，否则 vLLM 会在
  `sock.bind(addr)` 处报 `OSError: [Errno 98] Address already in use` 然后整个退出。

## 3. .env（两台机器都要改）

`.env` 是每台机器自己的一份，`HOST_QWEN3_8_27B` 在 proj54 指本机、在 proj55 指 proj54：

proj54：

```bash
HOST_QWEN3_8_27B="http://127.0.0.1:8000/v1"
PRIMARY_KEY_QWEN3_8_27B="sk-vllm-proj54-qwen38-27b"
```

proj55：

```bash
HOST_QWEN3_8_27B="http://192.168.50.54:8000/v1"
PRIMARY_KEY_QWEN3_8_27B="sk-vllm-proj54-qwen38-27b"
```

key 的名字来自 dojo 的约定：`PRIMARY_KEY_{model_id 大写，`-`/`.` 换成 `_`}`，即
`qwen3.8-27b` → `PRIMARY_KEY_QWEN3_8_27B`（见
`src/dojo/core/solvers/llm_helpers/backends/lite_llm.py`）。`HOST_QWEN3_8_27B` 只被
`dojo/utils/local_vllm/test_litellm.py` 和 `bench_context_speed.py` 读取，真正的 solver
走的是下面第 4 节的 client 配置。

## 4. client 配置（两台机器各改一次，值不同）

`src/dojo/configs/solver/client/litellm_qwen3.8-27b.yaml`，只有 `base_url` 不一样：

proj54（本机，保持现状）：

```yaml
_target_: dojo.config_dataclasses.client.base.ClientConfig
api: litellm
model_id: "qwen3.8-27b"
base_url: "http://127.0.0.1:8000/v1"
use_azure_client: false
provider: selfhosted
```

proj55（指到 proj54）：

```yaml
base_url: "http://192.168.50.54:8000/v1"
```

因为两台机器是两份独立 checkout，这里不会互相影响。
`model_id` 必须和 server 的 `--served-model-name`（`qwen3.8-27b`）一致。

## 5. NO_PROXY（这一步是跨节点的关键）

集群所有出网流量都走 `http://proxy.cse.cuhk.edu.hk:8000`，**内网 IP 不在默认白名单里**。
实测在 proj55 上不绕代理访问会直接挂住：

```text
$ curl -s --max-time 8 http://192.168.50.54:8000/v1/models -H 'Authorization: Bearer sk-vllm-proj54-qwen38-27b'
http=000 time=8.00          # 走代理，超时
$ curl -s --max-time 8 --noproxy '*' http://192.168.50.54:8000/v1/models ...
http=200 time=0.006         # 直连，秒回
```

所以 proj54 用：

```bash
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
```

**proj55 必须把 proj54 的地址也加进去**（这是相对原始验收命令唯一的额外一行）：

```bash
export NO_PROXY=127.0.0.1,localhost,192.168.50.54
export no_proxy=127.0.0.1,localhost,192.168.50.54
```

## 7. 验证 server（两台机器各跑一次）

```bash
source /home/zjchen/miniconda3/etc/profile.d/conda.sh && conda activate aira-dojo
set -a; source .env; set +a
export NO_PROXY=...   # 见第 5 节
export no_proxy=...
python -m dojo.utils.local_vllm.test_litellm
```

两边都实测 `all checks passed`（纯文本 / `response_format=json_object` / `LiteLLMClient.query`
结构化输出三项）。proj55 的 `base_url = http://192.168.50.54:8000/v1`，结构化调用延迟
0.63s。

## 8. 跑验收任务

### 8.1 proj54（bms-molecular-translation，8 seeds，singularity）

相对原始验收命令**只加了两处**：`launcher.devices=[2,3]` 和把
`launcher.max_parallel` 从 4 改成 2（原因见第 0 节：只有两块 2080Ti 可用；
`local_gpu_pool` 会校验 `max_parallel × gpus_per_task ≤ 选中的卡数`，不改的话要么直接
报错、要么把 worker 派到被 server 占着的 3090 上）。

```bash
conda activate aira-dojo
set -a; source .env; set +a
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost

python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_mcts_dsf_medium_mle \
  'benchmark.tasks=[bms-molecular-translation]' \
  'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.draft.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.improve.llm.client=litellm_qwen3.8-27b' \
  metadata.git_issue_id=bms-molecular-translation-8seeds \
  solver.execution_timeout=7200 \
  solver.time_limit_secs=86400 \
  solver.num_children=2 \
  launcher=local_gpu_pool \
  launcher.debug=false \
  'launcher.devices=[2,3]' \
  launcher.max_parallel=2 \
  launcher.gpus_per_task=1 \
  logger.use_wandb=false
```

`interpreter` 走 exp 配置里默认的 `jupyter`（singularity + superimage），符合「这台机器用
singularity 起任务」。

### 8.2 proj55（champs-scalar-coupling，4 seeds，纯 python）

**只加了一行 `interpreter=python`**（覆盖 exp 里的 `jupyter`），`max_parallel=4` 保持不动
（4 张 2080Ti 全空），另外 `NO_PROXY` 要带上 proj54 的 IP：

```bash
conda activate aira-dojo
set -a; source .env; set +a
export NO_PROXY=127.0.0.1,localhost,192.168.50.54
export no_proxy=127.0.0.1,localhost,192.168.50.54

python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_mcts_dsf_medium_mle \
  'benchmark.tasks=[champs-scalar-coupling]' \
  'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.8-27b_proj54' \
  'solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b_proj54' \
  'solver/client@solver.operators.draft.llm.client=litellm_qwen3.8-27b_proj54' \
  'solver/client@solver.operators.improve.llm.client=litellm_qwen3.8-27b_proj54' \
  metadata.git_issue_id=champs-scalar-coupling-4seeds \
  solver.execution_timeout=7200 \
  solver.time_limit_secs=86400 \
  solver.num_children=2 \
  interpreter=python \
  launcher=local_gpu_pool \
  launcher.debug=false \
  launcher.max_parallel=4 \
  launcher.gpus_per_task=1 \
  logger.use_wandb=false
```

`interpreter=python` 用 `PythonInterpreterConfig`，不起容器，agent 生成的代码直接在
`aira-dojo` 环境里跑——所以 proj55 **不需要** superimage，也不需要 `singularity`。

如果从 proj54 远程起：

```bash
ssh proj55 'cd /data/home/zjchen/aira-dojo-noise-robust && ... python -m dojo.main_runner_job_array ...'
```

## 9. 实测（2026-09-27，proj54 + proj55）

server 侧：

| 项目 | 数值 |
| --- | --- |
| 权重显存 | 12.9 GiB / 卡（GPU0、GPU1 两块 3090） |
| KV cache 可用显存 | 8.91 GiB / 卡 |
| KV cache 容量 | **541,764 tokens**（`--max-model-len 131072` 时并发度 4.13x） |
| 启动耗时 | 约 6 分 10 秒（权重加载 11.5s） |
| 两节点 6 个 worker 全开时 | `Running: 3~4 reqs, Waiting: 0 reqs`，聚合解码 **~146 tokens/s**，prefix cache 命中率 62.6% |

运行侧：

- proj54：2 个 worker 落在两块 2080Ti 上（UUID 级 CUDA mask），
  日志 `logs/aira-dojo/user_zjchen_issue_bms-molecular-translation-8seeds/local_gpu_pool/<batch>/logs/*.attempt-1.{out,err}`。
- proj55：4 个 worker 落在 4 块 2080Ti 上，
  日志 `logs/aira-dojo/user_zjchen_issue_champs-scalar-coupling-4seeds/local_gpu_pool/<batch>/logs/*.attempt-1.{out,err}`。
- **整条 MCTS 循环跑通**（proj54，seed_1）：容器起来 → 数据概览代码执行 518s（exit code 0）
  → draft 请求（`completion_tokens=16003`，`reasoning_effort: medium`，latency 440.7s）
  → 容器执行 draft 代码报 `RuntimeError: stack expects each tensor to be equal size`
  （CTC 的 `collate_fn` 问题）→ debug operator 接手并给出修好的完整脚本
  （thinking 里准确定位到 `permute(2,0,1)` 应为 `permute(1,0,2)` 和变长 target 不能 `torch.stack`）。
- prompt 里的 `**COMPUTE**` 段显示 `1 x NVIDIA GeForce RTX 2080 Ti (11 GiB VRAM)`，
  说明 `launcher.devices=[2,3]` 的 UUID mask 生效，agent 视角里只有一张 2080Ti。
- proj54 侧 `local_gpu_pool` 是 FIFO：`max_parallel=2`，manifest 里 2 个 seed `running`、
  其余 6 个 `pending`；proj55 侧 4 个 seed 同时 `running`。
- server 侧全程 `400 Bad Request` 计数为 **0**（`reasoning_effort: medium` 被 vLLM 正常接受），
  也没有代理超时；两节点 6 个 worker 同时工作时 `Running: 3~4 reqs, Waiting: 0 reqs`。

即：`+_exp` 配置解析、两节点并发、singularity / python 两种 interpreter、跨机器 LLM 访问
都已经实测通过。剩下的只是任务本身按 24h time limit 继续跑。

## 10. 排查清单

| 现象 | 原因/处理 |
| --- | --- |
| 启动即报 `OSError: [Errno 98] Address already in use` | 8000 被占（比如之前测试用的 `python3 -m http.server 8000`），`ss -ltnp \| grep 8000` 找出来杀掉 |
| `FATAL: "python": executable file not found in $PATH` | `singularity exec` 后面直接写了 `python`，容器里在 `/usr/bin/python3`，用 `bash -lc '...'` 或 `vllm` |
| 容器里 `ls /data` 不存在 | 默认只 bind `$HOME`；缓存目录用 `/home/zjchen/...` |
| proj55 请求挂住 / 8 秒超时 | `NO_PROXY` 少了 `192.168.50.54`，请求被集群代理截走 |
| proj54 起任务报 `Pool requests 4 GPU slots ... but only 2 are selected` | `devices` 只给了 2 张卡但 `max_parallel` 还是 4，两者要对上 |
| worker 落到 3090 上 / CUDA OOM | 没设 `launcher.devices=[2,3]`，`local_gpu_pool` 默认会把 4 张卡全选进去 |
| 想清掉 server | `ps aux \| grep -E "vllm\|singularity"` 找到 `singularity exec` 的进程组，`kill -- -<pgid>`（`setsid` 起的是独立进程组） |
