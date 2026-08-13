# Task-conditioned parent objective：结构审计

日期：2026-08-14。目的不是再调一次旧 critic，而是在写新方法前回答两个结构问题：真实 sibling
决策里是否有足够多的多候选 parent，以及每个 task 是否有足够 physical runs 支撑独立 head。

## 协议边界

- 只读 `decision_train_v11_b0.jsonl`；预算固定为 0、`intask_split=train`。
- outer fold 直接复用 frozen global-linear discovery 已锁定的 5-fold physical-run 分配，保证后续逐行配对；
  不重新随机拆分。
- 程序文件名守卫拒绝 `frozen`、`test`、`held` 路径；状态中记录 `frozen_read=false`。
- 本审计不拟合模型、不报告 accuracy，也不改变 `VERIFIED_DISCOVERY_NO_UNLOCK`。

## 结果与裁决

全局共有 4,263 pairs / 333 runs / 23 tasks / 2,293 parents / 5,499 endpoints。2,259 个完整
parent 全部可还原为严格总序。候选数分布为：2 候选 1,520 个，3 候选 676 个，4 候选 61 个，
5 候选 34 个，6 和 11 候选各 1 个。因此：

- 多候选 parent 为 773/2,293 = 0.337113；
- 它们覆盖 2,743/4,263 = 0.643444 的 pair 行。

这使 parent-centered/top-centered objective 成为有实际信息差的 baseline，而不是对二元标签改名。但 task
支撑高度不均：例如 APTOS 只有 2 runs，dogs-vs-cats 和 Kuzushiji 各 3 runs；英文 text-normalization
只有 2 runs，且它们都落在同一个 outer fold，导致该 fold 的 outer-fit 对该任务为 0 runs。故裁决为：

1. **禁止 23 个完全独立 task heads**，因为部分 outer fold 无法训练且会产生选择性缺失；
2. 允许一个共享 global weight 加强 L2 收缩的 task residual；outer-fit 未见任务时 residual 必须精确为 0，
   自动回退 global；
3. inner 选择必须按 physical run 分组，并在全部任务 pooled 的 parent-level 指标上完成，不能按已见 per-task
   outcome 手工选择模型；
4. 主模型优先使用 winner-vs-rest 的 parent-equal top-centered surrogate，并与 all-pair/global 两个因子做
   同 fold 消融；ListNet/ensemble 不能先验写成 novelty。

## 与学长最新训练的关系

学长 `dojo-reproduce` 分支的 0812 文档在旧 1,303-pair validation 上报告 1.5B--8B 无稳定规模收益，
head-only 约随机。08-13 最新 LFS `decision_clean_b0` 为 3,908 train / 1,499 test；其 3,908 个训练对与
v11 的 4,263 个训练对有 3,907 个定向 pair 相交，v11 净多 356 个训练对。因此该结果是“容量不是主要
瓶颈”的相关外部 baseline，但不是本次 v11 run-OOF 协议的重复实验，也不能用其 test 继续调参。

机器可读结果见 `phase1/results/task_parent_support_v11_20260814/`。
