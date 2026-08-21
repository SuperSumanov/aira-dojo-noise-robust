# Clean Direct-Decision component split：防 scoop 边界

日期：2026-08-21。状态：`GENERIC_NOVELTY_CLOSED_MLE_PROTOCOL_RETAINED`。本轮只核查 split 方法边界，
不读取新模型 outcome，不改变 component split、TF-IDF 或未来 Qwen 的任何数据和效果门。

## 1. 直接先例

1. **Refnd（2026-06）已经明确写出 component-level partition。** 论文把样本建成 proximity graph，令 connected
   components 形成数据划分，并把每个 component 整体分配给 train 或 evaluation；它还讨论 component 太大时的
   community split 与 post-filtering 权衡。这直接关闭“connected component 是新的防泄漏 split 方法”以及更宽的
   “首次按关系图决定 split unit”。来源：<https://arxiv.org/abs/2607.19376>。
2. **图 benchmark 的 edge split 泄漏已有直接诊断。** *On Leakage in Some Popular Benchmarks on Graphs* 指出随机
   edge partition 会切开 connected components，训练图中的路径可推断 held-out edge label，并主张 vertex split
   通常比 edge split 安全。来源：<https://openreview.net/pdf?id=VjqE1LTyBTQ>。
3. **不重叠 group 是通用模型评估常规。** scikit-learn 的 `GroupKFold` 明确定义每个 group 在各 fold 的测试部分
   只出现一次、group 不跨 train/test。它不自动求传递闭包，但足以说明“相关样本必须共同分组”不是新概念。
   来源：<https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html>。

这些工作领域不同，但已经覆盖本方法的抽象核心。Refnd 尤其与本实现同为“关系图的传递 connected component
整体入 split”，所以不能靠改名为 pair-component 或 run-component 获得 novelty。

## 2. 我们仍可写、且有数据支撑的部分

保留的是 **MLE-agent decision corpus 的具体 failure case 与解决契约**：

- Draft preference edge 可连接两个 physical runs；独立按 run 采样时，一条跨-run edge 只有两端同时落 dev 才能
  保留，更多 edge 会跨界被删。v1 实际删掉 485/5,240 个 outer-train pairs，且全部为 Draft；dev 只剩
  Draft/Improve=74/149，触发事前支持门。
- v2 把 physical-run pair graph 的 connected component 定义为最小不可分单位，在 seed=`20260821`、目标
  fraction=`1/10` 与原支持门均不变时得到 train/dev=`4,689/551`、零删 pair；dev Draft/Improve=`294/257`，
  train/dev/test 的 Card、run、unordered pair overlap 全为 0。
- producer×2、独立 verifier×2、gate×2 逐字节一致。这可以作为 benchmark construction、leakage audit 和
  reproducible data protocol；它不证明 Qwen scaling、search utility 或一种通用新算法。

## 3. 论文措辞边界

允许：`We expose a previously undocumented failure mode in MLE-agent decision corpora: run-level splitting can
selectively delete cross-run Draft comparisons; we therefore release a component-preserving split and receipts.`

禁止：`We introduce the first graph/component-aware split`、`a novel connected-component splitting algorithm`、
`the first leakage-free relational split`。正文应把 Refnd/graph leakage/group split 放入 evaluation protocol 相关工作，
把本结果定位为 MLE-specific empirical audit，而不是方法章节的 headline。
