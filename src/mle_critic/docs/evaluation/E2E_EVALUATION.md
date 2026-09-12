# ForeTS + Bradley--Terry critic 端到端评估

ForeTS 是基于 MCTS 的搜索 solver：每轮先让 draft/improve operator 生成多个候选代码，再调用 Bradley--Terry reward model 给候选排序，最后从排名靠前的候选中随机选择若干个执行。执行结果会继续进入 MCTS 的回传和 debug 流程。本文说明如何在同一台 Slurm 节点上启动 critic server，并运行一个 MLE-bench 任务。

## 运行前提

critic 服务和 MLE-bench 任务必须在同一节点上，因为任务通过 `127.0.0.1` 访问服务。需要准备：

- 训练好的 reward checkpoint，例如 `outputs/augmented_mle_critic/Qwen3-8B_reward_seed1/checkpoint-100`；该目录没有 `rm_meta.json`，启动时必须指定 `Qwen/Qwen3-8B-Base`。
- 可访问的 `.env`，其中包含 LLM API 和项目运行所需的环境变量。
- 两个 conda 环境：critic 使用 `Hista`，Dojo/ForeTS 任务使用 `aira-dojo`。
- 足够的 GPU。Qwen3-8B critic 会通过 `device_map="auto"` 按层切到分配给 server 的 GPU；ForeTS 的每个任务进程另外占用 `gpus_per_step` 指定的 GPU。

## 申请节点

下面的例子申请 1 个节点、6 张 GPU，并预留 6 个并行任务槽。资源数量应根据 critic 模型大小、任务数量和 `launcher.max_parallel` 调整：

```bash
salloc \
  --account=gpu \
  --qos=gpu \
  --partition=gpu_24h \
  --nodes=1 \
  --ntasks=6 \
  --cpus-per-task=6 \
  --gpus-per-node=6 \
  -w projgpu7
```

`--gpus-per-node` 是节点总 GPU 数；critic 的 `--gres=gpu:2` 会在单独的 Slurm step 中占用其中两张，任务 launcher 再使用剩余资源。不要让 critic 和任务 step 争用同一张 GPU。

## 启动 critic server

在仓库根目录执行：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate Hista
set -a
source .env
set +a
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
mkdir -p tmp

PYTHONPATH=src/mle_critic srun \
  -J criticserve \
  --ntasks 1 \
  --gres=gpu:1 \
  --cpus-per-task=4 \
  -o tmp/critic_%j.log \
  -e tmp/critic_%j.err \
  python -m src.evaluation.bradley_terry_server \
  --checkpoint outputs/augmented_mle_critic/store/Qwen3-8B_reward_seed1/checkpoint-100 \
  --base-model Qwen/Qwen3-8B-Base \
  --host 127.0.0.1 \
  --port 8765 \
  --batch-size 1 &
```

`--batch-size` 控制一次模型前向最多合并多少个请求。server 会把来自多个任务或多个客户端的请求合并；设为 `2`、`4` 等可以提高吞吐，但显存随 batch 中最长输入和 batch size 增加。设为 `1` 最省显存，也最适合第一次验证。

启动日志应出现类似内容：

```text
[rm_server] loaded ... (max_len=16384, task_cond=True, batch_size=1)
[rm_server] listening on 127.0.0.1:8765
```

server 内部使用 HTTP 线程接收请求、队列保存请求、单个后台 worker 执行模型推理。多个请求不会启动多个同时进行的模型 forward；worker 最多等待约 10 ms 收集一批请求，统一前向后逐个返回。请求失败时返回 HTTP 500，ForeTS 会按 `critic_max_attempts` 重试。

可以先检查端口是否已监听：

```bash
curl -sS -X POST http://127.0.0.1:8765/score \
  -H 'Content-Type: application/json' \
  -d '{"task":"us-patent-phrase-to-phrase-matching","code":"print(1)"}'
```

成功响应是 `{"score": ...}`，其中 score 是 reward model logit 的 sigmoid。server 默认从 `rm_meta.json` 读取 `max_len` 和 task conditioning；没有该文件时使用 `max_len=16384`、`head_frac=0.25`、`task_cond=true`。server 不接受预算 conditioning 参数。需要更长输入时，应在 checkpoint 中提供正确的 `rm_meta.json`，或修改 server 的配置逻辑；ForeTS 请求还会先把代码截到 40000 个字符。

## 运行 ForeTS

另开一个 shell，仍然位于同一个节点：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
set -a
source .env
set +a
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost

python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_forets_dsf_mle \
  'benchmark.tasks=[us-patent-phrase-to-phrase-matching]' \
  'solver/client@solver.operators.analyze.llm.client=litellm_minimax-m3' \
  'solver/client@solver.operators.debug.llm.client=litellm_minimax-m3' \
  'solver/client@solver.operators.draft.llm.client=litellm_minimax-m3' \
  'solver/client@solver.operators.improve.llm.client=litellm_minimax-m3' \
  metadata.git_issue_id=us-patent-phrase-to-phrase-matching-4seeds \
  solver.execution_timeout=3600 \
  solver.time_limit_secs=39600 \
  solver.num_children=8 \
  solver.critic_host=127.0.0.1 \
  solver.critic_port=8765 \
  solver.critic_max_attempts=5 \
  solver.critic_top_k=1 \
  solver.num_children_to_choose=1 \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=5 \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

`solver.num_children=8` 表示每次扩展最多生成 8 个候选；`critic_top_k=4` 只保留 critic 排名最高的 4 个；`num_children_to_choose=2` 从这 4 个中随机选 2 个实际执行。配置必须满足 `num_children_to_choose <= critic_top_k <= num_children`。

当前 ForeTS 的 critic 请求流程是：每个候选 node 生成完成后向 `/score` 发送 `{task, code}`；所有候选评分完成后排序和抽样；未选中的候选写入 journal，选中的候选执行并参与回传。critic 只影响候选选择，代码执行、错误 debug 和最终任务评分仍由 Dojo 原有流程负责。

如果当前主要在debug，建议使用一个较轻的任务和一个免费的模型endpoint，以免浪费时间和credit。

## 资源和并发关系

这里有两层并发：ForeTS 在一次扩展中并发生成多个候选；当前 `_query_critic` 使用同步 `urllib`，因此同一个 ForeTS 进程内的 critic 请求实际会逐个发送。server 用 `batch-size` 控制来自多个任务或客户端的请求在一次模型前向中的数量。`launcher.max_parallel` 控制同时运行的任务数，`launcher.gpus_per_step` 控制每个任务使用的 GPU 数。若 4 个任务同时运行、每个任务一次产生 8 个 child，server 的队列可能持续积压 32 个请求；这不会并发执行 32 次 forward，但会增加等待时间。实际使用时先固定 `max_parallel=1` 验证流程，再逐步提高并发。

## 日志、结果和常见问题

critic 日志在 `tmp/critic_<jobid>.log` 和 `tmp/critic_<jobid>.err`。ForeTS/Dojo 的日志和输出目录由 launcher、实验配置和 logger 设置决定；`export_search_results: true` 时会保存搜索树或节点结果，最终任务结果由 `dojo.main_runner_job_array` 的输出记录。

- 连接失败或 HTTP 500：确认 server 与任务在同一节点、端口为 8765、`NO_PROXY` 已设置，并查看 critic error 日志。
- checkpoint 找不到底座模型：原始 Trainer checkpoint 没有 `rm_meta.json` 时必须传 `--base-model`。
- 显存不足：减少 server 的 `--batch-size`，减少 ForeTS 的 `launcher.max_parallel`，或给 server 更多 GPU；`solver.num_children` 只影响候选数量和请求量，不会改变单个请求的上下文上限。
- server 启动后任务立即重试：先用上面的 curl 发送一个请求，确认返回 JSON，再检查任务是否能解析到 `solver.critic_host` 和 `solver.critic_port`。

## 与离线 reward 评估的区别

离线脚本评估固定的 better/worse pair，输出 pair accuracy；ForeTS 是端到端搜索，critic 的分数只用于搜索过程中的候选筛选，最终应看任务执行结果和搜索日志。两者使用同一个 checkpoint 时，离线 pair accuracy 不能直接换算成 ForeTS 的任务成功率。
