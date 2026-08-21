# Tree Transition Future Escrow：实现合同与激活预检

日期：2026-08-21。状态：`IMPLEMENTED_AND_SMOKED_BEFORE_FORMAL_BUILD_OR_ACTIVATION`。本文件在正式 full-fit、
正式 activation 和任何 post-activation run 产生前冻结。此前只在 `/tmp` 创建过一次明确无效的 smoke activation；
它不进入 Git、正式 receipt 或时间边界，当前 prospective outcome 始终未读。

## 1. 实现合同

冻结模型不是不透明 pickle，而是两项可移植、可独立重建的 model receipt：

1. `model_spec.json`：三臂 feature/matrix SHA、精确 HGB 参数、300 iterations 与反对称回执；
2. `train_reference.csv`：5,240 个训练 pair 按 canonical left/right orientation 的三条 full-fit margin。

每次 snapshot 的 producer 与 independent verifier 都从固定 Cards/train/dev 重新 full-fit 三个 HGB，再逐行核对训练
reference；不加载可执行 pickle。这样 activation 的 model SHA 是 spec/reference/summary/verifier 四段哈希链，实际预测
仍由固定输入、固定代码和固定 sklearn 环境完整重建。

future pair 固定按 `(task,physical_run,parent,left,right)` 识别，left/right 为 card-ID 字典序。正 margin 表示偏好
left，计算为 `0.5*(decision(d)-decision(-d))`。只有同 task/run 的 parent code 在 blind manifest 中存在才计算三臂；
missing parent 三条 margin 都写 `null`，避免 arm-specific complete-case。训练 endpoint ID、run ID 或 parent/children
任一 code SHA 重叠的 pair 标记并排除 primary。

预注册的 “finite non-tie” 在任何正式 support prediction 前保守固定为：三个 arm margin 都 finite 且都不等于 0。
不得在看到 future prediction 分布后改成只要求 primary 两臂。strict 时间边界是
`generation_started_at_utc > activated_at_utc`；相等永久属于 `support_only`。

## 2. Append 与双实现

- producer 用既有严格 blind-snapshot loader；verifier 用另一套 cohort loader、feature extractor、edit projection 和
  full refit；verifier 不 import producer；
- 新 snapshot 必须保留 prior artifact 的所有 pair IDs，且每个旧 row 逐字段完全相同；缺失或漂移 fail closed；
- 每次输出 all/support/strict/parent-covered/source-novel/finite/non-tie/eligible inventory、task/run 分布、三种
  overlap 与固定 support gates；effect metrics 始终为空；
- activation 由远端 `time.time_ns()` 自动产生，绑定 commit、全部相关 source files、protocol、model outputs 与
  independent verification；独立 verifier 复算 wall-clock、当前 snapshot 最大 generation time 和 strict=0；
- 正式源码入口为 `phase1/transition_future_escrow_protocol_v1.json` 列出的完整路径。

## 3. 结果盲 smoke

临时独立 Git commit 与 `/tmp` 输出上已完成：

- 7 个 synthetic tests：canonical orientation、swap antisymmetry、missing parent、ID overlap、strict/equal timestamp、
  all-three-arm non-tie、完整 support gate、prior tamper 与变长 fractional timestamp；
- 真实固定训练输入 full-fit + independent refit：5,240 rows，reference 最大差 0；
- 临时 activation + independent activation verifier：通过；
- 当前 frozen snapshot producer + independent verifier：1,665 rows，training/future margin 最大差均为 0；
- 当前 1,665 rows 全部为 support-only，strict=0，未读 outcome，也未计算 accuracy/effect。

临时 activation 只验证代码路径，不得被复制、引用或提升为正式边界。正式 activation 必须在本实现 commit、正式
model producer×2/verifier×2 和 seal 全过后重新由远端时钟创建。

## 4. 正式执行矩阵与 13 项预检

1. **方向**：Decision Corpus + Predictor Benchmark 的 frozen transition extension；不恢复 HCE/TD/probe。
2. **唯一问题**：原样冻结 combined−child 是否在严格未来 sibling 上确认；不加新 feature/模型/子集。
3. **输入**：Cards/train/dev 三个既定 SHA；snapshot/activation/model/protocol 每项精确 SHA。
4. **切分**：future 逐 pair endpoint/run/code 三查；current support 与 formal future 永不合并。
5. **样本**：first-960 固定全序与既有 closure；不重抽、不按 margin 删除。
6. **矩阵**：model producer×2 + independent verifier×2；activation×1 + verifier×2；initial escrow
   producer×2 + independent verifier×2；同 snapshot prior append replay producer×1 + verifier×1，共 30 次固定
   HGB fits。
7. **统计**：本轮只锁 prediction/support，不读 label、不做 CI；closure 后才执行既定三聚类 CI。
8. **RNG**：HGB random_state=7，PYTHONHASHSEED=0，单线程 BLAS；无本轮 bootstrap。
9. **资源**：单线程 CPU，0 GPU、0 API、0 LLM update；预计总墙钟 10—25 分钟。
10. **完整性**：producer/verifier byte reproducibility、stderr/diff、syscall forbidden paths、credential scan。
11. **失败规则**：任一数值差>1e-12、旧 row 漂移、source/input/hash/clock 不一致均不 activation/不提升。
12. **恢复**：每个阶段独立目录与完成标记；失败保留 staging，新 attempt 单列，不覆盖已有 artifact。
13. **封存**：完整命令、软件、输入 SHA、source blobs、测试、time、manifest；成功目录递归只读后再报告。

这是一项 CPU-only、无外部费用的固定协议执行，用户已授权继续正方向工作；不触发额外 GPU 预算审批。
