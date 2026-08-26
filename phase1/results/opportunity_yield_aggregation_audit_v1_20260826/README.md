# Opportunity-yield aggregation audit v1

本目录在 first-960 closure、prospective outcome 和 prediction-value 揭盲之前，冻结一个只影响**结果解释**、不改变任何
既有 primary 的聚合影响审计。它处理的设计问题是：真实搜索 run 对 sibling decision opportunities 的产率不同，且结构
pair 进入最终可评价 common support 的概率也可能因任务而异；pair-micro 因而隐式改变任务权重。

## 两级权重链

对每个任务 `t` 定义：

- `R_t`：eligible physical runs；
- `S_t`：truth/evaluability 过滤前的 structural exact-common pairs；
- `I_t`：最终 informative/evaluable exact-common pairs；
- `Y_t=S_t/R_t`：structural opportunity yield；
- `E_t=I_t/S_t`：informative retention。

令 `p_t=R_t/sum(R)`、`q_t=S_t/sum(S)`、`r_t=I_t/sum(I)`，则机器实现必须逐任务验证：

```text
q_t = p_t Y_t / E_p[Y]
r_t = q_t E_t / E_q[E]
```

closure 后，每个预注册 arm 与 paired contrast 都必须并列报告 informative-pair、structural-pair、run-weighted-task 和
uniform-task 四种点估计。pair→run 的总变化精确拆为 structural-yield component 与 informative-filter component；每段及总
变化都报告 `range(task metric) * TV(task weights)` 的 sharp bound。该 bound 是最坏情况设计 leverage，不是 observed bias、
expected bias 或 predictor effect。

## Entry gate 与非挽救规则

审计只能在 first-960 与独立 closure receipt 均成立后运行，并要求冻结的 arm/contrast registry、exact common support，且
cohort 中每个任务同时有 structural 与 informative pair。否则固定失败状态为
`NOT_IDENTIFIABLE_FULL_TASK_UNIVERSE`，不得删除零支持任务后继续。

既有 generic headline、scaling primary、component-breadth primary、truth channel、support/effect gate 和 inference 均不改变。
任何 alternate weighting、component decomposition、task subgroup 或 pair-vs-run sign flip 都不能挽救失败 primary；精确为零
统一标记 `ON_BOUNDARY`，不得人为归为正或负。

## 与既有工作的边界

cluster size 与 outcome 相关时，cluster-weighted 和 individual-weighted estimand 的差别已有成熟理论；本项目不主张
size-biased weighting 恒等式或 informative cluster size 理论本身是新贡献。相关先例包括
[Williamson, Datta & Satten (2003)](https://doi.org/10.1111/1541-0420.00005) 和
[Kahan et al. (2023)](https://doi.org/10.1093/ije/dyac131)。本地贡献限于：在真实 MLE-agent 搜索的 chronological、
outcome-blind 语料中识别 decision-opportunity yield 对衍生 sibling-pair benchmark task mix 的影响，并在 outcome 前把两级
影响分解、sharp bound 与 non-rescue reporting 冻结为机器契约。

## 形式化复现

- contract source commit：`f97026221e099c11fa1ca8f2c13a95c389bea743`；
- contract SHA-256：`49a9e7c659057f1f8e7db032b7b25de14e3de9e594f969df20d3d3f80686cff3`；
- fresh Linux focused/full：`17 passed in 0.24s` / `1064 passed, 47 warnings in 77.09s`；
- independent verifier：18/18 checks PASS，`PYTHONHASHSEED=0/1` 两份输出逐字节相同；
- formal `SHA256SUMS` 文件自身 SHA-256：
  `60711365ffe7ccaf00b346a78303c65f2d80fe6a2f5eb99c9d506cad980ecf95`。

本次只访问固定 Git evidence 与合成算术测试；prospective label/grade/outcome/winner orientation、prediction values 和 raw
archive payload 均未读取。accuracy/effect/search utility 未计算；GPU/API/model fit/base-LLM update=`0/0/0/0`。
