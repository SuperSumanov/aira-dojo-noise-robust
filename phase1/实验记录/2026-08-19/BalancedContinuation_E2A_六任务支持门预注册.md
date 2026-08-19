# Balanced continuation E2-A：六任务干预标签支持门预注册

日期：2026-08-19。状态：**结果前协议；真实 GPU/API 尚未启动**。用户已批准沿正方向继续实验，
但本实验仍须通过代码、数据、评分器和 13 项长实验预检后才能提交。论文稳定容器仍是 run-clean、
choice-set-faithful 的 MLE-agent 搜索树 benchmark；E2-A 是 gated interventional-resource 支线，不恢复旧
HCE、多保真、early-trace、conformal stop 或 TD/RL 主线。

## 1. 问题与边界

E1-Q 在 2 tasks / 2 anchors 上证明 fresh-workspace、policy-indexed matched continuation label 可以落盘，
但只有 2/8 continuation gain 为正、0/8 达到 0.01，且 warm/continuation 都只有 6/8 artifact 可评分。E2-A
只回答：把同一构造扩到任务平衡、run 平衡的 24 个真实 parent 后，标签是否有可用的有效性/质量变化与
test--retest 稳定性。它不训练 critic，不比较 search policy，不自动解锁 E2-B/E3，也不声称 continuation
提升了搜索。

估计对象固定为同一 physical run 的 exact-two siblings，在固定 Qwen one-shot operator、fresh workspace、
H=1 和相同执行契约下的 `V_1^{pi,c}(s)`。独立单位是 `(physical_run_id,parent_id)`，不是 rollout row。

## 2. 资格审计与冻结任务

资格审计只读取 v11 train identity/code、hold/frozen endpoint identity、两份既有 E1/E1-Q selection receipt，
以及每个任务公开的 `train.csv`/`description.md`；不读取 grade、gap、winner orientation、first-960、
prospective outcome、official test、official sample submission 或 private answer。

固定任务为：

1. `spaceship-titanic`：accuracy；
2. `tabular-playground-series-may-2022`：ROC-AUC；
3. `spooky-author-identification`：multiclass log loss；
4. `us-patent-phrase-to-phrase-matching`：Pearson correlation；
5. `nomad2018-predict-transparent-conductors`：两列 mean RMSLE；
6. `learning-agency-lab-automated-essay-scoring-2`：quadratic weighted kappa。

每任务按冻结 seed `20260819` 对 `(task,run,parent)` 作 SHA-256 排序，每个 physical run 至多取一个 parent，
取前四个。结果为 24 parents / 24 distinct runs / 48 exact-code-distinct siblings；逐任务 eligible run 数为
`10/27/29/10/12/10`。92 个 frozen runs、4 个 E1/E1-Q 旧 runs 与全部 frozen endpoints 均排除。

`tabular-playground-series-dec-2021` 曾进入初始资格候选，但其极小类别无法通过“不少于 20 行/stratum”的
预设 80/10/10 分层门，因此在任何 effect outcome 前被资格审计拒绝；门槛未降低。Nomad 依据纯 CSV、
12-run 结构支持和可独立实现的官方双列 mean-RMSLE 公式替代。这个 task qualification 过程必须完整报告，
不得把最终六任务冒充事前无候选筛选的总体随机样本。

## 3. 数据与评分契约

- 每任务只从已哈希锁定的 public `train.csv` 和 `description.md` 建新数据；不得打开原 competition
  `test.csv`、sample submission 或 private answer。
- 公开训练源按 80/10/10 生成 `D_train/D_search/D_val`。分类/离散目标按 exact target 分层；Nomad 按
  `formation_energy_ev_natom` 的稳定 rank decile 分层。ID 唯一性、行数、字段、每层计数与 membership SHA
  由 producer 和不 import producer 的 verifier 各自重建。
- candidate 只挂载 `D_train` 与无标签的 `D_search union D_val`；D_search 由外部 pristine sidecar 返回，
  D_val 只写 mode-0600 sealed receipt；official D_test 不物化、不挂载、不评分。
- 六个 metric 都须有第二种独立实现与固定 reference fixtures。任何 submission 必须完整覆盖生成的 public
  ID universe、字段精确、ID 不重不漏、预测 finite；不合规则进入 ITT failure，不补跑。
- raw competition score 与 raw oriented utility 原样保留。跨任务分析另用预先固定的 `[0,1]` utility：
  accuracy/AUC 原值；log loss 为 `exp(-loss)`；Pearson 为 `(r+1)/2`；mean RMSLE 为 `1/(1+loss)`；
  QWK 为 `(kappa+1)/2`。invalid/error/timeout/invalid-format 固定为 0。不得结果后改变映射。

## 4. 冻结矩阵与预算

- broad：6 tasks × 4 parents/task × 2 siblings × K=1 = 48 rollouts；
- calibration：每任务按 selection key 最小的第一个 parent，对 2 siblings 各增加一次独立 replicate =
  12 additional rollouts；
- 合计：60 rollout jobs、120 candidate execution attempts（每 rollout warm + continuation）、60 次 Qwen
  operator API calls、0 retry、0 analyze；H=1；每次 fresh workspace；
- 每 candidate hard timeout 600 秒；单 GPU/job；Slurm 最多同时 4 jobs，排除
  `projgpu7/8/33,gpu36/38`；
- E1-Q 实测线性点估计：`10.247889130908273 GPU·h`；candidate timeout 的硬上限：`20 GPU·h`。

提交分 score-blind engineering wave：先每任务一个完整 sibling block，六任务全部通过 capability、worker、
独立 receipt、credential scan 和 sealed-Dval commitment 后，剩余 assignments 才能依赖提交。wave gate 不能
读取 D_search/D_val 数值、validity 比例或 gain。任一 paid action 已写 intent 后状态不明，不自动重试或补位。

## 5. 完整性门与分析

完整性要求 60/60 assignments 有唯一 terminal receipt，120/120 candidate attempts，60/60 one-shot API
calls，0 retry/analyze/D_test read；所有 code/workspace/token/intent/step manifest/hash chain 与 source commit
一致。只有完整 coverage gate 关闭后，collector 才一次性打开 120 个 sealed D_val receipts。失败与 timeout
不删除。

逐 parent 报告两 sibling 的 ITT utility、validity、failure class、continuation-minus-warm gain 与成本；逐 task
和 parent/run 聚类报告，不给 rollout-iid 区间。六个 calibration parents 另报：

- 每 sibling 两次 replicate 的 validity agreement；
- 两 replicate block 的 sibling winner 是否一致；任一 block tie 或两 sibling 同为 failure 记为
  `uninformative`，不计作 agreement；
- raw score 与 `[0,1]` utility 的绝对 test--retest 差。

## 6. 冻结裁决门

以下门在 effect outcome 前固定，不因结果更换任务、parent、operator、timeout、metric 或追加样本：

1. **LABEL_RESOURCE_SUPPORT**：至少 5/6 calibration parents informative，其中至少 4/6 sibling winner
   一致；至少 4/6 tasks 各有不少于 3 个 parent 产生非 tie 的 sibling ITT utility；实际 candidate GPU·h
   不超过 12.5，且 continuation terminal artifact rate 不低于 0.50。
2. **HURDLE_SUPPORT**：在门 1 通过基础上，至少 4/6 tasks 的 continuation 同时出现 valid 与 non-valid，
   且至少 4/6 tasks 在 valid continuation 中存在非零 conditional-utility variation。只有该门通过，未来才可
   预注册 `P(valid) × E[utility|valid] / cost` 与 monolithic expected-utility 的比较。
3. **QUALITY_ONLY_SUPPORT**：若门 1 通过但 HURDLE_SUPPORT 因几乎全 valid 而失败，不解释为资源失败；只允许
   未来预注册 monolithic conditional-value controller，不再强行讲 hurdle。
4. **KILL**：门 1 任一条件失败，或结果被单一 task/physical run、评分器不等价、label leak、post-outcome
   repair、重试/补样本污染，则关闭 E2-B/E3；保留完整失败记录，不降门救活。

即使门 1/2 通过，E2-A 也只授权另立结果前 E2-B 训练/新-run equal-budget utility 预注册。真正的方法主张
必须来自未参与本轮选择和训练的新 physical runs 上 parent-equal top-1 与同真实执行预算 best-score/regret；
pair accuracy、Brier、calibration 或本轮 label variation 均不是最终方法胜利。

## 7. 长实验前剩余门

真实提交前仍须全部完成：独立 support verifier；六任务 split producer/verifier；六 metric 双实现 fixture；
真实 public-only warm smoke；Qwen one-token balance/capability probe；完整 Linux tests；source/container/Python/
operator/evaluator/data/config hash；精确 assignment manifest；13/13 preflight；artifact filename/content secret
scan。任一失败时 GPU/API 提交数必须保持 0。
