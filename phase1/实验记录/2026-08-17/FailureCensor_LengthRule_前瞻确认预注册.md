# Failure-censor code-length rule 前瞻确认预注册

日期：2026-08-17。状态：`FROZEN_NOT_STARTED`。本实验是 score-channel 主实验等待期的
train-only 支持审计，不替代当前主线，不读取 frozen b0/b1/b2，也不授权 GPU/API 或底座更新。

## 为什么值得确认

既有 494 个 unique-parent、same-run failure/success pairs 上，预先指定但非 primary 的 length-only
LOTO baseline 得到 pair accuracy `0.5688259109311741`、task-clustered 95% CI
`[0.5209636505871054, 0.6253654998528029]`。这个结果是在 discovery cohort 上看到的，只能生成假设；
不能在原 494 对上继续改特征、阈值或筛任务追认。

如果一个完全冻结、无需学习的代码长度规则能在全新 physical runs 上复现，它支持的正面结论不是
“长度是好 critic”，而是更基础也更贴合数据论文的结论：execution censoring 在 source sibling 内对静态代码
可观测量并非 exchangeable，因而只发布执行成功的 labeled fragment 会产生可测的选择偏差。

## 结果前冻结的协议

1. **研究问题**：在严格晚于本预注册 commit 的新 physical runs 中，较长的候选代码是否更可能成为
   retained-success，而不是 evaluator-verified execution failure？
2. **冻结顺序**：当前 score-channel 150-run cohort 的资格 manifest、trusted-parent selector 与 replay shards
   必须先逐字节封存；在此之前不得为本实验解析这些新 run 的 failure/success 结果。这样本支持实验不能影响
   主实验选样或停止时点。
3. **cohort**：按 `(root_creation_time, source_journal_sha256, parent_id)` 排序，取预注册 commit 之后最早的
   **150 个 eligible unique parents**，不按结果好坏或任务补样。达到 150 后立即冻结；不足 150 只报
   `SUPPORT_WAIT`，不计算 accuracy。
4. **资格单位**：每个 source parent 最多一对；同一 physical run、同一 task、不同 exact-code SHA；failure
   必须由 pristine execution receipt 唯一验证，success 必须是已保留、非空代码 sibling。多个 failure/success
   时分别按 child ID 字典序取第一个。与任何 frozen b0/b1/b2 run 重叠即拒绝整个 parent。
5. **唯一主规则**：比较原始 UTF-8 code byte length；长度更大的候选预测为 retained-success，相等计 `0.5`。
   不训练、不截断、不去注释、不 AST-normalize、不按 task 调方向或阈值。
6. **主指标**：150 对上的 tie-aware micro pair accuracy。主不确定性为 physical-run clustered bootstrap
   95% CI（固定 seed `20260817`，10,000 次）；task-clustered CI、per-task 数值和字符数规则仅作完整报告，
   不替换主指标。
7. **支持门**：至少 150 pairs、40 physical runs、8 tasks、dominant-task share `<=0.35`；主 accuracy
   `>=0.58` 且 run-clustered CI lower `>0.50`；在 pair 数至少 10 的任务中至少 70% accuracy `>0.50`。
   任一失败则状态为 `PROSPECTIVE_LENGTH_SIGNAL_NOT_CONFIRMED`，关闭该规则，不换长度定义重试。
8. **负控**：固定 SHA-256 parity 规则，期望接近 0.5，只做管线 sanity check，不进入支持门。身份/status
   精确重建率与 parent/run/task 一致性是结构门，不是正控效果。
9. **允许主张**：只有全部支持门通过，才允许写“新 cohort 上存在静态可观测的 informative censoring”。
   禁止写 search utility、质量预测、跨 agent 泛化、因果机制或生产加速。
10. **安全与隔离**：每个 journal 在解析前做完整 blob credential scan；任何 credential-shaped target journal
    使本实验 fail-closed。env member 永不读取；不输出原始代码，只输出长度、哈希、身份与聚合统计。
11. **资源与复现**：CPU-only、GPU=0、API=0；固定依赖、git commit、输入 SHA、seed 与命令写入产物；
    producer 双跑逐字节一致后，再由不 import producer 的 verifier 独立重建计数与指标。

## 明确的停止条件

- score-channel cohort 尚未先封存：不启动；
- 150 eligible parents 尚未到达：只等待，不看中间 accuracy；
- 结构门或安全门失败：`INVALID`，不解释效果；
- 支持门失败：诚实关闭，不在同 cohort 上改成行数、token 数、AST 节点数或组合模型。

这条路线的价值是给 failure-censored benchmark 增加一个真正前瞻、可证伪的 missingness 证据。它是数据/评测
贡献的增强项，不是把已经失败的 TF-IDF controller 换名复活。
