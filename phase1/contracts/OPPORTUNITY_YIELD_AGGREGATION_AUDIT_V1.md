# Opportunity-Yield Aggregation Audit v1

状态：`FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE`。

## 1. 目的与权限边界

本协议把已经确认的结构机制转成 closure 后的固定审计：真实搜索中，每个任务产生 canonical sibling pair 的速率不同，
因此 pair-micro 会按 decision-opportunity yield 对 run composition 做 size-biased reweighting。审计只回答这种重加权实际改变了
各 predictor 与预注册 arm contrast 多少；它不改变 generic estimand panel，也不覆盖任何既有实验 primary、truth、support、
effect 或 inference 契约。任何 alternate aggregation 或排名翻转均不得挽救失败 primary。

## 2. 执行门

仅在 chronological first-960、独立 accrual closure、结构门、全部 prediction escrow hash 与 exact common pair support
均通过后执行。arm 与 contrast registry 必须在读取 truth 前冻结。每个 cohort task 必须至少有一个 structural common pair 和
一个 informative common pair；否则输出 `NOT_IDENTIFIABLE_FULL_TASK_UNIVERSE`，不静默删除 task，也不计算 full-cohort
impact headline。

## 3. 固定恒等式

为避免把结构机会产率与 truth-tie/evaluability missingness 混为一谈，固定两级分解。对任务 `t`，`R_t` 是闭合 cohort 的
eligible physical runs，`S_t` 是 truth 过滤前的 exact-common-support structural pairs，`I_t` 是按实验原冻结 truth 与
evaluability 规则保留的 informative pairs，`Y_t=S_t/R_t`，`E_t=I_t/S_t`。固定复核：

```text
p_t = R_t / ΣR_t
q_t = S_t / ΣS_t
r_t = I_t / ΣI_t
q_t = p_t Y_t / Σ_s p_s Y_s
r_t = q_t E_t / Σ_s q_s E_s
TV_run_structural = 1/2 Σ_t |q_t-p_t|
TV_structural_informative = 1/2 Σ_t |r_t-q_t|
TV_run_informative = 1/2 Σ_t |r_t-p_t|
```

恒等式绝对误差容差固定为 `1e-12`，并发布全部任务的 `R_t/S_t/I_t/Y_t/E_t/p_t/q_t/r_t`。

## 4. 每个 arm 的实际重加权

令 `a_m_t` 为 arm `m` 在任务 `t` 内 exact-common-support pair credit 的算术均值：

```text
A_pair_m = Σ_t r_t a_m_t
A_struct_m = Σ_t q_t a_m_t
A_run_m  = Σ_t p_t a_m_t
A_task_m = mean_t(a_m_t)
delta_yield_m = A_struct_m - A_run_m
delta_info_m  = A_pair_m - A_struct_m
delta_total_m = A_pair_m - A_run_m = delta_yield_m + delta_info_m
W_m      = max_t a_m_t - min_t a_m_t
|delta_yield_m| <= W_m TV_run_structural
|delta_info_m|  <= W_m TV_structural_informative
|delta_total_m| <= W_m TV_run_informative
```

分别报告三个 component 的 realized bound fraction；分母为零时记 null，不改定义。所有注册 arms 必须同表出现。

## 5. 每个预注册 contrast 的实际重加权

先在同一 pair 上求 `credit_a-credit_b`，再在 task 内平均得到 `c_ab_t`。固定并列 pair-weighted、structural-weighted task、
run-weighted task、uniform-task 四个 contrast，并对 yield component、informative-filter component 与 total 分别验证匹配的
`range(c_ab_t)*TV` 上界。只有 `C_pair*C_run<0` 才记
`PAIR_VS_RUN_SIGN_FLIP`；恰好为零单列 `ON_BOUNDARY`。必须报告全部预注册 contrasts，禁止揭盲后新增有利比较。

这些量是确定性描述分解，不新增 p-value 或 CI；不确定性仍由 estimand panel 的 task bootstrap、LOTO、run-cluster
sensitivity 以及各实验原 primary 契约控制。

## 6. Related-work 边界

一般的 informative cluster size、cluster-average 与 unit-average estimand 区别并非本项目首创。直接近邻包括 Williamson,
Datta, and Satten (2003, `doi:10.1111/1541-0420.00005`) 与 Kahan et al. (2023,
`doi:10.1093/ije/dyac131`)。因此不得声称 size-biased cluster weighting、macro/micro 区别或其代数恒等式本身新颖。

本项目可守住的本地增量是：在真实 MLE-agent 搜索树的结果盲时间序语料中，证明 task-specific decision-opportunity yield
会随采集内生改变 derived sibling-pair benchmark 的任务混合，并在结果出现前冻结机器可执行、不得 rescue 的影响审计。

## 7. 当前访问声明

本冻结没有读取 prospective label、grade、outcome、winner orientation、prediction values 或 raw archive payload；没有计算
accuracy/effect/search utility；GPU/API/model fit/base-LLM update=`0/0/0/0`。
