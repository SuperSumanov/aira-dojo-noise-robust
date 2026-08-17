# Failure mechanism × code length heterogeneity v1：预注册与执行前检查

日期：2026-08-18。状态：`FROZEN_NOT_RUN`。本实验只使用已发布的 494 个 train-only unique-parent
failure/success pairs；不读取 frozen endpoint code、数值 grade 或新前瞻 cohort。

1. **问题**：此前 discovery cohort 中 length-only LOTO 的 `0.5688259109311741` 是否掩盖了不同 execution
   failure mechanism 的异质方向？这回答缺失机制是否同质，不回答长度能否成为搜索 controller。
2. **锁定单位**：SHA=`ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747`
   的 494-row code-free registry；每个 parent 一对 retained-success / evaluator-verified execution failure。
3. **唯一特征**：原始 UTF-8 code byte length；success 更长计 1、更短计 0、相等计 0.5。不截断、不去注释、
   不按任务或 category 调方向。
4. **分层**：使用 2026-08-17 前已机械冻结的 failure taxonomy；所有类别完整报告，只有 pairs `>=30` 的类别
   进入 primary heterogeneity test。不得按结果合并/拆分类别。
5. **主检验**：类别均值的 pair-count-weighted 方差；在 task 内置换 credit 100,000 次，固定 seed
   `20260818`。这是在保持 task/category 构成的前提下检验类别差异。
6. **不确定性**：每类别同时报告 task-clustered 与 physical-run-clustered bootstrap CI，各 10,000 次；
   不用 pair-binomial CI 替换。
7. **正门**：至少 3 个 `n>=30` 类别；最高/最低类别各 `n>=30` 且覆盖至少 4 tasks；credit range
   `>=0.15`；task-stratified permutation `p<=0.01`。任一失败即
   `INSUFFICIENT_FAILURE_MECHANISM_LENGTH_HETEROGENEITY`。
8. **负控**：parent SHA parity 的固定随机 credit 走同一置换管线，只作 sanity，不进入正门。
9. **安全**：target journal 在解析前做完整 blob credential scan；命中即 fail-closed。产物只含长度差与聚合，
   不输出 code、stdout、diagnostic 或 grade。
10. **资源/复现**：CPU-only、GPU=0、API=0；完整测试后正式双跑，要求逐字节一致并记录 exact commit/input SHA。
11. **允许主张**：过门只允许“execution censoring 的静态长度关联随机械 failure mechanism 显著不同”；
    不允许 method effect、search utility、因果解释或跨 agent 泛化。同一 494 对上不再换 token/line/AST 长度追正数。
