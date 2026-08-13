# Schema/probe-first 主动干预：双任务 smoke 预注册

日期：2026-08-13  
状态：**结果不可见；任务、seed、协议、门槛均在生成前冻结**  
路线：Anytime MLE Search under Selectively Observable Execution Feedback  
性质：基础设施/可行性 smoke，不作方法效果或论文主结论

## 1. 主张与本次最小验证

现有 AIRA draft 虽然要求“simple first”，但仍产出一段单体脚本，常在完整 CV/训练结束后才写
`submission.csv`。这使搜索控制器在中途只能看到“无 artifact”，无法区分一个尚未完成但有希望的
候选与一个永远不会完成的候选。

本次只改变 draft operator 的 artifact contract，要求同一 Python 进程：

1. 在昂贵 CV、全量训练或推理之前，用真实训练标签和任务特征训练 candidate-specific cheap probe；
2. 原子写入且永久保留 `candidate_probe.csv`，再把相同字节原子提升为 `submission.csv`；
3. 打印带实际 SHA-256 的 `CANDIDATE_PROBE_READY`；
4. 同一进程继续完整候选，完成后原子替换 `submission.csv` 并打印 `FULL_CANDIDATE_READY`；
5. 公共 fallback 只保有效性，必须显式标为 `COMMON_FALLBACK_READY`，不算候选证据。

原 draft 的其余文本、底座模型、temperature、task、seed、算子与执行预算不变。smoke 不设 control
arm，也不比较分数优劣；它只判断 contract 能否被生成并由独立 host watcher 验真。

## 2. 冻结矩阵与资源

| 阶段 | 任务 | seed | 方法 | 单候选上限 | 并行 GPU |
|---|---|---:|---|---:|---:|
| A：agent 生成 | `tabular-playground-series-may-2022` | 861 | schema/probe draft, DeepSeek flash | `journal step_limit=2`（空 root + 1 候选）, `execution_timeout=600`, `time_limit_secs=1200` | 2 |
| A：agent 生成 | `spooky-author-identification` | 861 | 同上 | 同上 | 同上 |
| B：连续重放 | 上述两个生成节点 | 861 | 一次启动，不重启 | checkpoints=`30,60,120,240,360,600` 秒 | 2 |

- 总计：2 个 agent run + 2 个连续 replay。
- 生成由一个受审计的 Slurm allocation 内两个 `srun --exclusive` 直接调用 `dojo.main_run`；每个 entry
  独立原子记录 command hash、host 时间和真实 rc。这样不依赖当前隔离分支缺失的 `srun_pool`，也不
  混用学长工作区代码；外层作业仍固定排除禁用节点。
- 预计 20--45 分钟；常见消耗约 0.5--0.7 GPU·时，按任务硬上限计不超过约 1.0 GPU·时。
- 只使用远端既有 `.env`，不把 key 写入命令、日志、代码或 Git；不使用聊天中粘贴的 key。
- 排除节点：`projgpu7,projgpu8,projgpu33,gpu36,gpu38`；QOS 同时最多 2 GPU。
- 数据仅绑定 MLE-bench `prepared/public` 为只读；评分在进程停止后由 pristine host grader 完成。

任务在生成前按“一个结构化表格、一个文本分类且公共数据/样例均完整”选定，而不是按结果选定。
若任一生成失败或静态门禁失败，不替换 task/seed、不偷偷二次生成；保留失败证据并停止 replay。

### 冻结后的实现映射修订（候选生成前）

原冻结表把“生成 1 个候选”误写成 `step_limit=1`。代码审计与作业 `10619` 的日志证明 MCTS 在进入
搜索前已把 immutable blank root 计为 `current_step=1`；旧映射因而生成 0 个候选，并因主循环使用
`current_step <= step_limit` 在零剩余预算下空转。`10619` 在 2 个任务都只完成 public data preview、
没有调用 draft LLM、没有候选 code 或 replay manifest 时被取消，全部日志保留。

修订只把技术映射改为 `journal step_limit=2 = 1 blank root + 1 generated candidate`，并把 MCTS 的主循环
终止条件从 `<=` 改为 `<`；内部到达预算时的判断同步从 `>` 改为 `>=`。这不增加预注册的候选数、任务、
seed、模型、prompt、执行时限或裁决门。新增回归测试必须证明 limit=1 时 0 次 expansion、limit=2 时
恰好 1 次 expansion 且不会再进入空迭代，才能再次提交。

## 3. 冻结假设、指标与裁决

静态门禁（每个节点均须满足）：Python AST 可解析，包含 `candidate_probe.csv`、两个 marker、
`os.replace` 与 `os.fsync`；每个 run 必须恰有一个非空 code node。

动态 probe 合格条件（每个任务全部满足）：

- host 以单调时钟在 120 秒内捕获稳定的 `candidate_probe.csv`；
- pristine grader 返回有限分数且 rc=0；
- 与 sample submission 字节不同、预测至少一列非恒定且至少一行预测不同；
- marker 恰好一次，marker SHA 与 host snapshot 一致；
- 第一个稳定 `submission.csv` 与 probe 字节一致；
- probe 到进程结束仍存在且未被修改；没有 common-fallback marker；
- 同一进程连续运行，worker 不在 checkpoint 重启候选。

完整候选 transition 合格条件：`FULL_CANDIDATE_READY` 至多一次；若出现，SHA 必须对应 600 秒内
host 捕获的第二个或更晚的稳定 `submission.csv`，且 pristine grade 有限。

预注册裁决：

- **PASS**：2/2 probe 动态合格，且至少 1/2 有合格 full transition；
- **PARTIAL**：2/2 probe 动态合格，但 0/2 有合格 full transition；
- **FAIL**：任一 probe 在有效性、候选特异性、原子 provenance、不可变性或 120 秒门槛失败。

PASS/PARTIAL 仍不等于质量提升。只有 PASS 才允许设计后续原 prompt vs schema prompt 的独立多任务
2×2 因果对照；该对照必须另行冻结，不能复用本 smoke 调参。

## 4. 13 项长实验 pre-flight

1. **旋钮落盘核验**：新 operator 由原 `draft.yaml` 仅增加四条 contract；新 MCTS 配置只替换
   draft 路径。提交前保存 `git diff --no-index`，并用 Hydra `--cfg job`/compose 确认实际解析为
   `mcts_schema_probe`、`journal step_limit=2`（空 root + 恰好 1 个候选）、600/1200 秒及四个 DeepSeek client。
2. **便宜路径测试**：生成前运行 Python compile、worker/validator self-test、静态 extractor fixture、
   Hydra compose 和 `--dry-count`。任何一项失败均不提交 GPU。
3. **去重**：冻结两个互异 task、单一 seed；extractor 要求 task/card ID 唯一、每 task 恰一个 code
   node；所有输出目录必须不存在，禁止覆盖/续写混淆。
4. **输入分布检查**：提交前记录每任务公共文件数、唯一 sample submission、任务模态和样例行/列；
   不以此次输出调整 task。
5. **评测分层/长度控制**：不适用。本次不评 predictor accuracy、不聚合长度效应，仅报告逐任务
   contract 结果和 2/2 计数，不用均值掩盖失败。
6. **昂贵训练保存**：不适用底座训练；不微调 LLM。每个生成 code、search export hash、完整日志、
   immutable probe、每次 submission transition 和 replay workdir 均保存。
7. **泄漏检查**：容器只读绑定 public 数据；不绑定 frozen decision/test 或 private grader 路径；
   外部 grader 仅在候选停止后运行。提交前静态扫描显式 private/held-out 路径。
8. **RNG/去重顺序**：任务与 seed=861 在生成前冻结；不 shuffle、不补抽；extractor 在所有过滤前
   验证 task/seed/唯一 node，失败即 fail-closed。
9. **密钥检查**：不读取/打印 `.env` 值；push 前 filename scan、staged content scan、LFS payload
   scan 必须均为 0。学长 tarball 未脱敏前不得读取。
10. **walltime 核算**：agent 单任务 1200 秒上限、replay 600 秒上限；监控记录 host monotonic
    creation time、进程 rc、SLURM state/elapsed 和完整矩阵。
11. **训练侧 power**：不适用可行性 smoke。2/2 只是进入独立因果对照的 gate，不能估计 effect
    size 或支撑论文结论；后续 power/task 数需另做分析。
12. **退出码先捕获**：所有 shell 先 `set +e` 执行，再立刻保存 `worker_rc`/`validator_rc`，然后记录；
    禁止用后续 `echo` 的 `$?` 冒充真实 rc。
13. **扩语料前冻结采样**：本次 task/seed/code 抽取规则与 gate 随 commit 冻结；v11/v12 或后续新语料
    不参与本 smoke，也不得据输出改变样本。

## 5. 预先声明的边界

- 两任务不足以说明跨任务泛化，也不说明 schema prompt 提高最终 Kaggle 分数。
- 生成模型是否遵循 prompt 是 intervention 的一部分；失败不是“模型能力负结论”，而是该 contract
  实现尚不可用。
- 自报 elapsed 仅作诊断，主时间来自 host watcher；marker 文本、hash、artifact 和 pristine grade
  四者必须相互闭合。
- 如果 smoke PASS，下一项优先是冻结的新任务/新 seed 上 `original draft` vs `schema draft`，比较
  valid-artifact time、600 秒内有效率、budgeted best score 与最终 score/regret，而不是回到旧 HCE/TD。
