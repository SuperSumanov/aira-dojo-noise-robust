# Randomized sibling logging v1：预算守恒设计冻结

日期：2026-08-14。状态：**协议与 synthetic contract only；未获 production policy 变更授权，不启动真实
run/GPU/API，不读取 0812、frozen 或 first-960 outcome。** 稳定主线仍是 physical-run-clean、
choice-set-faithful benchmark 与 first-960 prospective confirmation；本协议只是 gated interventional
resource 备选。

## 1. 为什么不是再训练一个 critic

E1-Q 证明 fresh-workspace matched continuation label 可以落盘，但只有 2 tasks / 2 anchors，continuation 与
warm 都只有 6/8 scored artifacts，且 0/8 gain 达到 0.01。近期直接竞品又已覆盖 code-tree revision reward、
tree-derived process value、same-prefix sibling supervision、validity/repair-aware reward 与 uncertainty-guided
allocation。因此 hurdle/listwise/uncertainty 的名称不是可防守 novelty；当前真正缺的是能识别真实 MLE sibling
future value 的、policy/propensity 明确的新数据。

## 2. estimand 与实验单位

对 physical run `u` 中同一 parent `p` 的两个真实 siblings `s0,s1`，固定 operator policy `pi`、执行契约
`c` 与 continuation horizon `H=1`：

`V_1^{pi,c}(s) = E[Y | do(start=s), pi, c, H=1]`。

实验单位是 `(physical_run_id,parent_id)`，不是 rollout row。每个 broad parent 对两个 sibling 各运行一次
continuation；calibration parent 对两个 sibling 各运行两次。每次 continuation 使用独立 fresh workspace、固定
one-shot operator、0 retry。失败、timeout 与 invalid submission 是 estimand 的一部分，不补跑、不 complete-case
删除。

未来 production sibling 自身已经有不可变执行/评分 receipt，所以 sidecar 不重复跑 warm baseline；本轮新增预算
只计 continuation candidate execution。若生产接口不能提供 hash-locked sibling receipt，则该 parent 不得进入
assignment，而不是临时加 warm rerun 改 estimand。

## 3. outcome-blind 输入契约

assignment producer 只接受严格 JSONL，每行一个预先排程的 exact-two parent，字段固定为：

- `schema_version/task/physical_run_id/parent_id/generation_started_at_utc/source_sha256`；
- `operator_contract_sha256/evaluator_contract_sha256`；
- `sibling_ids` 与同序 `sibling_code_sha256`，长度都必须恰为 2、值唯一；
- `source_sibling_receipt_sha256`，与 siblings 同序；
- `upstream_selection_probability_attested` 与 `upstream_selection_receipt_sha256`：production scheduler 在任何
  outcome 前记录的 parent 纳入概率及其 receipt hash；assignment 层只传递这项 attestation，不冒充已独立重建；
- `displaced_candidate_execution_slots`：该 parent 从正常 production 账本中预先扣除的槽位。

任意层级出现 `grade/label/score/reward/metric/prediction/stdout/runtime/self_report` 字段，或内容出现凭据形状，
必须在 assignment 前 fail closed。输入不含 code bytes，只含 identity/hash；producer 不接受 outcome 路径。

另一个严格 JSON config 固定：公共 seed、每任务 calibration parent 数、H、每 candidate timeout、source commit、
operator/evaluator/policy hash。真实运行前 config 与输入都必须进入 Git commit；当前只做 synthetic fixtures。

## 4. 随机化与 propensity

1. 所有输入 parent 都进入 broad K=1；其 inclusion propensity 继承
   `upstream_selection_probability_attested`，assignment 不事后筛 parent。对 scheduled pool 以外的总体作因果
   外推前，必须另有 scheduler verifier 从完整 opportunity list 重建 selection receipt；本模块不声称已做到。
2. 每任务按独立 hash stream 对 parent 作无放回随机排列，前 `c_t` 个进入 K=2 calibration；条件 propensity
   为 `c_t / n_t`。`c_t=0` 时为 0，`c_t>n_t` 直接失败。
3. 每个 `(parent,replicate)` block 内两个 sibling 的执行顺序用另一独立 hash stream随机化；给定 block 的每个
   sibling order propensity 固定为 1/2。
4. rollout seed、block ID、assignment ID 均由 protocol/config/input identity 独立哈希派生；重复 seed/ID
   失败。不同随机化用途使用 domain-separated hash prefix。
5. 不允许 adaptive allocation、按 validity/gain 补样本、按 task outcome 改 calibration quota，或用 API retry
   把失败变成第二次 treatment。

## 5. 预算守恒门

一个 broad parent 需要 2 个 continuation slots；calibration parent 额外需要 2 个。因此每行必须预先记录
`displaced_candidate_execution_slots = 2 + 2*I(calibration)`。producer 在随机化后逐 parent、逐 task 和全局
精确核对；不等即失败，任何 worker 都不得启动。该检查只能证明 **input-declared ledger 与计划一致**，不能证明
正常 production 的真实槽位已经扣减；真实 launch gate 还必须绑定并独立验证 scheduler 的 pre-submission budget
ledger。在那之前 artifact 必须写 `actual_production_budget_decrement_verified=false`，不得称实际预算已守恒。

这里守恒的是 candidate-execution slots 与每 candidate wall cap，不谎称不同任务的实际 GPU 秒相同。最终必须
同时报告 displaced slots、attempted/completed slots、candidate wall seconds 与 GPU·h。sidecar 目录、policy hash
和 release descriptor 与正常 MCTS、first-960 cohort 完全分开。

## 6. ITT、分析与杀死条件

- primary collection report：parent/task/run 支持、两 sibling equal exposure、validity、failure class、K=2
  test--retest、实际成本；不把 rollout 当 iid。
- quality outcome 预先定义为 task-oriented pristine external utility；失败用固定 failure floor 进入 ITT。
  conditional-on-valid 只作 hurdle 诊断，并与 ITT 并列，不得替代。
- 方法开发若以后获批，只在 physical-run outer folds 比较 task/action-only、monolithic expected utility 与
  `P(valid)*E[utility|valid]/cost`；最终门是新 run parent-equal top-1 及同真实执行预算 best-score/regret。

以下任一项关闭该支线：少于 6 tasks；任一 task 超过 25% parents；至少四个 task 内没有 validity/quality
variation；K=2 winner/test--retest 不稳定；实际失败率或 wall cost 使预算守恒不可执行；或学长不能在 production
提交前提供真实 displaced-slot ledger。关闭后不换阈值救活，资源回到 first-960 与数据发布。

## 7. 实现与权限边界

当前允许实现的只有 label-blind assignment producer、**不 import producer** 的独立 verifier、synthetic
positive/tamper tests 与文档。真实部署前仍须：双方确认 production opportunity cost；给出任务/parent 矩阵、
总 slots/API/GPU·h 上限；逐项完成长实验 preflight；使用新 artifact root。E1 批准不自动授权本协议的真实执行，
E2/E3 仍关闭。

## 8. scheduler receipt consistency verifier（仍不是 production gate）

commit `234cdd5` 后新增的 `verify_randomized_sibling_production_receipts.py` 只补内部闭环检查，且不 import
assignment producer：

1. 对每个 scheduler 声明的完整 eligible set，按固定 `sha256-top-m-without-replacement` 规则重新排序，要求
   重建出的 selected parents 与 frozen assignment parents 精确相等；逐 parent 重算 `m/n` propensity，并要求
   parent input 绑定该 canonical receipt 的 SHA-256。
2. 对 committed budget receipt，要求 assignment manifest/summary hash 精确绑定；每个 assignment ID 恰好映射
   一个唯一的 displaced standard slot 和一个唯一 randomized slot；若 `A` 为 rollout assignments 数，则强制
   `B_standard_after=B_before-|A|`、`B_randomized_after=|A|`、`B_total_after=B_before`。
3. selection/budget receipt 任意层级若出现 outcome-bearing key、凭据形状、非 canonical JSON、重复 parent/slot、
   时间逆序、policy/hash 漂移，均在写 verification receipt 前失败。

该 verifier 即使通过，也只能写：

- `upstream_selection_probability_reconstructed_from_declared_eligible_sets=true`；
- `committed_budget_decrement_internally_consistent=true`；
- `budget_conserved_within_receipt=true`。

它必须同时保留：

- `eligible_stream_completeness_verified=false`；
- `external_scheduler_receipt_authenticity_verified=false`；
- `upstream_selection_probability_verified_by_assignment=false`；
- `actual_production_budget_decrement_verified=false`；
- `production_activation_authorized=false` 与 `causal_claim_allowed=false`。

原因是 scheduler 自报 eligible set 仍可能漏事件，receipt 文件本身的来源/预提交时间也尚未由独立 production
provenance 证明。下一门不是再做一个 synthetic true flag，而是先取得学长 scheduler 的只读事件流格式，设计
append-only sequence/窗口完整性和 pre-outcome sealing；在此之前不得把本模块接到日常约 60 runs/day 的生产。
