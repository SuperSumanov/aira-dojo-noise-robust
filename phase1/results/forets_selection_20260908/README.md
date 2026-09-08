# ForeTS 固定候选批处理的真实随机基线入口

2026-09-08。0007 在 standalone 0005 + 0006 后应用；不是独立累计补丁。
学长 upstream：`54929de4ac92cb1a1a2fd75e31843a223c10c859`；base tree：
`a999d8aaf8e9278e4e1eab57e5e45d2b0f87aa48`。没有部署到学长分支或生产 checkout。

## 解决的比较缺口

原批次入口不管 top-k 多大，都会对所有候选调用 critic。top-k=全池取消排序筛选，
但仍不是不依赖 critic 的随机基线，也不能把该模式的费用当作随机方法费用。

新增必填 `selection_policy`：`uniform_random` 或 `critic_topk_random`。不设默选、不自动切臂。

| 共同批处理规则 | uniform_random | critic_topk_random |
|---|---|---|
| 生成候选数、完整执行数、debug 规则 | 相同冻结配置 | 相同冻结配置 |
| 生成全部完成后冻结有序候选记录 | 是 | 是，冻结前不评分 |
| critic 调用 | 不调用、不接受 score 输入 | 所有候选获得有限分数后才能选择 |
| 抽样范围 | 全池 | 按分数取 top-k；并列按原槽位稳定顺序 |
| selector 随机流 | 独立 seed/task/step | 同一规则，不消耗生成器随机流 |
| 执行前检查 | 原候选内容未改变 | 原候选内容未改变，评分后也检查 |

未选/未执行节点保留 generated/scored 状态，不伪造失败或零分。随机臂可在已知执行前状态
复用既定选择而不重生成/重抽；未知执行或中途评分状态仍停止，不自动重试。
台账 schema 升至4，旧批次不混用，更改 policy 不能借旧台账继续。

## 公平性与结论边界

- 先完成整批生成，再开始评分，是本次共同契约；不是保留旧 generation/scoring 交错调度不变。
  旧逐节点 MCTS 不能改名当成该 batch-random。
- 最终抽样前把 eligible slots 恢复为槽位顺序，selector domain 升至v2。因此在同一批候选、
  相同 seed/task/step 下，top-k=全池时两臂选择完全一致，与分数排序无关。
  这改变了旧版本给定 seed 的具体选择，不能拿新 selector 重放/重选旧已冻结批次。
- pool SHA覆盖有序完整生成记录；它不单独证明共同父状态/环境。相同seed、相同候选数
  也不保证两次付费生成输出相同。真实同池实验仍须锁同一原始候选与决策状态；本补丁
  没有提供跨策略多步轨迹共享或证明在线 runs 自动共池。
- 多步轨迹分叉后，各臂只能使用自身过去反馈，不能借另一臂未来轨迹。固定池排序价值
  与完整在线同预算收益是两个 estimand，不互相冒充。
- random 零 critic 调用不等于零分配GPU小时；如果预留GPU却闲置，该成本仍应计入。
  critic 初始化、实际调用/失败、生成、执行、分析、评分及闲置分配仍需独立完整成本记录。
- 截断/实际模型身份/完整恢复/硬预算仍未解决；train-only TF-IDF adapter 也尚未接入。
  不增loss网格、不重训、不改原严格四fit准入，不用合成结果宣称critic有效。

## 新增验证

Windows新增16项通过。包括真实修订 batch 函数体的零critic随机路径、评分前全池冻结、
top-k全池逐选择一致控制、失败不执行/不重试、评分不能篡改候选、已知选择复用及policy漂移拒绝。
生成/backend/task/config基础均人工构造，未运行真实LLM、GPU、程序或MLE评分。

Git独立应用tree：`6f7e650e5ecfd8dac7369a954ac16e01f258daa1`，5文件95新增20删除。
实际tree及Linux验证状态见后续回执；不重复此前task-return16项或request69项来堆测试数量。
下一步冻结源码后在独立Linux目录仅跑本矩阵，最多300秒CPU，0GPU/API/model fit。

本轮是让正面结论有公平对照入口的工程贡献，不是新方法或模型正收益。production_ready=false。
正式数据与四fit仍等待实际独立开发来源原记录；用户要求外部事实不足时等待。
