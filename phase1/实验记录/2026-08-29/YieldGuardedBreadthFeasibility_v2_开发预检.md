# Yield-Guarded Breadth MILP v2：开发性运行前预检

日期：2026-08-29

状态：`DEVELOPMENT_ONLY_NOT_EXTERNAL_CONFIRMATION`。0IQ 两个 run-disjoint folds 的结果已经读取，因此本轮只用于方法开发、结构可行性与求解规模判断；无论结果如何都不能写成未见图确认。

## v1 失败与结果前工程修订

v1 试图对六个 checkpoint 联合做二阶段全局最优。真实运行在没有产生 `result.json` 时发现 HiGHS 进程有 20 个线程，违反 single-CPU preflight；于 `2026-08-29T02:00:04Z` 主动终止。保留 root=`dev-87ba919-r1`、`FAILED_RC=143`、wall=`5:49.62`、max RSS=`567648 KiB`，没有读取 fold scientific result。

v2 不在看到科学结果后降门，而是把原来已经固定的所有通过门直接编码成可行性约束：逐点 yield、integrated task/run breadth、terminal parent 与 anti-dominance。常数目标下只回答“是否存在一条 nested trajectory 同时满足全部固定门”；不再声称找到全局最优 breadth。HiGHS 明确请求 `threads=1, random_seed=0`，并用 `taskset` 把整个进程树限制在一个允许 CPU 上。

## 固定开发问题

在六个 nested endpoint checkpoints 上，把 `uniform_edge` 256 seeds 的 nearest-rank median closed-edge 数设为逐点硬下限，同时要求 integrated task/run coverage 不低于原冻结门 `6/5,11/10`、terminal parent 不低于 `9/10`、terminal task/run share 不高于 `1/3,1/10`。唯一 readout 是每折是否存在经重新计算可逐项验证的可行 witness。

## 13 项 pre-flight

1. **方向**：仅属 Decision Corpus 的 topology-only label-acquisition 支持线；不恢复 HCE、多保真、Probe、score-channel、K≥1 lookahead；PASS。
2. **问题**：验证固定 yield+ breadth 合同的联合可行性，不声称 predictor accuracy/search utility 或优化算法首创；PASS。
3. **已知/未知**：两个 fold readout 均已知，明确标记 post-readout development；v1 无 result，v2 修订发生在 scientific readout 前；PASS。
4. **人口**：只重建已发布 exact 539-pair historical residual，并继承固定 salted physical-run split；PASS。
5. **输入绑定**：formal result SHA=`f1d8054ccc3e0d50f77a3ff4be29480f99ab0dbc51a6e1e510853da63c06e042`，worktree commit=`6cdcc928b3b654a8c7df31999cc3e332bccb0269`，v2 script SHA=`0e62c9c3bf15b689caf98ee73b2f22d1134e99b6c212960c958bd7021570942e`；PASS。
6. **公平**：同 fold、同 `[3..8]/32` checkpoints、同 256-seed uniform baseline；所有比较门沿用 0IQ，未因 v1 timing 改阈值；PASS。
7. **约束**：逐点 yield floor、integrated yield、task `6/5`、run `11/10`、terminal parent `9/10`、anti-dominance `1/3,1/10` 全固定；PASS。
8. **求解正确性**：常数目标 MILP；任一返回 witness 必须从 selected endpoints 重算 induced edges 和全部门，solver status 本身不代替复核；无 witness 的 time limit 只算 unresolved；PASS。
9. **攻击测试**：合法 disjoint synthetic、合法 overlapping-component synthetic、86 条可行 nested trajectories 的穷举 oracle，以及已知 infeasible 负控均一致；PASS。
10. **复现**：固定脚本 SHA、Python/SciPy 版本、HiGHS seed、单 CPU affinity、exclusive output、wall/RSS 与 manifest；PASS。
11. **访问边界**：禁止 prospective/first-960/Target-300/Target-522、senior test、orientation/gap/grade/outcome/code/prediction/runtime；只允许 safe Cards、historical train relation 与已发布 aggregates；PASS。
12. **资源与安全**：CPU-only；GPU/API/model-fit/base-update=`0/0/0/0`；清除 provider credential 环境变量，跟踪文件/网络访问并扫描；每折 feasibility 最多 300 秒，外层 900 秒；PASS。
13. **停止与表述**：任一 SHA、clean-worktree、自测、baseline reproduction、witness 重算、访问或 manifest 门失败即保留失败目录；不得降 floor、删 fold 或称为 confirmation；PASS。

## 运行矩阵

- folds：2（fold0、fold1，顺序固定）；
- checkpoints：每折 6；
- solver：每折一个 constant-objective feasibility MILP；
- 最大 solver 时间：`2 folds × 300 s = 600 s`；外层 hard cap 900 s；
- GPU·时/API 费用：`0 / 0`；CPU 预计 1–12 分钟，无 witness 的超时只判 `FEASIBILITY_NOT_RESOLVED`。
