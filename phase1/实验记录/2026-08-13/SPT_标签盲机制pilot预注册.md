# Scoreable Prediction Tap：标签盲机制 Pilot 预注册

日期：2026-08-13
状态：**在任何本 pilot GPU replay、pristine grade 或动态结果读取之前冻结**

## 1. 问题、主张边界与文献门

本 pilot 只问：对开放式 MLE agent 已生成的程序，precision-first、语义保持的 prediction tap 能否在
不改变原始候选逻辑的条件下，把可识别的 test-facing prediction 提前物化为外部可评分 artifact。

文献重叠门固定为五项：自动插桩自由代码、截获真实中间 test prediction、重建 schema-valid artifact 并由
外部隐藏标签 grader 评分、同一 base code 的语义保持干预、把早期 artifact 用于 sibling 排序/预算。
单篇工作覆盖 4/5 即停止，3/5 即作为强基线并重写差异。冻结检索未发现达到 3/5 的单篇工作；但
mlinspect、AutoDL 与 RL-for-MLE-Agents 分别覆盖相邻部件。因此本项目**不主张 prediction interception、
中间预测评分或代码插桩本身新颖**；可辩护问题是开放式 MLE agent 的 observation mismatch，以及
safe-abstaining adapter 对反馈时延、语义等价和 search utility 的联合影响。

## 2. 标签盲选样

唯一输入是 `cards_current_v11.jsonl` 与冻结 `runsplit_holdruns_v11.json`。选择脚本只能访问
`id/run_id/task.{name,metric,higher_is_better}/lineage.parent_id/code`，明确不访问或复制 `label`、`obs`，
也不读取 `decision_clean_b*.jsonl`。排除全部 hold run。

固定三个任务：`random-acts-of-pizza`、`us-patent-phrase-to-phrase-matching`、
`petfinder-pawpularity-score`。每任务按 `(task, run_id, parent_id)` 找 sibling group；要求至少两个
非重复代码都通过 precision-first AST tap。组排序为：最大化两张 card 的最小 tap-site 数，再最小化两张
代码的最大字节数，再按 group hash；组内按 tap-site 数、代码长度、代码 hash、card id 固定选两张。
任何任务无合格组即 fail-closed，不临时换任务。

## 3. 干预、矩阵与公平契约

每张 card 三臂：`original_a`、`original_b`、`tap`，共 3 groups × 2 siblings × 3 arms = 18 executions。
两个 original 是独立同代码重复，用于测量候选自身的非确定性；tap 与 original 共享逐字相同的 base code，
只增加一个 import 和对 precision-qualified `.predict/.predict_proba/.decision_function` call expression 的
identity wrapper。wrapper 返回输入对象本身；第一次满足 public `sample_submission.csv` 行数/严格目标宽度、
numeric finite 条件的 prediction 被原子写成 immutable `candidate_probe.csv`。无法安全映射就沉默 abstain。

三臂固定：同一 production Singularity、同一 public data、同一网络策略、同一 GPU 型号、600 秒 candidate
cap、host poll 0.10 秒、checkpoints=`30,60,120,240,360,600`、同一 pristine grader。candidate 看不到
private labels、grader、grader 输出或 sibling score；所有 artifact 仅在进程停止/终止后评分。不修改或微调
底座 LLM。

每张 card 的三臂同一 node 同时启动；card 顺序固定，arm 的 manifest 顺序按三种 rotation 轮换。失败不
retry、不补代码、不换 card。

## 4. 指标与等价性

- endpoint：进程 `rc=0`，最后一个 stable `submission.csv` 与 final source signature 一致，且 pristine score
  finite；
- valid tap probe：immutable、marker hash 与 host snapshot hash 一致、未修改、pristine score finite；
- baseline evaluable：两个 original 都有 endpoint；
- 若两个 original endpoint hash 相同，tap endpoint 必须同 hash；否则 tap score 到最近 original score 的
  距离不得超过两个 original 的 score span（下限 `1e-8`）。第二种只叫 replicate-span equivalence，不能
  宣称逐字语义等价；
- feedback gain：`(median(original endpoint host time) - tap probe host time) /
  median(original endpoint host time)`；
- sibling ranking：用两个 original score 的中位数作 reference，用 tap probe score 排序，按 task 冻结方向。
  只有 3 个 group，仅描述 `k/3`，不报 p-value 或总体准确率。

## 5. Outcome 前裁决门

- K0：18/18 manifest、status、result 与代码/runtime/container/hash provenance 完整，否则 `INVALID`；
- K1：至少 4/6 cards baseline evaluable，否则 `INCONCLUSIVE`；
- K2：至少 4/6 cards 在 120 秒前产生 finite valid probe，否则 `NO_TAP_COVERAGE`；
- K3：baseline-evaluable cards 的 empirical equivalence rate ≥0.95；在本样本即必须全部通过，否则
  `SEMANTICS_KILL`；
- K4：至少 4 张 card 同时满足 baseline evaluable、equivalent、probe by 120，否则 `INCONCLUSIVE`；
- K5：上述 card 的 median relative feedback gain ≥0.25，否则 `NO_FEEDBACK_ADVANCE`。

全部通过才是 `PILOT_PASS`，仅授权设计 30–50 个独立 sibling groups、multi-task 的 powered confirmation；
不构成论文主张。ranking 本 pilot 不作 kill gate；正式批次必须预注册 random/现有 predictor baseline、
task/run clustered inference 与 search-regret 指标。

## 6. 资源与停止预算

- 18 executions × 600 秒 = 3.0 candidate GPU·h 上限；
- 单个 `3×RTX3090` allocation，6 waves，scheduler hard cap 90 分钟 = 4.5 GPU·h；
- QOS 同时最多使用 3 GPU，不占用 API 余额；排除 `projgpu7/8/33`、`gpu36/38`；
- 任一 entry infrastructure rc 非零仍等待该 wave 其余 entry，保存真实 rc，随后 fail-closed，不解读 outcome。

## 7. 13 项 preflight

1. **旋钮**：任务、选择规则、三臂、cap/checkpoint/poll、容器与全部门落盘；
2. **cheap tests**：py_compile、5 个 transform/runtime tests、worker/verifier self-test；
3. **去重**：3 个不同 task、3 个不同 parent group、6 个 card、每 card 恰三臂、base code pair hash 一致；
4. **分布**：文本分类、文本匹配、图像/表格回归分开报告，不把 18 execution 当 IID；
5. **评测分层**：coverage、baseline stability、semantics、latency、ranking 分开；
6. **保存**：manifest/audit/config/status/stdout/stderr/artifact/grade/命令/commit/container SHA；
7. **泄漏**：只挂 public data；hold run 排除；label/obs/decision test 不访问；
8. **RNG/顺序**：seed 字段、arm rotation、group/card 顺序固定，不按结果 retry；
9. **密钥**：不需要 API key；commit/push 前文件名与内容双 secret scan；
10. **walltime**：candidate 600 秒、job 90 分钟、3 GPU；
11. **power**：N=6/3 groups 仅机制 feasibility，无显著性或总体效应；
12. **rc**：candidate rc 写 result，worker/entry rc 写 status，parent wait rc 写 Slurm log；
13. **freeze**：本文、文献审计、代码、tests、manifest/audit、resolved hashes 与 git commit 在 replay 前冻结。
