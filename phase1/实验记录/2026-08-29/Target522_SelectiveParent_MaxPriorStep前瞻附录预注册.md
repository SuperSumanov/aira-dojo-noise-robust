# Target-522 Selective Parent：max-prior-step 前瞻附录预注册

## 为什么需要这份附录

887 development falsification 的正式总分类因无效 manifest-row primary baseline 必须保持 integrity fail；但唯一因果前提有效、
且对固定选择点全覆盖的 `max_prior_step` 被内容方法显著击败：content/step errors=`7/492`，paired content-only/step-only
correct=`488/3`，task/run breadth=`19/96`。这是结果已知后的强描述性证据，尚不是前瞻确认。

本附录在 Target-522 candidate、increment profile、内容结果、step-baseline 值与 paired disagreement 全部未见时冻结，只回答：
在 first automatically selected disjoint Target-522 increment 上，固定 identifier-erased content 规则是否仍提供简单 step
recency 之外的 recorded-parent 信息。

## 冻结时状态

2026-08-28T21:19:44Z 的 outcome-blind 结构核验为：

- LATEST=`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；
- Target-522 selection / lineage / selective-parent 三个 watcher 均为原 live 实例，`complete=false, failed=false`；
- selection root 固定为
  `/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2`；
- upstream selective formal root 固定为
  `/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522/formal-349b9ca-target522-v1`；
- 没有读取 candidate、profile、parent-recovery aggregate、label/outcome/prediction/accuracy/search utility；
- 没有修改、重启或新增 watcher。

机器协议：`phase1/tree_content_selective_parent_forward_target522_order_addendum_v1.json`，SHA-256=
`81df44e9194fb194611d6ffb7f3fba6c0a3fd1d7d2c0aa1ba6be19d33f84ce87`。

## 固定 estimand 与 control

内容规则完全继承 upstream Target-522 protocol：same-run、exact preceding depth、identifier-erased exact-set Jaccard、unique top、
margin≥`1006/16929`；future threshold、task filtering、rebalancing、cumulative rescue 均禁止。

primary population 是所有被该固定内容规则接受的未来 rows。`max_prior_step` 在完全相同 candidate set 内仅保留
`candidate.lineage.step < child.lineage.step`，若最大 prior step 唯一则预测，否则 abstain。primary paired comparison 只在
step baseline 实际预测的 content-selected rows 上比较；abstention 不算错，但 coverage 必须单独过门。recorded parent 不参与
ranking；不允许拟合、组合或调阈值。887 已证明无效的 manifest row 与退化 generation timestamp 没有 confirmatory authority。

## 预注册门与分类顺序

结构完整性要求 first-crossing selection、upstream selective formal、append-only increment、固定 content profile 与 upstream
逐项一致、所有 parent-present increment edges 满足 parent step < child step、候选/阈值/step rule 不变且只输出匿名聚合。

支持门：content selected≥`500`、step-comparable≥`400`、paired coverage≥`9/10`。强 breadth 至少 8 个 tasks、30 个 runs；
task/run 最小 discordance=`5/2`。aggregate 正门固定为 content errors / step errors≤`1/2`、content-only / step-only wins≥`2`、
step errors>0；breadth 要求 task/run 净 content-positive fraction≥`3/4`，最大单 task/run discordance share≤`2/5,1/5`。

分类严格按以下优先级：

1. 任一 integrity failure → `FORWARD_ORDER_BASELINE_ADDENDUM_INTEGRITY_FAIL`；
2. upstream Target-522 主证书不是
   `FORWARD_TIME_GENERALIZED_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY` →
   `FORWARD_SELECTIVE_PARENT_PRIMARY_NOT_CONFIRMED`，本附录不得救回；
3. support 不足 → `FORWARD_ORDER_BASELINE_SUPPORT_INSUFFICIENT`；
4. aggregate+breadth 全过 → `FORWARD_CONTENT_ADDS_BROADLY_BEYOND_MAX_PRIOR_STEP`；
5. 只过 aggregate → `FORWARD_CONTENT_ADDS_AGGREGATELY_BUT_BREADTH_UNSUPPORTED`；
6. 否则 → `FORWARD_MAX_PRIOR_STEP_NOT_RULED_OUT`。

development 与 forward rows 不混池；same-candidate repair、alternate selection/formal root 与结果后改门全部禁止。

## 双实现与未来执行

- producer SHA-256：`b84894a75a4c2493aa8d79a7ca0a2afbb025bc4865408ca67c224430deea2cbf`；
- independent verifier SHA-256：`b2368ea4cb956f9514aaa09e70e07e37b9847a840ab232782403e7b415007ee3`；
- test SHA-256：`e81433e0d188c200097b2a4fb73158d58cb46f4020f6615a3ccaedf9678b217e`；
- fixed formal runner SHA-256：`32cd4923775c03671026012ab976f0711f0d963dd675833f380e40b23e083674`。

producer 使用生产侧 snapshot/fingerprint 栈，verifier 不 import 新 producer，使用独立 selection/snapshot/fingerprint/upstream
verifier 栈，逐字段重建 selection、candidate set、content margin、step choice、paired table、breadth、gates 与 classification。
合成/攻击 focused tests=`30 passed`（其中本附录 9 个）。

runner 不接受 output root、selection root 或 upstream root 参数；三者由协议和 commit 固定。它只允许在两个既有 fixed roots
均 `COMPLETE` 后手工执行，fresh detached worktree 下做 producer/verifier A/B、全测试、file/network trace、credential scan
和只读 manifest。当前不启动 runner，也不新增 watcher。

## 范围与安全

即使未来 broad positive，也只能称 fixed content 在首个 disjoint future increment 上增加了 max-prior-step 无法解释的
recorded-parent 信息，且以 upstream 主证书通过为条件。不能称 semantic/causal ancestry 真值、一般 lineage 算法 novelty、
predictor effect/scaling 或 search utility。

prospective first-960/Target-300 values 与 Target-522 candidate/profile 未读，raw senior archives 未开，无 row-level release；
GPU/API/model-fit/base-update=`0/0/0/0`。
