# RPM-style inference-only transfer：source-bound readiness（2026-09-02）

> 状态：`SOURCE_AND_LOCAL_RENDERER_FROZEN_NO_LIVE_CALLS_AUTHORIZED`。本文件只关闭
> Table 4B 直接竞品 baseline 的来源与本地表示缺口；没有调用模型、生成 prediction、读取前瞻结果或授权付费运行。

## 结论

RPM 的 optimized inference-only prompt 已从最新公开 v2 TeX source 逐字提取并固定，不再沿用 2026-08-22
记录的 v1 source hash，也不凭论文摘要重写 prompt：

- paper：*AI Research Preference Models*，arXiv `2608.13940v2`；
- source URL：`https://arxiv.org/src/2608.13940v2`；
- source：`458,133` bytes，SHA-256=
  `9910b62a9b8c9bb7da864fbb8534b124e697cf397a04103b43a273329e050ca0`；
- `sections/appendices/inference_only.tex`：`18,814` bytes，SHA-256=
  `f44585395980052a631d8eef19424759d22aebd3b3745fbfbd84d57b983a8c72`；
- second `lstlisting` optimized prompt：`1,950` bytes，SHA-256=
  `d64763172087a4243ddfa3ff364fad071c552af0783e5786a301a37bc338ff96`；
- arXiv 页面标注许可为 CC BY 4.0；原作者与 adaptation 边界已写入机器契约。

精确 prompt 位于 `phase1/baselines/rpm_inference_only_optimized_v2.txt`，机器契约位于
`phase1/rpm_inference_only_transfer_contract_v1.json`。纯本地模块
`phase1/rpm_inference_only_transfer.py` 只做四件事：hash/schema 校验、无截断 placeholder 填充、AB/BA 双顺序渲染、
严格 terminal `\\boxed{A/B}` 解析与位置一致性合并。它没有网络 transport、credential loader、panel/context selector、
outcome join 或模型调用路径。focused tests=`13 passed`。

## 为什么只能叫 transfer

RPM v2 报告在线系统使用 self-hosted Qwen3.6-27B，并以 maximum reasoning effort 和模型窗口能容纳的最大 context-node
数量运行 optimized prompt。Decision Corpus 当前至少有四个明确偏差：

1. corpus 不记录候选 plan；后续必须对两边对称填入固定字面
   `[PLAN_NOT_RECORDED_BY_DECISION_CORPUS]`，不得从 code/outcome 合成 plan；
2. 我方为审计位置偏差，对每个 pair 固定 AB/BA 两次；任一解析失败或两顺序不一致即 abstain；
3. exact Qwen3.6-27B checkpoint、serving stack、reasoning control 与 context packing 尚未匹配；
4. 我方是 recorded sibling-fragment 离线测量，不是 RPM 的在线 15-child tournament 或 end-to-end intervention。

因此最终表名固定为 **RPM-style inference-only prompt transfer**。只有 prompt、model/checkpoint、context builder、
reasoning、tournament 和预算全部精确匹配时才能另称 reproduction；当前不得这样写。

## 仍未关闭的运行门

真实调用前仍须另行冻结并复验：

- 只使用 decision-time 可见历史节点的 deterministic context builder，以及不 import producer 的独立 verifier；
- exact model/provider/checkpoint/context window、temperature、seed、reasoning 与 output budget；
- outcome-blind exact-common-support panel 与 append-only prediction escrow；
- first-960 identity + accrual closure 后才允许一次性结果 join；
- smoke 的 parse、position consistency、latency、token/cost 与无截断门；
- 总 calls、币种费用上限和单独用户批准。

本次资源与访问均为 GPU/API/model fit/base update=`0/0/0/0`，prospective label/outcome/prediction/accuracy/utility 与
candidate identity/private profile read=`false/false`，`counts_as_distinct_claim_evidence=false`。
