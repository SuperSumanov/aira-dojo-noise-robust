# Vertex-Cost Contrast Design：正方向工程冻结与查重边界

日期：2026-08-30
状态：`ENGINEERING_CONTRACT_FROZEN_BEFORE_TARGET522_CANDIDATE_PROFILE_OR_VALUES`

## 1. 这次真正改变了什么

当前所有 endpoint-budget 工作都把一次 endpoint execution 当真实成本，却常用诱导出的 pair rows 计 label yield。若同一 parent
有 k 个已执行 siblings，确实可物化 `k(k-1)/2` 条 pair rows；但这些 pair 全由 k 个 scalar grades 派生，独立 contrast rank
至多是 `k-1`。继续最大化 raw pair count 会奖励同一 clique 的二次膨胀，并可能解释此前 yield arm 的大任务集中、task-macro
下降与 calibration 恶化。

新工程线按真实付费单位选 endpoint 顶点，但在 contrast space 中计信息。向已有 k 个 selected siblings 加一个 endpoint 时，
centered scatter 的精确 rank-one 更新为：

`q = sqrt(k/(k+1)) * (x_new - mean_selected)`。

D-opt marginal 为 `log(1 + q^T A^{-1}q)`。尚未打开的 parent 作为两 endpoint action，按每个新 endpoint 的 marginal gain
比较；所有 tie 用 SHA-256 固定。terminal task/run endpoint cap 分别为 `max(2,ceil(B/5))` 与 `max(2,ceil(B/10))`，未知
不可行性 fail-closed。一次完整 clique 的每条 unordered pair 在未来 fit 中权重固定为 `2/k`，总权重恰为 `k-1`；双方向各取一半。

## 2. 查重后不允许宣称的 novelty

Guo et al. 早已研究 D-optimal pairwise experimental design，并给出子模 greedy 加速：
<https://arxiv.org/abs/1901.06080>。feedback-graph bandit 也早已系统研究“执行一个 action 得到邻接 side observations”：
<https://arxiv.org/abs/2105.14260>。因此不能宣称首次 D-opt、首次 active preference learning 或首次 graph feedback。

仍有差异、但必须靠结果证明的窄点是：MLE 搜索树中付费的是 endpoint execution；pair labels 是 sibling grades 的依赖派生物，
成本、独立信息秩、task/run 异质性与外部 run-clean confirmation 必须同时审计。它首先是数据/benchmark 的 acquisition contract，
不是通用算法首创。

## 3. 当前实现与反例测试

新增纯 outcome-blind 核心 `vertex_cost_contrast_design.py`，只接受 parent/task/run、endpoint code 与 endpoint budget；接口没有
label、grade、outcome、prediction、accuracy、utility 或 runtime。code feature 是无需 corpus fit 的固定 128 维 signed hashed
Unicode char 3--5 grams（仅在哈希时 UTF-8 编码），截断 20,000 chars、sublinear TF、L2 normalize；未来 code 不改变 vocabulary。

实现 SHA-256=`e241864e136deab45c7ac58386d91bdf5eacb98ded2241a0a4a1605d8bfcd68f`，测试 SHA-256=
`7e799d46b3687fecf16d06425b987bc3157f110bb1f8f460145e98a55e7f0518`。synthetic tests=`11 passed in 0.25s`，覆盖：

- clique raw rows 为二次而 contrast rank 为线性，`2/k` 总权重精确等于 `k-1`；
- Unicode 字符边界、truncation 与 array-like 输入归一化确定性；
- exact budget、nested prefix、task/run caps 与 tie 确定性；
- Sherman-Morrison 累计 logdet 与 dense `slogdet` 一致；
- 正交 parent contrast 累积 rank；
- cap 不可行和 endpoint 跨 parent 均 fail-closed。

## 4. 当前不能说什么，下一门是什么

这不是 accuracy 正结果，也不是 Target-522 科学预注册。冻结时 Target-522 candidate/COMPLETE/FAILED 均不存在，最新纯结构 run
count=`466`、snapshot dirs=`116`、config-v2 count=`0`，prospective values 未读。机器工程协议为
`vertex_cost_contrast_design_engineering_v0.json`。

在 candidate 出现前还必须补齐：可信 code-only exporter、固定 run-level acquisition/eval split、exact-B uniform 与现有 yield
baselines、固定 critic + rank-normalized loss、独立非导入 verifier、支持/晋级门、CPU fit 数和 ETA、fresh full tests 与访问审计。
这些全部冻结后才能让未来 cohort 做一次效果检验。OpenRouter evaluator 不进入 v0；若它的 smoke 后来可靠，只能在另立协议和
未触碰 cohort 中作为 acquisition prior，不能事后混入本方法救结果。

本轮 GPU/API/model fit/base update=`0/0/0/0`。
