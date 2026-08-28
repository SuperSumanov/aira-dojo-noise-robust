# Selective Parent Recovery：因果顺序基线 Falsification 预注册

## 为什么必须补

887 上已发布的 content-based selective parent certificate 很强，但现有 controls 是 uniform random、去 depth 和同层错误候选。
数据协议又保证非 root 的 recorded parent 来自更早 step，因此审稿人可以提出更廉价解释：在同 run、前一 depth 中直接选
`step` 最近或 blind manifest 中最近出现的候选，可能已经足以恢复 parent；如果如此，identifier-erased code content 的
独立贡献被高估。

本轮是已知正结果后的 falsification，不冒充原始预注册。冻结时已知 content test selected=`2691`、correct=`2684`、
errors=`7` 和 threshold=`1006/16929`；尚未读取三个 order baseline 的 coverage/correctness、paired disagreement 或任何
task/run breadth。

## 固定比较

primary population 逐字节复现原证书的 145 个 test runs、2,907 ambiguous edges 和固定 threshold 下 2,691 accepted
edges。候选集、fingerprint 和 content prediction 不变，不重新训练或选阈值。

两个 primary cheap baselines 均只能使用 child 之前的信息：

1. `max_prior_step`：在固定同 run、depth-1 候选中，只看 `candidate.step < child.step`，取唯一最大 step，否则 abstain；
2. `nearest_prior_manifest_row`：只看 blind-manifest row position 早于 child 的候选，取最近一行。

`latest_prior_generation_time` 只作 secondary；不能 rescue primary。baseline 不使用 recorded parent 排名，不拟合参数、不组合、
不按结果选 threshold；abstention 不算错误，pairwise 比较只在该 baseline 真正预测的相同行上进行。

## 结果前门

每个 primary baseline 都必须有至少 2,000 comparable rows 且覆盖≥9/10。要排除 cheap-order explanation，content 在同一
可比行上的错误数必须不超过 baseline 的一半，且 `content-correct/order-wrong` 至少是
`content-wrong/order-correct` 的两倍；两个 primary baseline 必须同时通过。

强分类还要求对固定 strongest threat（baseline error 最少，tie 按预写顺序）有匿名 task/run breadth：至少 8 tasks / 30
runs 达到 disagreement support，净 content-win group 比例各≥3/4，最大 task/run disagreement contribution share≤2/5、1/5。

顺序固定为：strong broad；aggregate advantage 但 breadth 不足；cheap order 未排除；baseline support 不足；integrity fail。
任何 below-gate 都必须弱化 content-specific 解释，不得用 generation-time secondary、train population、替代 threshold 或更多
887 subgroup rescue。

## 边界

只读已公开 outcome-blind 887 snapshot 与已发布 aggregate certificate；不读 first-960/Target-300 values、Target-522
candidate/profile、raw senior archive、label/outcome/prediction/accuracy/search utility。输出只有匿名聚合，不输出 task/run/
card/parent/code/per-edge values。GPU/API/model-fit/base-update=`0/0/0/0`。
