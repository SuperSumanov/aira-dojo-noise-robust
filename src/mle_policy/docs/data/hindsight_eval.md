# Hindsight 少量案例执行对照

这个流程用于人工检查选中的重写案例：生成两个版本 → prepare → evaluate → 查看结果。
训练数据批量重写走 `hindsight.md`。这里按选中的方案逐个占用一张 GPU 执行。

## 1. 生成案例

先启动模型服务，再从仓库根目录执行：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"
GENERATION=tmp/examples/hindsight/generation
EVALUATION=tmp/examples/hindsight/evaluation

python -m mle_policy.src.data.hindsight.experiment \
  --journal /absolute/path/to/run/json/JOURNAL.jsonl \
  --case debug:1:1 --case improve:1:15 \
  --output "$GENERATION" \
  --concurrency 6
```

模型和服务地址取自原 run 中目标 operator 的 `llm.client`，密钥沿用 `.env` 的
`PRIMARY_KEY_<MODEL>` 或 `PRIMARY_KEY`。

`stage:target:donor` 的 target 和 donor 都是原 journal 中 episode 起点的 step。
`debug:1:1` 从同一条调试轨迹提炼经验；`improve:1:15` 从 step 15 的方案提炼经验，
重新回答 step 1 的原始输入。每个案例的两个版本共享同一次 hint 提炼。

```text
<generation>/
  debug-1-1-hint-only/
    metadata.json       # case、include_code、原 journal/config 绝对路径、采样参数
    trace.json          # hint 调用列表 + rewrite 的输入、参数、完整回答
    nodes.json          # 新节点及必要祖先
  debug-1-1-with-code/
    metadata.json
    trace.json
    nodes.json
  improve-1-15-hint-only/...
  improve-1-15-with-code/...
```

人工检查主要读 `trace.json`。其中 `hint` 按调用顺序保存提炼过程，`rewrite`
保存增强后的输入和新回答；`nodes.json` 保存训练时使用的原始输入和新回答。

仓库内 `src/mle_policy/test/fixtures/hindsight/run/` 是接口测试用的微型 run，
可用 `--case debug:1:1 --case improve:1:3` 检查生成格式。

## 2. Prepare：集中准备文件和清单

```bash
python -m mle_policy.src.data.hindsight.exp.prepare \
  --generation "$GENERATION" --output "$EVALUATION"
```

prepare 从生成案例的 metadata 读取原 journal 和配置，提取新程序，再加入历史对照。
一个生成目录对应同一份原 journal/config。

| 对照 | 首次执行代码 | debug 预算 |
|---|---|---|
| 生成的 hint-only / with-code | 新回答中的程序 | 最多 4 次 |
| `original-<target>` | 原提案程序，仅 debug 案例加入 | 最多 4 次 |
| `terminal-reference-<target>` | 目标 episode 的历史跑通程序 | 执行一次 |
| `donor-reference-<terminal>` | improve 来源的历史跑通程序，按终点去重 | 执行一次 |

```text
<evaluation>/
  manifest.json                    # source + runs；列出每个方案全部产物路径
  runs/<name>/
    metadata.json                  # 对应清单项：来源、历史指标、plan、各文件路径
    solution.py                    # 首次执行的程序
```

`manifest.source` 包含原 journal 和 dojo config 的绝对路径。
`manifest.runs` 中的 `solution`、`metadata`、`result`、`worker_log` 均相对评测目录。
`historical_steps`、`historical_cv`、`historical_test` 和 `historical_execution_seconds`
描述来源轨迹。prepare 每次重新写入这些文件，供下一步统一消费。

## 3. Evaluate：执行清单

取得 GPU allocation 后，在该 allocation 内运行：

```bash
export HARDWARE='One NVIDIA GeForce RTX 3090 with 24 GiB GPU memory'

python -u -m mle_policy.src.data.hindsight.exp.evaluate \
  --output "$EVALUATION" \
  --workers 2 --cpus-per-task 8 --timeout 7200 --max-debug-calls 4
```

evaluate 读取已准备好的 manifest，使用当前 `SLURM_JOB_ID` 创建 `srun --exclusive`
step。每个 worker 使用一张 GPU，负责一个方案从首次执行到 debug 结束。
`--workers` 控制同时运行的方案数，`--timeout` 是每次程序执行的秒数。
`--max-debug-calls 0` 可以只执行生成的程序及对照。

debug 沿用来源 dojo config 的模型、提示模板、memory 和采样参数；
服务地址直接沿用配置，密钥使用现有 `.env` 中的 `PRIMARY_KEY` / 按模型命名的密钥。
模型服务使用独立资源，并确保各执行节点均可访问。
`HARDWARE` 描述单个方案实际可用的硬件，CPU 线程数由 `--cpus-per-task` 设置。

本机串行执行使用 `--local --workers 1`；`--output` 也可传多个已准备的评测目录。
每次运行都会执行清单中的全部方案。

```text
<evaluation>/
  manifest.json
  results.json                     # 每个方案一行，包含历史指标与实测结果
  runs/<name>/
    metadata.json
    solution.py
    worker-0.log                   # 本次 worker 的 dojo 日志
    result.json                    # 所有执行尝试的 code、plan、输出、实测结果
    workspace-0/...                # dojo 首次执行的工作目录
    workspace-1/...                # 有 debug 时的后续工作目录
    grading/...                    # MLEBench 评分产物
```

执行尝试和 debug 历史在 worker 内存中维护，方案结束时写一个 `result.json`。
出现请求或基础设施异常时直接抛出，worker 日志用于定位原因。

## 4. 查看结果

`results.json` 直接对照以下字段：

- `first_attempt_valid`：首次程序执行是否产生有效提交。
- `resolved`：最终是否成功；`debug_calls_to_success` 是成功前调用 debug 的次数。
- `test_score`：新程序的实测分数；失败方案为 null。
- `executed_attempts`、`execution_seconds`：实际执行次数与程序执行总耗时。
- `historical_debug_calls`、`historical_cv`、`historical_test`：来源轨迹的原指标。

evaluate 完成后自动汇总已执行结果。需要重新汇总时显式运行：

```bash
python -m mle_policy.src.data.hindsight.exp.summarize --output "$EVALUATION"
```

汇总只消费完成的 `result.json`。定位具体一次尝试时读该方案的 `result.json`，
查看完整运行过程时读同目录的 `worker-0.log`。
