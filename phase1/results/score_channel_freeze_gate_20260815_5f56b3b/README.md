# Score-channel parent/replay freeze infrastructure gate

日期：2026-08-15。状态：`VERIFIED_INFRASTRUCTURE_ONLY_REPLAY_NOT_AUTHORIZED`。
这不是新的科学结果，也没有提前打开当前 47-run cohort 的 label vault；它只把 150-run 门通过后的
parent 选择和 replay manifest 冻结过程实现为可独立复核、默认拒绝的流水线。

## 固定契约

精确 source commit 为 `5f56b3b64594c6128adfed57fcb9981caf4951b6`。新增四个相互分离的角色：

1. `score_channel_parent_selector.py` 先独立重算 `eligible_runs>=150` 和 dominant task
   share `<=0.25`；门未过时在读取 intake/vault 之前退出。门通过后只使用 `graded` 是否 finite，
   不读取代码，不计算 gap/rank/winner；每 run 按
   `SHA-256(20260813|run_id|parent_id)` 固定选择最多 2 个 parent。
2. `verify_score_channel_parent_selection.py` 不导入 producer，重新读取结构对与 vault、重建
   finite-sibling 资格和 SHA-256 顺序。对外收据不含 label 值或顺序。
3. `score_channel_replay_manifest.py` 在 parent 冻结后只读取 credential-screened blind code view，
   不打开 vault；生成固定 120 秒、4 个 1-GPU shard 的 manifest，同一 physical run 严格落在同一 shard。
4. `verify_score_channel_replay_manifest.py` 不导入 materializer，重新绑定 code SHA、parent/card identity、
   shard、replay 数和 cap 理论 GPU·h。最终仍写
   `user_matrix_and_budget_approval_recorded=false`、`replay_submission_authorized=false`。

合成验收使用 150 个 runs、5 个均衡 tasks、每 run 3 个合格 parents、每 parent 3 个同分 finite
siblings。所有 grade 刻意相同，因此选择不可能依赖 gap 或 winner；producer 固定得到 450 个 eligible
parents、选择 300 个 parents/900 个 candidates，两个 verifier 逐行重建一致。另覆盖 149-run 拒绝、
NaN、空 scoreable run、重复身份、篡改后重签 hash、覆盖写拒绝、code-view 不被 selector 打开和
同 run 单 shard。这里的 450/300/900 都是**合成测试数**，不得当作真实 cohort 估计。

## 精确远端验证

在 fresh detached worktree
`/research/d7/spc/yzyang4/worktrees/score_channel_freeze_5f56b3b_a3`、上述精确 commit 上：

- focused：`11 passed in 1.97s`；
- 完整 `phase1/tests`：`335 passed in 27.81s`；
- 环境：Python 3.11.15、pytest 7.4.3、scikit-learn 1.6.1、SciPy 1.16.2；
- 当前正式 47-run registry 被 selector 在传入一个刻意不存在的 intake root 时先行拒绝，退出码 2，
  stderr 为 `run gate has not passed or replay was already authorized`；输出目录不存在。因此本次没有
  读取真实 intake 或 label vault。
- GPU jobs=0、API calls=0、replay manifest=0、replay submission authorization=false。

坏调用完整保留：a1 checkout 被既有 LFS 404 阻断、a2 误用无 pytest 的系统 Python、a3 首次把
registry 路径少写 `/producer`。它们均发生在科学输入读取或 replay 之前；成功测试没有被覆盖，正确
47-run 拒绝调用另写 `47run_corrected.*`。`SHA256SUMS` 在下载后逐项复核全部 OK；远端产物名和内容
高置信 credential 扫描均为 0。

## 当前裁决

真实状态仍是 47/150，shortfall=103，parent 资格与真实 replay 数未知。不得用合成测试数量估预算，
不得现在打开 vault，也不得提交 GPU。达到 150 且任务占比门通过后，先运行 selector + 两个独立
verifier 并冻结真实 manifest；然后向用户报告确切 parent/replay 数与 cap 上界 GPU·h，得到矩阵和预算
明确批准后，才允许单独生成 authorization receipt 和提交 4 个 shard。

