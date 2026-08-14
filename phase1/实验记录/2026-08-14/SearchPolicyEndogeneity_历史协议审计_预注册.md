# Search-policy endogeneity：历史协议契约审计与受控续跑路线

日期：2026-08-14。协议名：`search_policy_contract_audit_v1`。本文件固定在全量历史归档结果之前，
但**不是 outcome-blind discovery 预注册**：此前 `amplifier_test.py` 已在旧 fragment 身份上看到两个任务的
探索性结果；本轮又在正式审计前查看了一份 0802 与一份 0805 nomad 归档的配置契约。样本契约已经显示
底座、执行限时、子节点数和代码 commit 不一致，因此本轮的首要目标是阻止错误的因果主张，并恢复真实
physical-run provenance；任何全量结构结果都只能是描述性证据。

## 1. 问题与固定输入

历史假设是：MCTS 会把更多 continuation 分给早期看好的分支，因此用“已观察子树最大分”训练 branch-value
critic 时，标签同时编码了分支质量和行为策略分配的预算。0805 的 sequential/no-selection 采集原本被当作
近似自然实验。本轮先问一个更基础的问题：0802–0804 MCTS 与 0805 sequential 是否真的只改变了 selection
policy？若不是，就禁止把两者的差异归因于 selection。

固定输入为远端不可变 tar 分批：

- MCTS 候选臂：`external/senior_data/mle/0802`、`0803`、`0804`；
- sequential 候选臂：`external/senior_data/mle/0805-这里开始进一步压低任务限时和子节点数`；
- 每个归档只读取每个 run root 的 `dojo_config.json` 与 `checkpoint/journal.jsonl`；
- 不读取 `env_variables.json`、日志、HTML、workspace、submission、grading report 或任何 frozen/test pair。

运行前先写出每个 tar 的相对路径、字节数与 SHA-256；相同字节的重复归档不重复计 run。physical run ID
固定为 checkpoint journal 原始字节的 SHA-256。policy 标签来自冻结的日期/采集协议清单，不从 outcome
反推。

## 2. 安全与完整性门

tar 使用流式 allowlist 读取；拒绝绝对路径、`..`、反斜杠、NUL、symlink、hardlink、device 和 FIFO。
allowlist member 在 JSON 解析前先按 credential regex 扫描；命中即 fail closed，不输出部分科学结果。
每个**进入结构审计的 complete run**必须恰有一个 config、一个 checkpoint journal、一个 step-0 root；
只有 config 或只有 checkpoint 的 root 不读取 outcome、只进入覆盖率分母。complete run 内 step 唯一，非 root
恰有一个更早的 parent，所有节点 creation time 不早于 root。任何 parent/重复/非有限时间异常均判
`INVALID`。

输出不得包含代码、prompt 正文、term output、metric、grade、tar 内部 run-root 用户身份或 API/base URL。只保留
归档 SHA、journal SHA、task、seed、节点结构统计、下列公平契约值及 prompt SHA。

## 3. 公平契约与先验 kill gate

逐 run 固定比较：

1. `metadata.git_commit_id`；
2. 四个 operator 的 model/provider、generation kwargs、prompt SHA-256；
3. `interpreter.timeout`、`solver.execution_timeout`、`time_limit_secs`、`step_limit`；
4. `num_children`、`uct_c`、debug 深度/时间、memory processor 与其两个布尔旋钮；
5. benchmark、task、`use_test_score`、`use_complexity`。

只有在同一任务的两臂中，除预先声明的 selection-policy implementation 外上述契约逐项相同，才允许
`HISTORICAL_POLICY_NATURAL_EXPERIMENT_ELIGIBLE`。任一关键字段不同即固定输出
`CONTRACT_KILLED_DESCRIPTIVE_ONLY`。正式审计前已知的 nomad 样本差异必须保留：0802 使用
`deepseek-v4-flash`、14,400 秒执行限时和 5 children；0805 使用 `qwen3.5-397b-a17b`、4,800 秒和
2 children，且 commit 不同。因此预期全量审计不会通过因果门；不得因后续结构效果漂亮而放宽。

## 4. 描述性结构审计

即使契约门失败，仍可为了数据设计报告 source-truth 结构，但不能做因果措辞。每个合法 physical run 以
step 0 的直接 child 为一级分支，统计每个一级分支的全部后代数。run 必须至少有两个一级分支和四个非 root
节点才进入 allocation 指标。

固定指标为：总节点数、最大深度、一级分支数、最大分支份额、HHI、按一级分支数归一化 HHI、归一化熵、
有效分支数比率和 Gini。主描述量是归一化 HHI；其余为稳健性。只比较两臂共有任务，逐任务报告 run 数与
中位数，不只报 pooled 均值。若每臂 physical-run 总数少于 20、任一臂 journal 覆盖率低于 80%、共有任务
少于 2，或共有任务中没有至少每臂 4 runs 的任务，则结构路线也判 `DESCRIPTIVE_SUPPORT_INSUFFICIENT`。

由于采集协议未随机化且公平契约已知失败，不把 permutation/bootstrap 的零假设 p 值解释为 selection 的
因果效应。可以报告 task-macro paired difference 与 run-cluster bootstrap 区间，只用于估计描述性差异和
后续样本量；逐任务方向必须同时列出。

## 5. 标签结论边界

本审计不读取 grade，也不重新拟合 critic。结构集中度不同最多说明 historical subtree maximum 可能受
不等 continuation count 污染；它不证明污染的大小、不证明 balanced label 更可预测、更不证明下游搜索会
变好。旧 `amplifier_test.py` 的“两任务 0.73 对 0.56”必须降级为 confounded exploratory result，不得写入
摘要或主表。

真正可识别的下一实验必须重新采集：同一个 parent 先产生固定数量兄弟，然后在冻结的同模型、prompt、
operator eligibility、硬件、单次执行限时与总预算下，为每个兄弟分配相同的 K 个 continuation；记录每次
选择概率、停止原因和 exact cost。由独立 replicate 构造固定预算 branch value 与不确定度，并在 fresh
physical runs 上比较 historical-MCTS label、balanced-K label 和 immediate child label 的 test-retest、
run/task-held-out ranking 及最终 fixed-budget best score/regret。未完成该干预前，不声称解决了 label
endogeneity。

## 6. 资源与停止规则

本轮只做 CPU 流式 tar 审计，0 GPU、0 API、0 LLM 权重更新；预期 5–15 分钟。正式输出原子写入新目录，
命令、commit、Python 版本、输入 manifest、失败配置和随机 seed 与结果并存。若契约门失败，停止对历史
0802–0805 做方法效果挖掘，转而产出受控 balanced-continuation 的配置矩阵和预算估算，不在同一数据上
更换指标、任务或阈值。
