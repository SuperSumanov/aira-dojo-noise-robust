# Opportunity-yield 重加权恒等式与 benchmark 影响上界

日期：2026-08-26

性质：对已报告结构统计的确定性数学推论；不读取 outcome、label 或 prediction。

## 1. 恒等式

对任务 `t`，记：

- `R_t`：eligible physical runs 数；
- `P_t`：canonical sibling pairs 数；
- `Y_t=P_t/R_t`：每 run 的 observed decision-opportunity yield；
- `p_t=R_t/R`：run-weighted task distribution；
- `q_t=P_t/P`：pair-weighted task distribution；
- `μ=Σ_t p_t Y_t=P/R`：全语料平均 pair yield。

则有精确恒等式：

`q_t = p_t × Y_t / μ`。

因此 pair sampling 是 run distribution 对 opportunity yield 的 size-biased reweighting，并且：

`TV(p,q) = 1/2 × Σ_t p_t × |Y_t/μ - 1|`。

这给出了一个无需 outcome 的机制解释：只要任务间 `Y_t` 不同，pair-micro 的任务权重就会偏离 run composition；偏离量正是
归一化 yield 离散程度的一阶绝对矩。

## 2. 对 headline 指标的 sharp bound

令 `a_t∈[0,1]` 为任意 predictor 在任务 `t` 上的固定 task-level 指标。pair-weighted 与 run-weighted 聚合之差为：

`Δ(a)=Σ_t (q_t-p_t)a_t`。

由 total variation 的变分刻画：

`sup_{a_t∈[0,1]} |Δ(a)| = TV(p,q)`。

上界是可达到的：取 `a_t=1` 于 `q_t>p_t` 的任务、其余为 0，即得到正向极值；反向集合得到负向极值。若指标的 task
range 只有 `W=max_t a_t-min_t a_t`，则进一步有：

`|Δ(a)| ≤ W × TV(p,q)`。

## 3. 当前 snapshot 的含义

固定 `7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1` 上，已由 producer 与 independent
verifier 得到：

`TV(p_run,p_pair)=0.337082500713674`。

所以 pairing construction 对任意 `[0,1]` task-level 指标具有最多 `0.337082500713674`，即约 33.71 个百分点的聚合
leverage。这个数是当前结构下的 sharp worst-case bound，不是某个 predictor 已观察到的 accuracy 偏移，也不是 expected bias。
closure 后应在 exact common support 上报告每个 arm 的实际 task vector，再把观测到的聚合差与该结构上界并列。

## 4. 论文可用主张与边界

可用：pair-micro benchmark 的 task mixture 是 run composition 经 decision-opportunity yield 做的 size-biased reweighting；
当前结构允许 aggregation choice 对 bounded task metrics 产生实质性 headline leverage。因此 sampling unit、task weights、yield
provenance 和 estimand 必须显式发布。

不可用：当前已经观察到 33.71 pp accuracy 差；task-macro 一定高于 pair-micro；某个 predictor 因此获益；或该上界在最终
first-960 snapshot 不会变化。

直接数据证据：`phase1/results/structural_weight_trajectory_7cda_20260826/trajectory.json`。
