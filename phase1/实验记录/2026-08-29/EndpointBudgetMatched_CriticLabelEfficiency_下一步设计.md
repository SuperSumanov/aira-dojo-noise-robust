# Endpoint-Budget-Matched Critic Label Efficiency：下一步设计

日期：2026-08-29
状态：`DESIGN_ONLY_NOT_PREREGISTERED_NOT_RUN`
目的：把 topology-only 结构可行性推进为真正有论文价值的 downstream 正结论。

## 一句话问题

在 agent、完整 endpoint execution 定义、总 endpoint 数、critic 架构和训练预算全部固定时，利用 sibling topology 选择要执行的
endpoints，能否比 exact-B uniform-edge 产生**更有用**而不只是更多的训练 pairs，并提高未见 physical runs 上的 critic
pairwise accuracy/calibration？

## 为什么这是下一步，而不是继续堆结构指标

当前 yield-guarded breadth 只证明某个 endpoint subset 可以同时闭合足够多 sibling labels 并覆盖更多 task/run；它没有证明这些
labels 会改善 predictor。Graph active learning、pairwise active sampling 和 constrained coverage 都已有相关工作，因此“又一个
拓扑优化器”不足以构成主张。真正与 Decision Corpus + Predictor Benchmark 容器闭环的是：按真实执行成本计价的数据生产策略，
能否改善固定 critic 的 run-disjoint 学习曲线。

## 建议的 development protocol

### Population 与防泄漏

- 只用 `intask_split == "train"` 的历史 development population；所有 `test` 行继续零访问、零训练。
- 先按 physical `run_id` 做固定 salted 五折；一个 run 的 endpoints/pairs 只能属于一个 outer fold。
- 每折 acquisition 只看 outer-train 的 unordered endpoint/parent/task/run topology；orientation、gap、grade 和 code 都不得参与选择。
- outer-test 只用于该折一次评估，不参与 seed、budget、超参或 early stopping 选择。
- 任一折 support 不足、task/run share 过大或出现 endpoint/run overlap，则整项停在 `LIMITED_SUPPORT`，不删折。

### 固定 arms

1. `exact_b_uniform_edge`：保留 edge hash priority、endpoint linearization 和 singleton-fill；每 checkpoint 必须 exact B。
2. `exact_b_uniform_vertex`：不利用 sibling closure 的随机 endpoint control。
3. `exact_b_balanced_closure_greedy`：旧 balanced greedy 的 exact-B 版本，禁止原子 action underfill。
4. `yield_guarded_breadth`：与 Target-522 相同的逐点/积分 yield floor 和 breadth/anti-dominance contract；只接受可直接验证的
   private witness。

若 MILP 在固定时限内 unresolved，该折/预算记 unresolved，不能用 greedy 结果冒充 arm。随机 arm 的 256 seeds 只用于 topology-only
分布；每折每预算在看 labels 前固定 nearest-rank median-yield seed，避免训练 256 个模型后挑最好 accuracy。

### Budgets 与训练数据

- 沿用 endpoint fractions `[3,4,5,6,7,8]/32`，每个值向下取整；六点构成一条 nested trajectory。
- 训练 pairs 恰为两个 endpoints 均被 arm 选择的 canonical direct-sibling rows；同/reverse duplicate 在训练前按 canonical
  endpoint pair 去重并记录 duplication rate。
- primary 比较固定 endpoint cost，不强行固定 pair count，因为 pair-label amplification 正是 estimand 的一部分。
- secondary `equal_pair_count`：每个 topology arm 的诱导 pairs 用结果无关 hash 截到 baseline pair count，用来区分“更多 labels”与
  “更广 coverage”两种机制；secondary 不得 rescue primary。

### 固定 predictor

- 第一阶段只用 CPU `tfidf_lr`：endpoint code 截断 20,000 字符，char 3--5 gram；vectorizer 只 fit acquisition 后的
  outer-train endpoints，pair feature 与正则化完全固定。
- 同一 outer fold 内缓存原始 code 后，由每个 arm 自己 fit vocabulary；不得 fit outer-test 或未选择 train endpoints。
- seed、solver、scikit-learn 版本和 Git commit 写入逐 run CSV；一行对应 fold × budget × arm × selection seed。
- 若 CPU 结果过固定门，再单独提交 0.6B/8B critic GPU 矩阵；当前设计不授权 GPU。

### Primary metrics 与推断

- pairwise accuracy、log loss、Brier score；同时报告每 executed endpoint 产生的 canonical pair 数。
- task-clustered paired bootstrap 为主，run-clustered为辅；另报 outer-fold paired differences 和 run-level sign test。
- 不只报总体均值：每 task、每 fold、coverage、最大 task/run share、未见 run 数都要列出。
- 初始化/训练成本与单 pair query 成本分别记录，遵守 NAS predictor 的 init/query accounting。

### 结果前 promotion gate

只有同时满足下列条件，才允许称 development 正信号：

1. `yield_guarded_breadth - exact_b_uniform_edge` 的五折 accuracy difference 至少 4/5 同号；
2. task-clustered paired 95% CI 下界大于 0；
3. log loss 或 Brier 至少一项同向且没有明显 calibration 退化；
4. 所有 checkpoint exact-B，primary pair yield 不低于 baseline，task/run anti-dominance 全过；
5. drop-dominant-task 与 equal-pair-count secondary 不把效果反转；
6. 任一 method/threshold/budget/seed/模型选择均在 label readout 前冻结。

通过也只能称历史 run-disjoint development；最终 confirmation 必须用 acquisition 规则冻结后才产生的 future physical runs，且
不能与 Target-522 的结构 confirmation 混成独立任务 replication。

## 预计资源（尚未授权启动）

- CPU Phase A：5 folds × 6 budgets × 4 arms；topology selection 可共享，模型拟合约 120 个，单机预计 1--3 CPU·时，需先做
  1 fold × 2 budgets smoke。
- GPU Phase B：仅 Phase A 过门后另报 0.6B/8B、context、seed、总 GPU·时矩阵并请求批准。
- API：0；agent 底座更新：0；RL：0。
