# Decision Observability Funnel v1：正式裁决

日期：2026-08-21。正式代码 commit：`1b8a7b94f7175823763ef866e0dde2ce202828b7`。
状态：`VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION`。

## 核心正结果

固定的 3,252-parent release census 给出以下严格可加漏斗：

| 层级 | child slots / endpoints | undirected pair capacity / edges |
| --- | ---: | ---: |
| source-declared | 9,088 | 9,755 |
| raw cards | 7,760 | 5,998 |
| finite candidates | 7,760 | 5,998 |
| published decision graph | 7,760 endpoints | 5,897 unique edges |

source→finite child-slot loss share=`0.14612676056338025`，而 `C(n,2)` pair-capacity loss share=
`0.3851358277806253`。pair loss 比 child loss多 `0.23900906721724502`，attrition amplification=
`2.6356283154144`。换言之，14.6% 的 parent-level candidate-slot 缺口对应 38.5% 的 declared sibling-pair
capacity 缺口。

三段 pair loss 精确为：

- source→raw：3,757；
- raw→finite：0；
- finite→published：101。

总 source→published 缺口为 3,858，其中 source→raw 占 `0.9738206324520476`，finite→published 只占
`0.026179367547952307`。published graph 已覆盖 finite pair capacity 的 `0.9831610536845615`；端到端只覆盖
source-declared pair capacity 的 `0.6045105074320861`。因此该 release 的主要可观测性损失不是发布时少连了边，
而是 source-declared child slots 没有进入 raw card 集合后被组合数放大。

## 分层与边界

train/frozen/extension 的 child loss分别为 `0.15955983493810177` / `0.1189542483660131` /
`0.04400000000000004`，pair-capacity loss分别为 `0.4112200435729847` /
`0.3173546382600977` / `0.1392405063291139`；train 与 frozen 的冻结 role 门均通过。

23 个 tasks 中有 14 个达到 source pair capacity≥100 的支持门，其中 12 个 pair loss严格大于 child loss；只有
Russian text normalization 与 US patent 两个支持任务没有 source→finite loss。source-pair dominant task share=
`0.2185545873910815`，published-edge dominant share=`0.25606240461251484`，均完整披露而不作伪 IID 区间。

一个重要负边界是：全部 3,252 个 source decision parents 仍有至少两个 finite children，且全部有至少一条
published edge，decision-parent survival=`1.0`。所以不能写“38.5% 的决策点消失”；准确说法是
**within-parent sibling comparison resolution 被压缩**。

同样，9,755 是逐 `(role,parent)` 计算 `C(source_declared_size,2)` 的 declared structural capacity，不代表
9,755 次 agent 实际比较、执行或选择。9,088−7,760=1,328 是 parent-level missing slots；先前 status registry 的
996 是其自身纳入与去重合同下的 distinct target identities，两者分母不同，禁止直接相减或声称新身份数。

本结果不恢复 complete choice set：部分 source identities 仍不可恢复，missing candidates 没有 numeric outcomes。
它也不证明 MAR/非 MAR 个体机制、missing candidate quality、critic accuracy、search gain 或方法 novelty。可以与
独立的 902/996 status recovery（其中 893 execution errors）并列，形成“身份/status + 组合可观测性”的数据说明，
但不能把 status 比例机械分摊到 3,757 个 pair slots。

## 冻结门与完整性

六项预注册门全部为 true：pair loss≥0.15、pair-minus-child≥0.03、支持 tasks≥10、至少 8 个支持 tasks 有
amplification、train/frozen role gate，以及三段 loss 恒等式。

- producer×2 全 artifact 逐字节一致；
- 不 import producer 的 verifier×2 逐字节一致，独立重建最大差=0；
- focused tests=`6 passed in 0.19s`；完整 phase tests=`638 passed, 25 warnings in 54.79s`；
- forbidden scientific path hits=0；文件名/内容秘密扫描均为 0；正式产物可写文件=0；
- producer summary SHA-256=
  `e2bf11bc557ff147a11040821a6d3aa5a0650023ba585bbbf7f5e730fcf07ceb`；
- producer manifest SHA-256=
  `a74f33df91bfb12b12f2a5ca3ccbbad0f5796625472096d8f4e42e8bd84ce9f3`；
- funnel CSV SHA-256=
  `164e45714481650d711976a2644e8933cb1820500f11e3e606fec9331a38be8c`；
- 全量 `SHA256SUMS` 文件 SHA-256=
  `2ad84fb62d42ff4f0327ff58c85b11a5ca4c2be890c6f02286cea4498c6839da`；
- 完整只读产物：
  `/research/d7/spc/yzyang4/decision-observability-funnel/1b8a7b9-v1`。

GPU=0、API=0、base-LLM update=0；code、numeric outcome、pair orientation、prediction 与 prospective vault
均未读取。

## 论文作用

这是一个可独立成图/表的 D&B 正资产：只发布 retained pair accuracy 会把 source candidate censoring 压缩成
不显眼的 14.6% child 缺口，但真正的 pairwise decision denominator 已减少 38.5%。Benchmark 应同时报告
source child slots、declared pair capacity、finite capacity 与 published edges，避免把 conditional-on-observed
pair performance误解为 source-opportunity coverage。

它不改变 strict-future transition escrow、first-960/closure 或 clean Qwen G0/G1 的效果门。
