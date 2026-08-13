# FOREAGENT 官方 alignment 审计 v2 预注册（2026-08-13）

状态：**在读取任何真实 accuracy、confidence 或 gap aggregate 之前冻结**。v1 因官方发布物的
六文件 pair grid 不完全相同而按预注册规则中止，未生成 summary/CSV。v2 只根据 v1 已公开记录的
结构事实修改“哪些 pair 构成可比三次复现”，不修改统计指标、bootstrap 或主裁决门。

## 1. v1 已知且仅用于设计 v2 的结构事实

- 26 tasks、156 个固定 manifest 文件、每 task/model family 三个 release runs；
- DeepSeek 三次运行在 26/26 tasks 内 pair grid 完全一致；
- GPT run 2/3 是完整网格，run 1 在 6 tasks 合计少 8 pairs；其余 20 tasks 完全一致；
- 49 个 Google QUEST pairs 含 NaN score，跨两个模型和三次运行对称存在；
- 26 个 DeepSeek run-1 文件的 `log_index` 全为 null，但每个文件的无序 pair key 与抽取
  `ordinal` 均唯一；
- 上述结构检查不读取 `prediction`、`correct`、`confidence`，也未计算任何性能汇总。

## 2. v2 固定分析集合

1. **DeepSeek primary**：每个 task 必须有三个文件，且三者 pair key 集合完全相同；否则
   `PRIMARY-GRID-MISMATCH` 并在写结果前停止。三次完整网格的全部 pair 构成 primary base。
2. **GPT replication**：每个 task 预先取三个 release-run pair key 的交集。必须同时报告每轮
   pair 数、union、intersection、被排除的不完整三次复现 pair 数和 intersection/union 比例。
   每个 task 的比例必须至少 0.99，否则在写结果前停止。
3. 不计算 DeepSeek-vs-GPT 的 paired accuracy difference，因为两者分析网格并不完全相同。
   跨模型只检查共同 pair 的 canonical scores、`is_lower_better` 和 score 推导 winner 一致性。
4. 每个模型的 task-internal quartile/decile 都只在该模型固定的三轮 intersection 上独立定义；
   DeepSeek 因完整网格而等于其全网格。
5. per-run 表可描述每个原始文件自身的全部记录；所有三轮平均、gap 分层和主/复现裁决只使用
   对应模型的固定 intersection。

0.99 是在知道发布物缺行结构之后、读取性能结果之前设定的 replication 支持阈值；它不会改变
DeepSeek primary。GPT 仍只作为方向性复现，不能改变 primary gate。

## 3. 标签、缺失值与完整性规则

- pair key 固定为 `task + sorted(solution paths)`；`log_index` 仅作缺失/重复计数，不作主键。
- winner 与 correctness 必须从 canonical path-score mapping 和 `is_lower_better` 独立重算；
  发布物 `correct` 只用于 mismatch 审计。
- exact-score tie 不进入方向准确率和 gap quantile；NaN/Inf score pair 对两个模型、三次运行对称
  隔离，不借助发布物 groundtruth 或 prediction 恢复。
- 对 finite non-tie：非法/缺失 `prediction.best_index` 按错误计入 accuracy，禁止 complete-case
  删除；非法/缺失 confidence 不改变已可判定 prediction 的 correctness，但不进入 ECE/mean
  confidence，并使该 task/run 的 valid coverage 降低。
- 每个 DeepSeek task/run 的 valid coverage 必须至少 0.99；至少 24 个 DeepSeek tasks 的最低和
  最高 task-internal gap quartile 各至少 20 pairs。失败则 primary 为 `INSUFFICIENT-SUPPORT`。
- GPT 的同样两项支持门独立报告；失败只使 replication unsupported，不改写 DeepSeek primary。

## 4. 冻结指标与推断

沿用 v1，不作结果驱动修改：

- 先对 `model × task × pair` 三个 release-run correctness 取平均；
- primary 为 26 个 task accuracy 等权平均及 task bootstrap 95% CI；secondary 为 pair-micro，仍用
  task-cluster bootstrap；
- raw gap 桶固定为
  `[0,1e-4),[1e-4,3e-4),[3e-4,1e-3),[1e-3,3e-3),[3e-3,1e-2),`
  `[1e-2,3e-2),[3e-2,1e-1),[1e-1,3e-1),[3e-1,∞)`；
- task-internal quartile/decile 使用相同 gap 的 average-rank percentile；
- 每 task 计算最高减最低 quartile accuracy，再作 task 等权平均和 paired task bootstrap；
- bootstrap seed=`20260813`，10,000 replicates，percentile CI；
- 输出 `grid.csv`、`per_run.csv`、`per_task.csv`、`stratified.csv`、`summary.json`；结果目录 v2
  独立且拒绝覆盖。

## 5. 冻结 primary 裁决

- `LOCAL-DIFFICULTY-CONFIRMED`：DeepSeek 最低 task-internal gap quartile 的 task-macro point
  `<=0.55`，95% CI 包含 0.5，且“最高−最低 quartile”的 task-paired 95% CI 下界严格大于 0；
- `GAP-ALONE-WEAKENED`：DeepSeek 最低 quartile 95% CI 下界严格大于 0.55；
- 其余为 `INCONCLUSIVE`；支持门失败优先报 `INSUFFICIENT-SUPPORT`。

GPT 若同方向且 paired-difference CI 也严格大于 0，仅作为跨模型 replication；反向或不支持必须
完整报告。无论结果如何，本审计不推翻 FOREAGENT 的 agent-level 加速结论，也不能把 gap 当作
我方真实 sibling 失败的唯一因果解释。

## 6. 运行前验证

- 主实现与不导入主实现的独立 verifier 必须共同通过；
- 合成端到端测试必须显式包含：DeepSeek exact grid、GPT 单轮缺 pair 但交集比例 `>=0.99`、
  exact tie、NaN score、null `log_index` 和低于 1% 的 invalid prediction metadata；
- v2 代码、本文档与运行脚本先提交并通过 secret scan，再在固定 compact SHA256
  `480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe` 上运行。
