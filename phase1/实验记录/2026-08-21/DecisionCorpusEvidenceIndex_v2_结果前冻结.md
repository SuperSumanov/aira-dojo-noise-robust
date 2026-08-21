# Decision-Corpus evidence index v2：source-aware 结果前冻结

日期：2026-08-21。状态：`V2_SCHEMA_FROZEN_BEFORE_BUILD`。本轮只重组已经独立验证并公开在仓库中的 JSON
收据，不读取 pair label、predictor output、prospective outcome、模型 checkpoint 或 API；GPU=0。

## 唯一问题

五项 v1 索引没有绑定当前论文叙事最关键的 source-opportunity 边界，容易让读者把真实 sibling 的**带标签片段**
误解为 agent 当时面对的完整 choice set。v2 固定新增第六个互异 estimand：source retention、missing child
identity 与 journal status 的联合 registry；原五项内容和边界不得重算或美化。

## 固定输入与输出合同

- v1 index 固定 normalized-LF SHA-256=
  `cfbe749f84114a633d902a358f8ef8243c4c4fe71433961c94e18494ca93769d`；
- 新增项只绑定三个既有独立 verifier receipts：raw completeness、source identity recovery、journal status；
- 所有 artifact 使用 UTF-8/LF 规范化 SHA-256，避免 Windows/Linux checkout 换行差异；
- builder 与 verifier 不共享构建函数；verifier 从固定 v1 和 source schema 独立重建整份 v2 后做深相等，再逐文件
  验 hash 与 JSON assertions；
- 固定六项顺序：decision corpus、source opportunity、label repeatability、normalized clone、deployment cost、
  prospective gate。

## 强制边界

无论构建结果如何，以下值必须为 false：完整 source choice set、missing-at-random、first/only novelty、
prospective effect、release complete。self-report 固定归类为 post-execution signal。新增项只能支持：已发布资源是
labeled sibling fragment，同时可发布高覆盖、parent-linked 的 missing identity/status registry。它不恢复缺失
数值 outcome，不证明 censor-aware selector 或搜索收益。

## 停止规则与验证

任一 source hash、entry membership/order、artifact hash、固定 assertion、路径逃逸或 UTF-8 JSON 门失败即停止，
不换收据、不删失败项。先提交本 schema；再从该 commit 的隔离 Linux worktree 构建两遍、独立验证两遍并要求
逐字节一致，运行聚焦测试和全部 phase tests。只有全过才生成人类 README、更新方向入口并推送正式结论。
