# 本地 vLLM server（Qwen3.8-27B 4bit）+ MLE-bench 端到端冒烟测试

本文记录怎么在一台 salloc 出来的 3090 节点上，用 `build/vllm/vllm.sif` 起一个 OpenAI 兼容的 Qwen3.8-27B 4bit server，怎么验证 dojo 的 litellm client 能调通它，以及怎么拿它跑一个 MLE-bench 任务（spaceship-titanic）做端到端测试。所有命令都在仓库根目录执行。

## 0. 一句提醒：vLLM 不能加载 GGUF

vLLM 0.29.0 已经删掉了 GGUF 支持（镜像里没有 gguf loader，`vllm serve --help` 里也没有相关选项），所以这里用的是 vLLM 能直接读的 4bit safetensors 权重。要跑 GGUF 只能换 llama.cpp，那套跟本文的命令不通用。

## 1. 前提

- 已经 salloc 好了带 GPU 的节点（例子里是 6 张 3090 的 `gpu27`）。`srun` 在这个 allocation 里起 server 和跑测试。
- 镜像：`build/vllm/vllm.sif`（vLLM 0.29.0，CUDA 13.0，transformers 5.16.1）。
- 权重在共享 HF cache 里，两份都是 cyankiwi 出的纯量化版本（没有额外的去审查/微调改动）：

  ```bash
  source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
  # 两卡用这份：AWQ INT4，非量化部分保留 bf16，26.9GB，单卡 24G 放不下
  hf download cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4
  # 单卡才用这份：AWQ INT4，21GB，能塞进 24G
  hf download cyankiwi/Qwen3.8-27B-AWQ-INT4
  ls /research/d2/gds/zzchen2/transformerscache/hub/ | grep -i cyankiwi
  ```

- 所有缓存目录都放在 `/research` 下（容器里 root 分区不可写）：
  `VLLM_CACHE_ROOT=/research/d2/gds/zzchen2/vllm_cache`、`TRITON_HOME=.../triton_home`、`TORCH_HOME=.../torchhome`、`HF_HOME=.../transformerscache`。

## 2. 启动 server

有两种起法：**两卡（TP=2，推荐）** 和 **单卡（对照）**。两卡用 AWQ-BF16-INT4 权重，能开到模型原生的 262144 上下文、解码 51 tokens/s，而且不用 `--enforce-eager`；单卡只能配小一号的 AWQ-INT4 权重，上下文 11 万出头、解码 16 tokens/s。选哪个看你能拿到几张卡（本 allocation 是 6 张，server 拿 2 张、剩下 4 张给 dojo 并发跑）。

### 2.1 两卡（TP=2，推荐）

```bash
mkdir -p tmp

srun -J vllmserve \
  --ntasks 1 \
  --gres=gpu:2 \
  --cpus-per-task=12 \
  -o tmp/vllm_%j.log \
  -e tmp/vllm_%j.err \
  singularity exec --nv --cleanenv \
    --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_CACHE_ROOT=/research/d2/gds/zzchen2/vllm_cache \
    --env TRITON_HOME=/research/d2/gds/zzchen2/triton_home \
    --env TORCH_HOME=/research/d2/gds/zzchen2/torchhome \
    --env HF_HOME=/research/d2/gds/zzchen2/transformerscache \
    --env HF_HUB_OFFLINE=1 \
    -B /research/d2/gds/zzchen2:/research/d2/gds/zzchen2 \
    build/vllm/vllm.sif \
    vllm serve cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4 \
      --served-model-name qwen3.8-27b \
      --host 0.0.0.0 \
      --port 8000 \
      --api-key sk-vllm-gpu27-qwen38-27b \
      --tensor-parallel-size 2 \
      --max-model-len 131072 \
      --gpu-memory-utilization 0.95 \
      --kv-cache-dtype fp8_e5m2 \
      --limit-mm-per-prompt '{"image":0,"video":0}' \
      --max-num-seqs 4
```

和单卡版的区别只有四处：`--gres=gpu:2` + `--tensor-parallel-size 2`、`--max-model-len` 直接开到模型原生上限 262144、去掉 `--enforce-eager`（省下的显存本来就是为了开 CUDA graph，两卡不需要牺牲它）、去掉 `--override-generation-config` 的输出上限。`--gpu-memory-utilization` 用 0.95 就够，不需要像单卡那样抠到 0.97。

### 2.2 单卡（对照）

```bash
cd /research/d2/gds/zzchen2/mle_project/aira-dojo-noise-robust
mkdir -p tmp

srun -J vllmserve \
  --ntasks 1 \
  --gres=gpu:1 \
  --cpus-per-task=6 \
  -o tmp/vllm_%j.log \
  -e tmp/vllm_%j.err \
  singularity exec --nv --cleanenv \
    --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
    --env VLLM_CACHE_ROOT=/research/d2/gds/zzchen2/vllm_cache \
    --env TRITON_HOME=/research/d2/gds/zzchen2/triton_home \
    --env TORCH_HOME=/research/d2/gds/zzchen2/torchhome \
    --env HF_HOME=/research/d2/gds/zzchen2/transformerscache \
    --env HF_HUB_OFFLINE=1 \
    -B /research/d2/gds/zzchen2:/research/d2/gds/zzchen2 \
    build/vllm/vllm.sif \
    vllm serve cyankiwi/Qwen3.8-27B-AWQ-INT4 \
      --served-model-name qwen3.8-27b \
      --host 0.0.0.0 \
      --port 8000 \
      --api-key sk-vllm-gpu27-qwen38-27b \
      --max-model-len 114688 \
      --gpu-memory-utilization 0.97 \
      --enforce-eager \
      --kv-cache-dtype fp8_e5m2 \
      --limit-mm-per-prompt '{"image":0,"video":0}' \
      --override-generation-config '{"max_new_tokens": 32768}' \
      --max-num-seqs 4
```

启动时间两卡约 4.5 分钟、单卡约 4 分钟（权重加载 35 秒）。启动成功的标志是日志里出现 `GPU KV cache size: N tokens` 和 `Application startup complete.`。

server 监听 `0.0.0.0:8000`，转发到 `--served-model-name qwen3.8-27b`。注意**计算节点的 8000 端口对登录节点不开**，从 linux5 直接 `curl http://gpu27:8000/...` 连不通（也不会被代理帮上忙）；所有测试都要用 `srun` 在节点上跑，走 `127.0.0.1:8000`。

## 3. 实测数据

### 3.1 两卡 TP=2（推荐，2026-09-12 实测）

启动日志的关键行（每张卡都一样）：

```text
Using fp8_e5m2 data type to store kv cache
Model loading took 12.9 GiB memory and 34.512766 seconds
Available KV cache memory: 8.91 GiB
GPU KV cache size: 560,445 tokens, Maximum concurrency for 262,144 tokens per request: 2.14x
Application startup complete.
```

| 项目 | 数值 |
| --- | --- |
| 权重显存（每张卡） | 12.9 GiB |
| KV cache 可用显存（每张卡） | 8.91 GiB |
| KV cache 容量 | **560,445 tokens** |
| `--max-model-len` | 262144（模型原生上限，直接开满） |
| 实测最长 prompt（并发=1） | **261,316 tokens**（再长报 400 `maximum context length is 262144 tokens`） |
| 解码速度（并发=1） | **约 51 tokens/s** |
| 首 token 延迟（864 prompt tokens） | 0.61s（热 0.52s） |
| 首 token 延迟（6,660 prompt tokens） | 3.97s（热 0.30s） |
| 首 token 延迟（100,914 prompt tokens） | 75.5s，prefill 约 1,336 tokens/s（同一 prompt 再发一次 1.08s） |
| 261k token prompt 的冷 prefill | 291s，约 900 tokens/s |
| 262144 上下文能同时跑几个请求 | 2.14 个（也就是两个满上下文请求并行） |

分析：

- 显存账很清楚：26.9 GiB 的权重被 TP=2 拆成每卡 12.9 GiB，24G 卡上每卡还剩 8.91 GiB 给 KV cache。加上 fp8 KV（约 35 KiB/token），KV 总容量直接到 56 万 token，比模型原生 262144 上限还大一倍多，所以 `--max-model-len` 可以开满，`Maximum concurrency` 还有 2.14x。
- 速度：解码 51 tokens/s 是单卡（16 tokens/s）的 3.2 倍。TP=2 理论上达不到 2 倍（每层都要 all-reduce），但这里涨得比 2 倍还多，因为它顺带把单卡被 `--enforce-eager` 拿掉的那部分补回来了——两卡的显存够开 CUDA graph，不用再牺牲它。
- `--gpu-memory-utilization` 用 0.95 就够，不需要像单卡那样抠到 0.97；`--max-num-seqs 4` 保持不变即可（真要 4 个请求都跑满 26 万上下文才需要更大的 KV）。

### 3.2 单卡（对照：cyankiwi AWQ-INT4 + fp8 KV + eager + 0.97）

| 项目 | 数值 |
| --- | --- |
| 权重显存 | 18.37 GiB |
| KV cache 可用显存 | 4.05 GiB |
| KV cache 容量 | 120,422 tokens（fp8，约 35 KiB/token，fp16 时是约 71 KiB/token） |
| `--max-model-len` | 114688 |
| 单请求最长 prompt（并发=1） | **114,507 tokens** |
| 首 token 延迟（864 prompt tokens，冷/热） | 0.87s / 0.79s |
| 首 token 延迟（6,660 prompt tokens，冷/热） | 5.75s / 0.49s |
| 首 token 延迟（100,914 prompt tokens） | 119.9s（prefill 约 842 tokens/s） |
| 解码速度（并发=1） | **约 16 tokens/s** |

说明：

- “最长 prompt”是**被 `--max-model-len` 卡住**的（超了报 400 `maximum context length is 114688 tokens`），不是被 KV cache 卡住：KV 容量 120,422 tokens 还多一点。想要更长就把 `--max-model-len` 往上加，但必须 ≤ KV 容量，否则 vLLM 直接启动失败并告诉你差多少。
- 长 prompt 的主要成本是 prefill：10 万 token 的 prompt 光 prefill 就要两分钟，之后才按 16 tokens/s 出字。agent 每轮 prompt 有很长的公共前缀，前缀缓存命中时会快很多（6.6k prompt 从 5.75s 降到 0.49s）。
- 这个模型默认开启 thinking。JSON 模式下 `content` 里只有 JSON（实测没问题）；普通文本模式下 thinking 会混在 `content` 里，需要的话可以加 `--reasoning-parser qwen3` 把它拆到 `reasoning_content`，或者用 `--default-chat-template-kwargs '{"enable_thinking": false}'` 直接关掉。

### 3.3 单卡为什么必须加 `--enforce-eager`：上下文和速度直接冲突

这张卡上权重就吃掉 18.4 GiB，剩下能留给 KV cache 的不多，而开不开 `--enforce-eager` 差 2.3 GiB，正好决定能不能上 100k。四种组合都实测过（同一个模型、fp8 KV、`--gpu-memory-utilization 0.97`）：

| 配置 | KV cache 显存 | KV 容量（fp8） | 能开的最大上下文 | 解码速度 |
| --- | --- | --- | --- | --- |
| 默认（torch.compile + CUDA graph） | 1.79 GiB | ~53k tokens | ~50k | 未测；此前另一份 W4A16 权重在 fp16 KV 下是 ~47 tokens/s |
| 只关 FlashInfer autotune | 1.79 GiB | ~53k tokens | ~50k | — |
| `--enforce-eager`（本文采用） | 4.05 GiB | 120,422 tokens | 114,688 | ~16 tokens/s |
| `--enforce-eager` + fp16 KV | 4.05 GiB | 59,837 tokens | ~49k | ~15.9 tokens/s |

两个结论：

1. 那 2.3 GiB 是 torch.compile / CUDA graph 本身的开销，关掉 FlashInfer autotune 也没用。要在 24G 卡上跑 100k 上下文，`--enforce-eager` 是必须的。
2. 慢的主要原因是 `--enforce-eager`，不是 fp8 KV cache（fp8 和 fp16 在 eager 下都是 16 tokens/s 左右）；反过来，fp8 KV 换来的是 KV 容量翻倍（120k vs 60k），是 100k 上下文的另一个前提。

所以这是硬取舍：**要 100k 上下文就得接受 ~16 tokens/s；要 ~47 tokens/s 就只能开到 ~49k 上下文**。想要两者都要，只能换更小的模型/更多的卡（比如把权重切到 2 张卡上，腾出显存开 CUDA graph）。

单卡为了凑出上下文，实际用到的手段（按收益从大到小）：

- `--kv-cache-dtype fp8_e5m2`：KV cache 从 fp16 换成 fp8，单 token 占用几乎减半，这是能上 100k 的前提。
- `--enforce-eager`：省掉约 2.3 GiB 的 torch.compile / CUDA graph 开销，代价是解码慢约 3 倍。
- `--gpu-memory-utilization 0.97`：权重占 18.4 GiB，剩下的显存全给 KV cache（0.95 会少给约 0.5GB）。
- `--override-generation-config '{"max_new_tokens": 32768}'`：给所有请求加一个输出上限。dojo 的 operator 不传 `max_tokens`（`generation_kwargs: {}`），单卡上不加这个上限的话，一个请求可以一路生成到把上下文吃满（最坏 11 万 token，按 16 tokens/s 要跑两个小时）。**两卡配置里不需要这个安全网**，因为 51 tokens/s 下就算真的生成十几万 token 也是分钟级，我们按你的要求去掉了它。

### 3.4 两卡 vs 单卡

| 项目 | 两卡 TP=2（推荐） | 单卡 |
| --- | --- | --- |
| 权重 | cyankiwi AWQ-BF16-INT4 | cyankiwi AWQ-INT4 |
| 需要几张卡 | 2 | 1 |
| 权重显存 | 12.9 GiB / 卡 | 18.37 GiB |
| KV 容量 | 560,445 tokens | 120,422 tokens |
| 最大上下文 | 262,144（实测 prompt 261,316） | 114,688（实测 prompt 114,507） |
| 解码速度 | **51 tokens/s** | 16 tokens/s |
| 10 万 token prompt 的冷 TTFT | **75.5s** | 119.9s |
| 额外需要的开关 | 无（不用 `--enforce-eager`） | `--enforce-eager`、0.97、输出上限 |

结论：两卡版本在上下文（2.3 倍）和速度（3.2 倍）上全面更好，代价是多吃一张卡。**只要在 allocation 里有 2 张空闲卡就用两卡版本**；只有单卡可用时退回单卡版本，并把 `--enforce-eager` 和输出上限加回来。

## 4. 连接测试

`src/dojo/utils/local_vllm/test_litellm.py` 用 `aira-dojo` 环境里的 litellm 做三项检查：纯文本、`response_format={"type":"json_object"}`、以及 dojo 自己的 `LiteLLMClient.query`（结构化输出，跟 solver 实际调用路径一致）。

```bash
srun -J litellmtest --ntasks 1 --gres=gpu:1 --cpus-per-task=2 \
  /usr/bin/env NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
  /research/d2/gds/zzchen2/anaconda/envs/aira-dojo/bin/python \
  -m dojo.utils.local_vllm.test_litellm
```

实测输出（节选）：

```text
[1/3] plain text completion
  content: 'We need to respond exactly "hello from vllm"...</think>\n\nhello from vllm'
  usage: Usage(completion_tokens=43, prompt_tokens=61, total_tokens=104, ...)
[2/3] json_object response format
  raw content: '{"animal":"cat","count":3,"colors":["black","white","orange"]}'
[3/3] dojo LiteLLMClient.query with a JSON schema
  parsed output: {'animal': 'cat', 'count': 3, 'colors': ['black', 'white']}
all checks passed
```

两个容易踩的点：

- **必须**设置 `NO_PROXY=127.0.0.1,localhost` 和 `no_proxy=`。这台集群所有出网流量走 `http://proxy.cse.cuhk.edu.hk:8000`，不设的话请求会被代理截走（返回 503 或者直接挂住）。
- `srun` 的 step **必须**带 `--gres=gpu:N`。这个 QoS 限制（`QOSMinGRES`）会让不带 GPU 的 step 一直 pending，最后报 `Unable to create step for job ...: Job/step already completing or completed`，看起来像 allocation 坏了，其实只是没申请 GPU。

还有一个模型行为上的坑（实测于 cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4）：dojo 的结构化调用是把 JSON Schema 追加进 system message 再要求 `response_format={"type":"json_object"}`。如果 operator 的 system message 里出现类似 "You answer with JSON only." 这种话，模型会**直接把 Schema 本身当成答案输出**（校验时报 `'animal' is a required property`，看 instance 就是那份 schema）。把 system message 换成正常口吻（比如 "You are a careful assistant. Follow the requested response format."）就正常了；真实的 draft/improve/debug operator 的 system message 是 "You are a Kaggle Grandmaster ..."，没有这个问题。`test_litellm.py` 里保留了注释说明。

## 5. 性能测试

`src/dojo/utils/local_vllm/bench_context_speed.py` 做两件事，都是并发=1 逐个请求：二分出 server 能吃下的最长 prompt，然后在几个 prompt 长度上测 TTFT 和解码速度。

```bash
srun -J vllmbench --ntasks 1 --gres=gpu:1 --cpus-per-task=4 \
  -o tmp/bench_%j.log -e tmp/bench_%j.err \
  /usr/bin/env NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
  /research/d2/gds/zzchen2/anaconda/envs/aira-dojo/bin/python \
  -m dojo.utils.local_vllm.bench_context_speed
```

实测输出（节选）：

```text
     524288 chars -> ok (105836 prompt tokens)
    1048576 chars -> FAILED
  RESULT: largest accepted prompt = 114507 tokens
  server error at the failing size: Error code: 400 - ... maximum context length is 114688 tokens ...

 prompt_tokens   TTFT (s)  total (s)  prefill tok/s  decode tok/s
           864       0.87       2.90          998.1          16.2   (cold)
           864       0.79       2.83         1090.1          16.2
          6660       5.75       7.85         1157.5          16.2   (cold)
          6660       0.49       2.59        13669.0          16.2
```

想看长 prompt 的开销，单独跑一次 10 万 token 的（`--speed-prompt-chars 500000 --runs 1 --decode-tokens 64`）：

```text
 prompt_tokens   TTFT (s)  total (s)  prefill tok/s  decode tok/s
        100914     119.85     122.59          842.0          16.5
```

上下文很大时（两卡是 262144），二分搜索每次探测都要几分钟 prefill，不划算；这时用 `--probe-chars` 直接点名几个尺寸探一次就行：

```bash
python -m dojo.utils.local_vllm.bench_context_speed \
  --probe-chars 1295000,1310000 --speed-prompt-chars 4096,32768,500000 --runs 2
```

两卡上实测（同一个命令）：

```text
    1295000 chars -> ok: 261316 prompt tokens, prefill 291.3s
    1310000 chars -> FAILED after 0.6s: Error code: 400 - ... maximum context length is 262144 tokens ...
 prompt_tokens   TTFT (s)  total (s)  prefill tok/s  decode tok/s
           864       0.61       1.29         1414.5          51.4
          6660       3.97       4.64         1676.2          51.0
        100914      75.54      76.35         1335.9          49.6
```

## 6. .env 和 client 配置

`.env` 里加了两行（litellm backend 会在 `PRIMARY_KEY_<MODEL_ID 大写>` 里找 key，`model_id` 是 `qwen3.8-27b`）：

```bash
HOST_QWEN3_8_27B="http://127.0.0.1:8000/v1"
PRIMARY_KEY_QWEN3_8_27B="sk-vllm-gpu27-qwen38-27b"
```

`127.0.0.1` 是故意的：dojo 的 srun step 跟 server 在同一台节点上，跟本地 critic server 的用法一致，换了节点也不用改 .env。

client 配置：`src/dojo/configs/solver/client/litellm_qwen3.8-27b.yaml`

```yaml
_target_: dojo.config_dataclasses.client.base.ClientConfig
api: litellm
model_id: "qwen3.8-27b"      # 必须和 server 的 --served-model-name 一致
base_url: "http://127.0.0.1:8000/v1"
use_azure_client: false
provider: selfhosted
```

## 7. 端到端测试（spaceship-titanic）

在 allocation 里（不要在登录节点另开 allocation）跑：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost

python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_mcts_dsf_mlell_accounthc \
  'benchmark.tasks=[spaceship-titanic]' \
  'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.draft.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.improve.llm.client=litellm_qwen3.8-27b' \
  metadata.git_issue_id=spaceship-titanic-8seeds \
  solver.execution_timeout=7200 \
  solver.time_limit_secs=86400 \
  solver.num_children=2 \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=4 \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

注意点：

- `launcher=srun_pool` 是用 `srun --jobid=$SLURM_JOB_ID --gres=gpu:1 ...` 在**当前 allocation** 里起 step，所以必须在 salloc 出来的 shell 里执行，也要保证 allocation 里还有空 GPU（server 占 1 张，`max_parallel=4` 需要 4 张，节点一共 9 张、我们这个 allocation 有 6 张）。
- 这份 exp 配置默认是 8 个 seed；跑起来的日志在
  `logs/aira-dojo/user_zzchen2_issue_spaceship-titanic-8seeds/srun_pool/<batch>/logs/*.attempt-1.out|.err`，
  runner 自己的日志 stdout 里能看到每个 run 的 srun PID。
- 任务容器里（superimage）执行代码、跑 CV、出 `submission.csv`；LLM 部分全部打到本地 server。

实测现象（2026-09-12，gpu27）：

- 两卡 server（2 张卡）+ 4 个 seed（各 1 张卡）刚好用完 allocation 的 6 张卡。runner 起来后 4 个 seed 立刻并发启动，容器里先做数据概览，然后同时向 server 发 draft 请求。
- server 侧：`Running: 4 reqs, Waiting: 0 reqs`，聚合解码 **约 159 tokens/s**（单请求约 40 tokens/s），KV cache 用量远低于上限。对比单卡：4 并发时聚合只有 58～60 tokens/s（单请求约 15 tokens/s），而最早那版 32k 上下文的 server 还要排队（`Waiting: 3 reqs`，`reason="capacity"`）。
- 整条 MCTS 循环跑通：draft 出代码 → 容器里执行（常有报错）→ debug operator 接手 → 再调 server。
- 这个模型的 thinking 很长：最早那版 32k 上下文时，一次 draft 就生成了 **28,224 tokens**（prompt 4,544，正好吃满 32768，被截断在代码中间），耗时 829 秒。这既是当初必须上大上下文的原因，也是现在必须上两卡的原因——同样长度的 draft 在两卡上大约 12 分钟出完，而且不会被截断。

## 8. 排查清单

| 现象 | 原因/处理 |
| --- | --- |
| `Error 803: system has unsupported display driver / cuda driver combination` | 覆盖了 `LD_LIBRARY_PATH`（见第 2 节），去掉那个 `--env` |
| `Overriding HOME environment variable ... is not permitted` | 删掉 `--env HOME=...` |
| 请求返回 503 或一直挂着 | `NO_PROXY`/`no_proxy` 没设，走了集群代理 |
| 登录节点 curl 不通 `gpu27:8000` | 正常，节点端口不对外开放，测试用 `srun` 在节点内跑 |
| `srun` 报 `Unable to create step for job ...: Job/step already completing or completed` | step 没带 `--gres=gpu:N`，被 QoS 卡住；带上 GPU 再试 |
| 结构化输出报 `'xxx' is a required property`，instance 就是那份 schema | system message 里写了类似 "JSON only" 的话，见第 4 节最后一段 |
| 单卡起 26.9GB 的 AWQ-BF16-INT4 权重 | 那是两卡专用权重，单卡请用 AWQ-INT4（21GB） |
| 想清掉 server | `scancel 13150.20`（step id 用 `squeue -s -j <jobid>` 查），或者直接 `scancel <jobid>` 结束整个 allocation |
| 缓存写不进去 | 检查 `VLLM_CACHE_ROOT`/`TRITON_HOME`/`TORCH_HOME`/`HF_HOME` 是否都在 `/research` 下 |
