# Balanced continuation E1：真实执行冻结预注册

日期：2026-08-14。状态：**E1 已获用户批准；E2/E3 未获批准**。本文件晚于同日的预算门与
real-adapter mock 裁决，冻结首次真实执行，不改变稳定论文主线：稳定主线仍是 run-clean、decision-local
MLE-agent 搜索树数据集/benchmark 与 first-960 前瞻确认；balanced continuation 只是 gated 方法扩展，E1
本身不是方法正结论。

## 1. Estimand 与撤回边界

固定 estimand：

\[
V_H^{\pi}(c)=\mathbb{E}_{\omega}\left[\max_{1\le h\le H}U(Y_h)\mid
c,\pi_{\mathrm{cont}},\mathrm{contract}\right].
\]

节点 `c` 已执行且当前 `D_search` 分数可见；`π_cont` 固定为 valid→improve、buggy→debug，每个 transition
恰好一次 operator call、一次候选执行、零语义重试、零 SDK 重试、零 analyze call。失败、超时和 invalid
format 都是观测结果，固定最差 utility 为 `0.0`，不补跑。主标签保留 continuation utility、相对 warm start
gain，以及 `gain >= 0.01` 的 practical-success 指示。

E1 只有两个任务、每任务一个 anchor，不能检验论文的三个 primary gates，也不能据此宣称标签可靠性、预测性
或真实搜索效用显著改善。无论 E1 数字多漂亮，`primary_gate_claim_allowed=false`、`E2/E3_unlocked=false`。
E1 只回答：真实 public-only executor、fresh workspace、one-shot operator、D_search-visible/D_val-sealed evaluator
能否端到端运行，并给出不作显著性主张的初始 effect-size/失败率描述。

## 2. Outcome-blind 输入冻结

- 语料：v11，16,012 cards，SHA-256
  `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- 数据门 source commit：`acd215a96e4e1843f3fcd19c775b3c1abe6de5c6`；
- 任务固定为 `spaceship-titanic` 与 `tabular-playground-series-may-2022`；
- 每任务在 v11 非 held run、b0 train parent whitelist、结构上恰好两个 children 的候选中，按
  `(run_id,parent_id)` 排序取第一项；不读取 grade、gap、winner orientation、first-960 或 prospective outcome；
- 支持量在 outcome 前打印：前者 15 个 eligible parents/12 physical runs，后者 47/29；
- 选中端点与 frozen b0/b1/b2 的 endpoint overlap=0、physical-run overlap=0；frozen 文件不含 `run_id`，run
  仅由 hash-locked v11 endpoint identity 回填；
- 两任务源数据只读取 `train.csv` 与 `description.md`。按标签内 SHA-256、seed `20260814` 固定
  80/10/10 `D_train/D_search/D_val`；`D_test` 和 official test/private answer 从不读取；
- public dataset contract SHA-256：
  `3aedb20f34a91fbc53fde6ecc40754dde1a50f0a821bf8c5f18277603d581ace`；opaque split manifest
  SHA-256：`8539f81c5cf16799424cc91b30851b02e3887f6797f10d14999a53267733da6c`。

## 3. 固定矩阵、预算与顺序

固定矩阵：`2 tasks × 1 anchor/task × B=2 siblings × K=2 replicates × H=1 = 8 rollout jobs`；每个
rollout 先执行一次 warm start，再执行一次 continuation，共 **16 次候选执行、8 次 API operator call**。
历史中位执行时间 561 秒，加 30% 后预计 3.24 GPU·时。每次候选硬 cap 固定 600 秒，operator 240 秒，
每个 evaluator sidecar 120 秒；看到结果后不得提高 cap。每 job 1×RTX3090，array concurrency=4，排除
`projgpu7,projgpu8,projgpu33,gpu36,gpu38`。

assignment seed 固定 `20260814`，blocked order 在任何真实执行前生成。每个 `(anchor,replicate)` block 必须
同时包含两个 siblings；inclusion probability=1、order probability=1/2。每 rollout 使用新的物理 workspace；
marker 位于候选不可见的父目录，候选只挂载其 `candidate/` 子目录。

## 4. 两阶段 wall-clock gate（不按分数决策）

阶段一固定为每任务 `block_replicate=0` 的完整二-sibling block，共 4 rollout；阶段二是剩余 4 rollout。
阶段二只依赖阶段一 Slurm/job/worker/独立 verifier 全部 rc=0，绝不依赖 D_search 或 D_val 数字。阶段一的
D_val 仅写 mode-0600 sealed receipts；完整 8-rollout coverage 关闭前，任何 collector 都不得 parse sealed JSON。

阶段一工程 gate：

1. 两任务各一个完整 block，无缺 job、无 replacement；
2. 每 rollout 2 次 candidate attempt、1 次 operator call、retry=0、D_test rows=0；
3. 容器 `--containall --cleanenv --net --network none --no-home --no-mount bind-paths --no-eval`，
   public task 与 HF cache 均只读挂载，无 private path；
4. fresh workspace path/token 唯一，candidate 看不到 marker/API credential/host research filesystem；
5. worker 与不 import worker 的 commitment-only verifier 均 rc=0，sealed receipts mode=0600 且 hash 匹配；
6. 任一 PENDING paid action 没有完整 durable step manifest 时记为 ambiguous failure，自动重试和替代样本均禁止。

任一工程 gate 失败即停止剩余阶段，诚实记录失败；不删除失败产物、不换节点补样本、不扩 timeout。完整 8 个
rollout 都存在后，collection verifier 先验证 coverage/exact-K/workspace/retry，再一次性打开 16 个 D_val receipts。

## 5. E1 报告与禁止追参

必须逐 rollout 报告 raw/effective warm utility、best-within-H utility、gain、失败状态、candidate wall、API usage；
再按 sibling 聚合 K=2 mean/sample variance，并报告每任务两个 replicate block 的 sibling winner agreement。只作
描述统计，不给显著性主张，不筛掉负任务，不按结果修改 failure utility、practical delta、anchor、任务、prompt、
模型、cap 或 seed。E1 之后是否提出新的已预算实验，必须先单独给矩阵和 power/effect-size 依据并获得批准。

后续真正的三个 primary gates 保持原定义：balanced-vs-historical 标签可靠性 task-CI 下界>0；同构 head 在 fresh
physical runs 的预测性相对提升且 run/task CI 不支持负效应、至少70%任务同向；相同预算下真实 D_val
best-score/regret 至少一项 task-CI 下界>0。E1 不具备这些 gate 所需样本量。
