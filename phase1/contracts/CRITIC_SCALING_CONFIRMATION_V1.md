# Clean critic scaling 独立确认契约 v1

状态：`CONTRACT_READY_ASSETS_PENDING`。本契约只准备 future-only 结果交付与独立裁决，不授权 GPU、API、
模型拟合、底座更新或前瞻 score-channel 真值读取。

## 1. 要确认的窄命题

在同一批 run-clean、真实 sibling、一次性 test cohort 上，Qwen3-Base critic 的容量从 0.6B 增至 8B 时，
task-macro pair accuracy 是否稳定改善；8B 是否在两个 seed 上都超过同池、train-only 拟合的 char-TFIDF；
若准确率改善成立，它是否进一步转化为 comparison-component 的 oracle-gain capture。

这只是数据集/benchmark 的容量与效用机制证据，不申 reward-model 方法首创，也不等价于在线搜索收益。
旧 test-touched checkpoint、旧 b0/b1/b2、前瞻 score-channel vault 均禁止进入。

## 2. 冻结矩阵与分层裁决

- 模型：Qwen3-Base `{0.6B, 1.7B, 4B, 8B}`；seed `{6, 7}`，共 8 个 checkpoint。
- 每个 checkpoint 必须训练完整、只按 dev 选择、记录 step/dev metric，并在首次 test access 前锁定模型
  revision 与 checkpoint manifest SHA-256。
- 同一 truth/pair IDs 必须被 8 个模型和 TF-IDF 全覆盖；缺一项、重复一项或多一项均 fail closed。
- primary 只用 `canonical_raw_sibling`；micro/run-macro/其他 semantics 仅作 secondary。
- task bootstrap 10,000 次，seed=`20260823`；禁止 pair-i.i.d. 区间。

层级门互不偷换：

1. **支持门**：至少 20 tasks、300 comparison components，最大任务 pair share 不超过 0.20。
2. **容量门**：四个两-seed task-macro 均值随规模单调不降；8B−0.6B 点差至少 0.02；两个 seed
   各自 8B−0.6B 为正；task-bootstrap CI 下界严格大于 0。
3. **基线门**：两个 8B seed 各自高于同池 TF-IDF；两 seed 平均的 task-paired delta CI 下界严格大于 0；
   leave-one-task-out 删除任一任务后 delta 均为正。
4. **效用转换门**：8B 两 seed 平均减 TF-IDF 的 component gain-capture task-bootstrap CI 下界严格大于 0。

容量门与基线门全过才允许写 clean scaling + stable baseline win；效用门另过才能加“转换为 decision utility”。
效用门失败不能反过来撤销已经通过的容量门，也不能用 subgroup 替换 primary。

## 3. 三段式不可变交付

### A. test 前 lock

`critic-scaling-confirmation-lock-v1` 必须先进入 Git 历史，并至少含：

- 本契约 SHA、训练源码 commit、UTC freeze 时间；
- truth 文件 SHA/rows/split，但不要求研究者查看其数值内容；
- TF-IDF 的 train-only fit receipt SHA；
- 8 个模型的 size、seed、base model、model revision、checkpoint manifest SHA、training complete、
  dev-only selection、checkpoint step 与 dev metric。

lock 状态必须是 `LOCKED_BEFORE_TEST_ACCESS`。补 checkpoint、换 seed、按 test 选 step 都会使该轮作废。

### B. 一次性 bundle

`critic-scaling-confirmation-bundle-v1` 后验绑定 truth、TF-IDF predictions、8 份模型 predictions 与各自 ledger。
所有路径必须是 bundle 目录内的相对普通文件，禁止绝对路径、`..` 逃逸与 symlink。每份 ledger 必须精确记录：

```json
{
  "status": "COMPLETE",
  "test_attempts": 1,
  "lock_sha256": "...",
  "truth_sha256": "...",
  "prediction_sha256": "...",
  "checkpoint_manifest_sha256": "... model only ..."
}
```

任何 `test_attempts != 1`、hash 不一致、失败后覆盖、未知/重复 run 一律拒绝。

### C. 行级 schema

truth 每行固定字段：`pair_id/split/task/pair_semantics/parent_id/parent_run_id/
comparison_component_id/better_id/worse_id/better_run_id/worse_run_id/better_utility/worse_utility`。
`pair_id` 是上述身份六元组的 canonical JSON SHA-256；better utility 必须严格大于 worse utility；primary
sibling 的 parent/better/worse 必须同 physical run；同一 comparison component 必须连通且元数据一致。

prediction 每行只有 `pair_id/better_score/worse_score/margin`。分析器独立检查 `margin=better−worse`、有限值、
全 predictor 同池，以及同 endpoint 在多条 pair 中的 score 一致性。component tie 以 score 最大端点均匀选择；
gain capture 先在 component 内以 uniform 与 oracle 归一化，再 task-macro，绝不跨任务混 raw grade。

## 4. 双实现与发布条件

- producer：`phase1/critic_scaling_confirmation_analysis.py`；
- 不 import producer 的 verifier：`phase1/verify_critic_scaling_confirmation_analysis.py`；
- model-side one-shot endpoint receipt overlay：
  `phase1/upstream_patches/0004-Emit-endpoint-score-receipts.patch`，SHA-256=
  `237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`；
- 冻结机器契约：`phase1/critic_scaling_confirmation_contract_v1.json`，SHA-256=
  `579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568`。

verifier 将冻结契约 SHA 写死，独立重建 pair/task/run/component 指标、bootstrap、所有 gate、两个 CSV 与
artifact manifest。只有 producer 与 verifier 同时通过，结果才可进入论文表格。

## 5. 下一轮训练前 13 项检查

1. 唯一科学旋钮是模型规模；数据、prompt、max length、优化器 token budget、checkpoint 规则不变。
2. exact source/config provenance manifest 全覆盖，unknown interaction metadata 不进入 interaction claim。
3. train/dev/test 的 endpoint、physical run、unordered pair 零交集。
4. Trainer 只挂载 train/dev；test path 不可见，周期 eval 只读 dev。
5. `metric_for_best_model=eval_pair_accuracy` 且 `greater_is_better=true`。
6. 8 个 run 的模型 revision、checkpoint SHA、step、dev metric 在 test 前同时锁定。
7. TF-IDF 只 fit train；同一 test truth 与全部模型逐 pair 对齐。
8. 每个 checkpoint×test 只有一次排他 ledger；失败不得覆盖重试成成功。
9. truth orientation、physical run、component 连通与 endpoint score/utility 一致性全部 fail closed。
10. 保存逐 pair、逐 task、逐 run、逐 component 和两个 seed，不只报均值。
11. 任务聚类为 primary；pair-i.i.d. 显著性不得进入 headline。
12. 文件名与内容做凭据形状扫描，原始 key/tar payload 不进入 Git 或日志。
13. 提交前另给 exact run 数、GPU 数、wall cap 与总 GPU·时并取得用户批准；本契约本身授权量仍为 0。

## 6. 当前资产缺口

model-side endpoint receipt overlay 已在 `ac008af + 0001/2/3` 上通过 36 项聚焦测试，但当前只有学长 0820
聚合表的探索性 scaling；没有可用的逐 pair predictions、完整 checkpoint manifests 与
one-shot ledgers，已知常见 checkpoint 目录也不存在。因此现在不能运行本分析，更不能把历史表升级为确认结果。
学长下一轮只需在删除 checkpoint 前保留上述 lock/bundle 所需资产；无需把大模型权重推到 Git，权重只需在共享
存储保留并把不可变 manifest/hash 入库。
