# G-reuse target-A50 selector：0L28 后开发预检

日期：2026-09-05。状态：看到 0L28 失败后提出的 **development**；尚未读取本 selector 的任何结果。
机器协议 canonical-JSON SHA-256=`ffd04c96b0433cdf917798e6169d79b0341c19a9846025311c1d3038b237f448`。

## 1. 问题与假设

0L28 表明优化全图 D/A-opt 的 spectral50 虽广泛胜简单顺序，但对目标 local contrasts 的平均改善只有约
1.5%，且 p90 不变。新 selector 不改预算，而把每一步目标改成“每 valid token 最大化所有 local sibling
contrast 方差和的解析下降”。主均值优势部分是 objective-aligned sanity check；真正可证伪的是效应幅度、
task-macro、跨任务广度、集中度及 tail 不恶化。

## 2. 输入与隔离

沿用 0L28 的 exact historical-train 输入/SHA、4689 local、2745 record-consistent full G、790 basis、28 tasks
和 16K token 成本。真实 orientation/score/prediction/code 与 dev/test/first960/Target300/522 禁止读取；不输出
task/run/card/component/edge 身份。旧结果仅用于提出新问题和固定门，不参与 candidate scoring。

## 3. Arm 与算法

新 arm=`targetA50`；对照=`spectral50/cheapest50/hash50`，basis/full 仅作参考。所有 50% arm 每任务从同一
`local+basis` 图开始，额外 token cap 恰为 `floor((full-basis)/2)`，候选与 tie-break 相同。

当前 inverse 为 `K`，候选 incidence vector 为 `b`，local target vectors 为 `c_j`。加边后总目标方差下降为
`sum_j (c_j^T K b)^2 / (1+b^T K b)`；targetA50 以该值/token、15位量化、endpoint lexicographic tie-break
贪心。edge 不可拆，task 未花预算不得转移。单位 edge weight 不变。

## 4. Development success gates

全部通过才称 `TARGET_A50_DEVELOPMENT_STRUCTURALLY_SUPPORTED`：

1. 固定 population、相同逐任务预算、targetA50 预算利用率≥95%、所有 variance 有限非负；
2. pair-weighted mean 严格低于 spectral/cheapest/hash，且相对 spectral 至少降1%、相对两个简单基线各至少降3%；
3. task-macro mean 严格低于三个对照；pooled p90 不高于三个对照；
4. 相对 spectral 至少20/28 tasks 不劣、至少15/28严格更低；
5. 相对 spectral 的 task-level 正向下降最大单任务份额≤20%；
6. full 的 pair/task-macro 仍严格低于 basis，作为计算正控。

失败后不得改预算、门、目标权重、删任务或加入 identity/label feature 救回。本项门是看到 0L28 后冻结的开发门，
无论通过与否都不能称独立确认。

## 5. 资源矩阵与 ETA

单 CPU、BLAS=1；producer A/B 与 grounded verifier A/B 各≤300秒。预计实现/测试/正式 70--115 分钟。
GPU/API/neural model load/fit/base update=`0/0/0/0/0`。

## 6. 随机性与统计单位

完全确定性，无 seed。任务是广度和集中度单位；edge 是有限总体 estimand，不作独立样本，不报 p 值。

## 7. 公平

四个 50% arm 的 local、basis、remaining、valid-token cap、edge weight完全相同，唯一变化是排序准则。targetA50
不得获得 global pool、跨 task 预算或更细 edge 拆分。basis/full 不参与同成本胜负。

## 8. 完整性

credential/SHA 前后门、只读 audit hook、无网络/子进程、独占结果根、mode-0600、producer/verifier A/B、命令/环境/
耗时/stderr/manifest 均与 0L28 同级。producer 使用 shifted inverse；verifier 使用 grounded inverse且不 import新producer。

## 9. 输出

仅 aggregate、匿名 task 数值行、选择集合 hash/count、门和资源计数。不得输出 selected edge 或任何身份。

## 10. 解释

通过只说明 target-aware optimal-design heuristic 在这个历史 MLE graph 上比通用 spectral heuristic 更贴近 local
decision variance，并为未来 cost challenger 提供开发依据。它不证明神经 critic、校准或搜索收益；主均值是优化目标，
不能单独当新发现。失败则关闭这个 selector，不继续改目标。

## 11. 相关工作与后续门

这是 c/V/A-optimal experimental design 的领域化，不申算法首创。即使 development 通过，也只能在权威新包到来后
先重新冻结且独立验证 selector manifest；任何真实模型 arm 仍需 core 先通过、G0计价及精确 GPU·时批准。
