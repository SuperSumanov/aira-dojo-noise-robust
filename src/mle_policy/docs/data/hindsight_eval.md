# Hindsight 重写结果评估

这套工具位于 `src/mle_policy/src/data/hindsight/exp/`，从已生成的 hindsight 代码出发，
执行代码、在失败时调用 dojo debug、最后用 MLEBench 官方 grader 得到测试分数。

模型服务启动和 hindsight 重写生成见 [hindsight.md](hindsight.md)。评估工具只连接已有服务，
使用来源运行的 dojo 配置、容器、debug 提示模板和祖先记忆。

通常只需要运行一次 `evaluate`。入口会先检查每个 `--output` 目录：

1. **没有 `manifest.json`**：自动调用 `prepare`，扫描生成结果、准备代码和对照方案，写出方案清单。
2. **已有 `manifest.json`**：直接使用该清单，再根据各方案的 `attempt-N.json` 判断哪些需要继续执行。
3. 为待处理方案启动 worker；每个 worker 串行完成一条执行与修复链。
4. worker 全部结束后，为每个目录生成 `results.json` 和 `results.md`。

`source.json` 和生成结果需要调用方提前准备；`manifest.json`、`runs/` 和结果文件由评估工具生成。

## 1. 准备评估目录

### 手动配置来源，放入生成结果

每个评估目录对应一份原始搜索日志，可以包含多个 Debug 或 Improve 案例：

```text
<output>/
  source.json
  generation/
    debug-1-1-hint-only/
      diagnostics.json
      nodes.json
      hint.md
      ...
    debug-1-1-with-code/
      ...
    improve-1-15-hint-only/
      ...
```

生成时把 `hindsight.experiment` 的 `--output` 指向这里的 `<output>/generation`；
如果已经在别处生成，也可以把对应结果目录复制到这里。生成阶段的 hint、提示词和完整回答留在原目录。

**`source.json` 需要手动创建，每个评估目录一份。** `hindsight.experiment` 和 `evaluate`
都不会替你生成它。两个字段应指向产生这些重写结果的同一份原始运行：

```json
{
  "journal": "原始运行目录/json/JOURNAL.jsonl",
  "config": "原始运行目录/dojo_config.json"
}
```

`journal` 用于还原原始方案、历史修复链和终点对照；当前读取格式是每行含 `data` 的
`json/JOURNAL.jsonl`，而非每行直接是节点的 checkpoint journal。
`config` 用于创建执行容器、定位任务数据和配置 debug 模型。这里的路径相对于运行命令时的
仓库根目录，也可以使用绝对路径。虽然生成结果的 `diagnostics.json` 也记录了 `source_journal`，
当前 `prepare` 仍以手动配置的 `source.json` 为准，配置时应确认两者对应同一份来源。

配置中的 public 数据、容器镜像和 debug 模型均须在当前环境可用。先进入仓库根目录并激活环境：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
```

### 首次运行时，prepare 具体做什么

`prepare` 依次处理当前评估目录下匹配 `generation/*/diagnostics.json` 的文件，按路径排序读取。
每个这样的文件代表一个重写版本，只扫描这一层子目录：

1. 读取 `diagnostics.json` 的 `case`，拆成阶段、目标起点和经验来源起点。
   例如 `improve:1:15` 表示把起点 15 后续方案的经验用于重写起点 1；`debug:1:1` 表示吸收起点 1 自身修复链的经验。
2. 读取同目录 `nodes.json` 的最后一个节点，取其 `code` 和 `plan`。
3. 根据 `include_code` 记录版本：`false` 对应 `hint-only`，`true` 对应 `with-code`。
4. 从原始 journal 补齐对照方案、历史分数和节点来源，将所有方案写入 `runs/` 和 `manifest.json`。

没有 `diagnostics.json` 的目录不会加入清单；找到它后，若 `nodes.json` 缺失或字段不完整则直接报错。
每个已生成的版本独立加入清单，`prepare` 不强制一个案例必须同时具备两个版本。

**重写方案的名称直接使用生成结果的子目录名。** 这个名称由生成工具按以下规则构造，
`prepare` 读取 `case` 和 `include_code` 记录含义，但不会重新拼接或校验目录名：

```text
<阶段>-<目标起点>-<经验来源起点>-<版本>

debug:1:1    + include_code=false → debug-1-1-hint-only
improve:1:15 + include_code=true  → improve-1-15-with-code
```

生成结果的目录名会成为 `manifest.json` 中的 `name`，也成为 `runs/<name>/` 的目录名，
建议保持生成工具原有命名。`prepare` 另外生成以下对照名称：

| 方案名 | 取哪份代码 | 何时加入 |
|---|---|---|
| `original-<目标起点>` | 目标起点的原始代码 | 目标参与 Debug 案例时 |
| `terminal-reference-<目标起点>` | 目标起点沿历史 debug 链跑通的终点代码 | 每个目标起点 |
| `donor-reference-<来源终点>` | Improve 经验来源沿历史 debug 链跑通的终点代码 | 该终点还未作为目标终点对照加入时 |

注意第二行使用的是目标**起点**编号，第三行使用的是来源**终点**编号；具体代码节点看
`metadata.json` 的 `source_step`。共用目标或来源终点的对照会复用，不重复执行同一份终点对照。

准备完成后的主要文件：

```text
<output>/
  source.json                      # 调用方手动配置
  generation/...                   # 已有重写结果
  manifest.json                    # prepare 生成的方案清单与来源信息
  runs/<方案名>/
    metadata.json                  # 该方案的来源和历史指标
    attempt-0.py                   # 从生成结果或原 journal 提取的首次执行代码
```

此时还没有 `attempt-0.json`，因为 `prepare` 只准备代码，不执行或评分。
通常直接运行 `evaluate` 即可；如果想先检查清单，可以单独执行：

```bash
python -m mle_policy.src.data.hindsight.exp.prepare --output <output>
```

已有 `manifest.json` 时，`evaluate` 不会重新扫描 `generation/`。新增生成结果后，需要显式重跑
`prepare` 更新清单；同名 `attempt-0.py` 内容一致时保留已有执行记录，内容不同时报错。
这一步会重写清单和 metadata，准备更换来源或同名代码时，使用新的评估目录更清楚。

## 2. 运行完整评估

### Slurm 批量执行

先取得评估用的 GPU allocation，再在该 allocation 内运行：

```bash
export HINDSIGHT_API_KEY='<模型服务密钥>'
export HARDWARE='One NVIDIA GeForce RTX 3090 with 24 GiB GPU memory'

python -u -m mle_policy.src.data.hindsight.exp.evaluate \
  --output tmp/examples/hindsight/exp \
  --base-url http://模型服务器地址:8000/v1 \
  --workers 2 \
  --cpus-per-task 8 \
  --timeout 7200
```

- 默认并行两个 worker，每个使用独占的一张 GPU、8 个 CPU；allocation 至少需要两张 GPU 和 16 个 CPU。
- 工具用 `SLURM_JOB_ID` 在当前 allocation 内创建 `srun --exclusive` step，不自行提交新作业。
- 一个 worker 负责一条完整链：执行 → 失败时 debug → 执行修复代码，直到有效提交或用完四次修复。
- `--timeout` 是每次代码执行的秒数。allocation 要覆盖整条链的训练、评分和模型推理时间。
- debug 的模型名称、生成参数和提示模板来自 `source.json` 指向的配置；`--base-url` 只覆盖服务地址，省略时沿用原配置。
- 设置 `HINDSIGHT_API_KEY` 时，用它作为 debug 服务密钥；未设置则使用 dojo 原有的 `PRIMARY_KEY` / 按模型命名的密钥环境变量。
- `HARDWARE` 应描述每个 solution 实际可用的资源。CPU 计算库线程数与 `--cpus-per-task` 一致。
- debug 模型服务需要独立资源，并能被所有执行节点访问；`127.0.0.1` 只适用于服务与 worker 在同一节点。
  评估所分配的 GPU 用于 solution 训练，应与模型服务 GPU 分开。
- 本地模型服务需要绕过 HTTP 代理时，将其主机地址加入 `NO_PROXY` 和 `no_proxy`。

### 当前 GPU 上串行执行

已有 GPU 环境中可以直接运行，不经过 `srun`：

```bash
python -u -m mle_policy.src.data.hindsight.exp.evaluate \
  --output tmp/examples/hindsight/exp \
  --base-url http://模型服务器地址:8000/v1 \
  --local --workers 1
```

本地模式要求一个 worker，由调用方隔离当前进程可见的 GPU。

### 一次评估多个搜索日志

同一个入口接收多个评估目录，共享 worker 数量限制，各自保存来源、修复链和汇总：

```bash
python -u -m mle_policy.src.data.hindsight.exp.evaluate \
  --output \
    tmp/examples/hindsight/exp/additional-1102/seed-2 \
    tmp/examples/hindsight/exp/additional-1102/seed-3 \
    tmp/examples/hindsight/exp/additional-1102/seed-4 \
  --base-url http://模型服务器地址:8000/v1 \
  --workers 2
```

目录名称和 seed 数量由调用方决定。生成案例的选择和生成调用由 `hindsight.experiment` 负责，
评估入口统一处理已完成的生成结果。

### 并发如何分配

主进程把所有 `--output` 的待处理方案合并成一个任务列表，使用
`ThreadPoolExecutor(max_workers=workers)` 同时管理最多 `--workers` 个子进程。
这里的线程负责启动和等待 worker，不在线程里直接并发训练模型。

Slurm 模式中，每个子进程通过一个 `srun --exclusive` step 启动，同一条链始终由它处理：

```text
主进程：扫描清单 → 合并待处理方案 → 最多两个并发 worker → 全部结束后汇总
                                ├─ worker A：执行 A0 → debug A1 → 执行 A1 → ...
                                └─ worker B：执行 B0 → 成功 → 领取下一条链
```

因此 `--workers 2` 是**所有目录合计最多两条链**，而非每个目录两条，也非同一方案同时跑两次。
一条链里的执行与 debug 严格串行；两条不同链可以一条训练、另一条请求 debug 服务。
worker 请求 debug 服务时仍持有它的 Slurm GPU/CPU 资源，不会把训练 GPU 暂时让给下一条链。
debug 服务的请求也可能随 worker 并发，模型服务需要承受相应并发量。

任务按输入目录顺序及各自 manifest 中的顺序进入队列，不按案例得分优先调度。
GPU 或 CPU allocation 不足时，`srun` 可能等待资源，增加 `--workers` 不会自动获得额外 GPU。
本地模式也使用子进程，但不加 `srun`，限制 `--workers 1`，由调用方控制 GPU 可见性。

## 3. 从头执行和断点续跑

### 判断依据：attempt-N.json，而不是工作目录是否存在

`attempt-0.py` 是首次执行代码，`attempt-0.json` 是这次执行**完成后**的结果记录。
`attempt-1.py/json` 表示第一次 debug 后的代码与执行结果，以此类推。

主进程的 `pending_runs` 按方案依次检查 `attempt-0.json` 到 `attempt-4.json`：

- 遇到 `valid=true`，这条链已成功，不启动 worker。
- 遇到第一个缺失的结果文件，将这条链交给 worker；缺失文件对应代码尚未运行，或前次运行被中断。
- 终点对照已经执行但失败，或四次修复后的执行仍失败，停止自动续跑，交给汇总标记失败状态。

worker 拿到方案后先获取该目录的 `chain.lock` 文件锁，再从 attempt 0 开始顺序检查。
检查已有结果只读取缓存，不会把每个历史 attempt 都重新训练一遍。

| 当前文件状态 | worker 行为 |
|---|---|
| 有 `attempt-0.py`，无 `attempt-0.json` | 首次执行代码，完成评分后写 `attempt-0.json` |
| `attempt-0.json` 的 `valid=true` | 结束；通常主进程已跳过这条链，重复 worker 进入时也会在这里停止 |
| attempt 0 失败，无 `attempt-1.py` | 用 attempt 0 的代码和报错调用 debug，写 `repair-1.json`、`attempt-1.py`，再执行并写 `attempt-1.json` |
| attempt 0 失败，已有 `attempt-1.py`，无 `attempt-1.json` | 复用修复代码，直接执行 attempt 1，跳过生成该次修复 |
| attempt 1 也失败 | 同样处理 attempt 2，直到首个有效提交或 attempt 4 执行结束 |

每次执行复用 dojo 容器和官方 grader。正常完成后先保存输出日志，再原子写入
`attempt-N.json`；其中包含 `valid`、`test_score`、代码 SHA-256、timeout、执行输出和作业信息。
`valid=true` 要求正常退出、未超时、通过官方提交格式检查，并得到有限数值的测试分数。
分数低也算有效结果，成功后立即停止该链。

### 中断后怎么继续，什么时候重开目录

重新执行相同的 `evaluate` 命令即可续跑。成功链直接跳过；已落盘的失败记录和修复代码继续使用。
文件锁避免重复 worker 同时修改同一条链；批量评估通常只需启动一个主进程。
`workspace-*`、`submission.csv` 或执行日志的存在不代表完成：没有 `attempt-N.json` 时，
会从同一份代码重新执行该 attempt，不会从模型训练 checkpoint 自动恢复。
工作目录名是 `workspace-<attempt>-<SLURM_JOB_ID>/`，本地无作业号时使用 `local`；
同一作业内重试会使用相同工作目录，换作业后使用新的目录。

worker 读取已有执行结果时校验代码哈希和 timeout，不匹配就报错。
主进程已判定成功而跳过的链不会进入这一步；缓存也没有完整比较 CPU、模型服务和任务配置。
更换代码、运行设置，或希望重新采样一次独立实验时，创建新的评估目录，放入对应的
`source.json` 和 `generation/`。只换作业或重复原命令表示续跑，不表示从头重测成功方案。

重写代码和 Debug 原始起点最多修复四次，每次都保留原代码、报错和模型回答。
终点对照只执行一次，失败时报告 `reference_failed`，保持比较用的代码不变。

四次修复用尽仍失败的链标记 `repair_budget_exhausted`，最终分数留空。
Jupyter kernel readiness 失败单独记录为基础设施故障，不写该次 `attempt-N.json`，也不调用 debug；
该 worker 停止，检查环境后重跑相同命令。debug 调用本身失败时也会停止 worker，保留已有执行结果供续跑。
一个 worker 失败不会主动取消其他链；正常收尾时，主进程等待全部 worker 结束并汇总，
有 worker 异常或方案未解决就以非零状态退出。整个作业被强制终止时可能来不及汇总，
可单独从已有完整执行记录生成汇总：

```bash
python -m mle_policy.src.data.hindsight.exp.summarize --output <output>
```

## 4. 查看文件与结果

生成文件位于 `<output>/generation/<方案名>/`：

| 文件 | 内容 |
|---|---|
| `hint.md`、`hint_trace.json` | hint 及其提取过程 |
| `original_prompt.json`、`rewrite_trace.json` | 原始提示词与重写调用记录 |
| `generated.md`、`nodes.json` | 完整生成回答和结构化代码 |
| `diagnostics.json` | 案例编号、版本及生成诊断 |

执行文件位于 `<output>/runs/<方案名>/`：

| 文件 | 内容 |
|---|---|
| `metadata.json` | 方案来源、对照关系和历史指标 |
| `attempt-0.py` | 首次执行的代码 |
| `attempt-N.py`、`repair-N.json` | 第 N 次修复的代码、方案和模型调用记录 |
| `attempt-N.json` | 是否有效、实测测试分数、耗时、代码哈希、作业信息和完整输出 |
| `attempt-N.log` | 执行输出和报错 |
| `chain-worker.log` | 完整执行与修复链的进程日志，多次续跑追加写入 |
| `workspace-N-<job_id>/` | 执行工作目录及生成的 `submission.csv` |
| `grading/grading_report.json` | 官方评分报告 |
| `infrastructure-failure-*.json` | 基础设施故障记录 |

每个评估目录的 `results.json` 和 `results.md` 汇总各方案的首轮有效性、执行次数、
达到有效提交的 debug 次数和测试分数。需要合并多目录结果时，按各目录 `results.json` 中的方案来源对齐。
`metadata.json` 中的历史指标用于对照，新执行分数以 `attempt-N.json` 和 `results.json` 为准。
`results.md` 由汇总程序生成，手工撰写的分析报告单独保存。

测试位于 `src/mle_policy/test/test_hindsight_eval.py`：

```bash
python -m pytest src/mle_policy/test/test_hindsight_eval.py -q
```
