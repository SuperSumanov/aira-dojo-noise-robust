# Decision Semantic Mixture CPU 发现门 v1：预注册与预检

日期：2026-08-21。状态：`PREREGISTERED_NOT_RUN`。本实验服务当前 Decision Corpus + Predictor Benchmark 与
学长 0820 scaling 支持线，不恢复 HCE、TD/RL、多保真、probe 或已关闭的 parent-patch/TGCA 路线。

## 1. 问题与证据级别

学长固定文件把 decision pairs 分成两种可观测语义：Draft 是同 experiment 下跨 physical runs 的首批方案，
Improve 是同一搜索局部的 sibling/contracted-parent 改进。当前 TF-IDF 与 Qwen value-transfer 都用单一 head，
可能把两个条件分布强行平均。本轮只问：在相同 train-only 字符表示下，**预固定的 pooled + semantic-specialist
margin 混合**能否稳定优于 pooled head。

这是已见过旧 test 的 retrospective discovery，最多授权 future exact-stratum Qwen/新 frozen cohort 的新预注册；
无论结果多好都不是确认性论文效果，也不得改写 0820 的旧 checkpoint 缺陷。

## 2. 固定输入

学长 repo commit 固定为 `baf6bddefe62b769b2fab699ff5805dd627dc69f`。只读以下已通过 raw-byte
credential-shape scan=0 的 Git LFS 对象：

| 文件 | SHA-256 | bytes |
|---|---|---:|
| `augmented_cards_current.json` | `5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb` | 604,190,866 |
| `merged_decision_pairs_filtered_runsplit.jsonl` | `c62dae814f7834b9beb3457d63fb60963636a31a811b216616e6912681bba2f4` | 2,858,161 |
| `batch_draft_decision_pairs_filtered_runsplit.jsonl` | `84adc361226899d4fd7b1a17cef3bf27884e76ec591566c7a4470fd525a94de7` | 1,714,459 |
| `batch_improve_decision_pairs_filtered_runsplit.jsonl` | `c2a062a81b7aa12457d4cb6a66aa102f8623bdfbb2961dd7d443c2c3e16ab516` | 1,143,702 |

已知但不作为选择依据的文档清单是 31,742 cards / 676 run groups、decision train/test=5,596/960、
draft=3,552/343、improve=2,044/617。正式 producer 必须重新得到这些精确数；不符即 fail-closed。

## 3. 固定表示、heads 与 arms

所有 arm 共用一个只在 **全部 decision-train endpoints** 上拟合的字符 TF-IDF：

- `analyzer=char_wb`、`ngram_range=(3,5)`、`max_features=30000`、`min_df=3`、`sublinear_tf=True`；
- 每张 card 只取 code 前 20,000 字符；不读 `obs/label/plan` 作为 feature；
- LogisticRegression：`C=0.5`、`max_iter=1500`，antisymmetric `(better-worse, worse-better)` 双向训练；
- CPU float64；sklearn/numpy/Python 版本写入回执；无训练期 test fitting。

固定拟合三个 heads：`P=pooled decision train`、`D=draft train`、`I=improve train`。测试 pair 类型由它在固定
draft/improve 文件中的 exact unordered identity 决定：

| arm | 测试 margin | 角色 |
|---|---|---|
| `pooled` | `m_P` | 唯一 baseline |
| `specialist` | Draft 用 `m_D`，Improve 用 `m_I` | secondary |
| `semantic_mix` | `0.5*m_P + 0.5*m_{D/I}` | **唯一 primary candidate** |

权重 0.5 不调参；不看 test 选 blend、不加 task token、不按任务翻转、不改 C/词表/截断。每个正式实现跑两次并
逐字节比较；独立 verifier 不 import producer，重新读输入、拟合三 heads 并复算全部门。

## 4. 指标、推断与固定门

固定报告 merged/draft/improve 的 pair micro accuracy、task-macro accuracy、逐任务 delta、margin/tie 数量与成本。
唯一 headline 是 `semantic_mix - pooled` 的 merged **task-macro accuracy delta**。

- task-clustered paired bootstrap：20,000 次，seed=`20260821`，以 task 为 cluster；
- secondary parent-clustered paired bootstrap：20,000 次，seed=`20260822`，cluster=`(task,parent)`；
- task consistency 只在 test pairs≥10 的任务上计算，但所有任务仍进入 headline task-macro/CI；
- 同时打印正/零/负任务数，不只报均值。

只有以下全部满足才得到 `DISCOVERY_UNLOCK_FUTURE_CONFIRMATION`：

1. merged task-macro delta `>= +0.010`；
2. task-bootstrap 95% CI 下界 `>0`；
3. 至少 15 个 supported tasks，且其中严格正 delta 比例 `>=0.60`；
4. draft 与 improve 两个子集的 micro delta 均 `>=-0.005`；
5. 所有完整性门、双跑与独立复核通过。

否则为 `DISCOVERY_NO_UNLOCK`；纯 specialist 或某个子集即使更漂亮也不能替换 primary。通过也只授权提交新的
Qwen 配置矩阵和 future exact-stratum frozen confirmation，不授权用旧 960 test 重训后写确认性结论。

## 5. 13 项长实验预检与资源矩阵

1. **方向/estimand**：只研究 Draft/Improve 可观测语义条件化，论文主容器与 first-960 不变。
2. **cheap tests**：synthetic 两语义 fixture、混合公式、train-only vocabulary、run overlap、篡改拒绝与 verifier
   不 import producer 必须全过。
3. **输入/禁区**：四个 SHA 精确；不访问 prospective state/vault、旧 checkpoint、API 或 tar/env。
4. **分布**：正式重算 31,742/676、5,596/960、3,552/343、2,044/617；merged 必须是两子集 exact disjoint union。
5. **平衡/支持**：逐 task/type 打印；不按效果删任务或改 dominant composition。
6. **checkpoint/resume**：CPU 单阶段、无 checkpoint；每次写全新原子 output，已有目录拒绝覆盖。
7. **泄漏/公平**：train/test endpoint 与 physical-run 交集均为 0；每对 exact
   `(task,client,hardware,time_limit,execution_timeout)` 相同；三 arm 共用同一个 train-only TF-IDF matrix。
8. **随机/数值**：bootstrap seeds 固定；margin/系数/输入 finite；ties 统一判错且单列。
9. **密钥**：原始四文件 scan=0；Git 只收聚合结果，push 前 filename/content scan 必须均为 0。
10. **wall-clock smoke**：synthetic 不读真实 test accuracy；真实运行前打印卡数/稀疏矩阵维度与内存估计。
11. **功效/统计**：唯一 primary、5 个门、20k 双 cluster bootstrap 与任务方向原样执行，不追参。
12. **退出码**：producer/verifier rc 立即记录，异常不能写成科学 `NO_UNLOCK`。
13. **append-only/hash**：source commit、输入、脚本、summary/per-task 与 manifest 全部哈希，双跑逐字节一致。

配置矩阵为 1 representation × 3 fitted heads × 2 formal producer repetitions，再由独立 verifier 同样重拟合两次，
共 12 个 LR fits；scientific runs=1 个固定数据发现门，GPU·时=0、API calls=0、底座更新=0。预计每个进程
3--12 分钟，四进程总 wall 12--48 分钟，峰值 RAM 预计 <8 GiB；线程固定为 1，单进程顺序执行。用户已明确授权
离开期间对正方向有利的实验，本固定零 GPU 矩阵不扩张其预算。
