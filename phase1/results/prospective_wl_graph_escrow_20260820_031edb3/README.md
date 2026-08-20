# Prospective WL graph prediction escrow v1

日期：2026-08-20。正式状态：`INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED`。

## 固定边界与结果

- source commit：`031edb34400781ca026bc9833ac7f850312ffb1c`；
- 自动 activation 时间：`2026-08-20T05:20:27.656860Z`，receipt SHA256=
  `0139670acc49c961e38e6851d0416d1e5bfa1c318024b50330c15d51823112fb`；
- 固定 snapshot：`88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8`；
- 5,643 endpoints / 223 physical runs / 25 tasks / 1,473 canonical sibling pairs；
- 该 snapshot 全部早于 activation：223 runs 与 1,473 pairs 均为
  `outcome_unread_support_only`，严格 post-activation primary 为 0；
- 四臂 `step_only_lr`、`wl_graph_lr`、`wl_graph_static_lr`、
  `wl_graph_static_tfidf_lr` 均全覆盖且 ties=0；
- graph 输入为 5,488 AST、150 token-sequence fallback、5 raw-line fallback；159 endpoints
  触发预固定 8,192-node cap；
- producer 墙钟 `10:22.30`、peak RSS=`3020036` KiB；独立 verifier 墙钟
  `9:50.30`、peak RSS=`3012904` KiB；两者退出码均为 0；
- 不 import producer 的 verifier 对四臂逐 endpoint 重算，最大绝对分数差全部为 `0.0`。

## 完整性与安全

producer 与 verifier 都在 syscall trace 下运行。syscall-aware 扫描对
`prospective_decision_v1/{label,outcome,scorer,score_index}`、v11 frozen/extension、0812 temporal
vault 等禁读路径得到 content opens=0、metadata observations=0。完整产物与 activation/protocol 共扫描
18 个文件，高置信 credential-shape matches=0。

程序没有效果指标入口；产物明确记录 `prospective_outcomes_read=false`、
`temporal_label_vault_read=false`、`v11_frozen_or_extension_read=false`、
`effect_metrics_computed=[]`、GPU=0、API=0、base-LLM update=0。

关键 SHA256：

- artifact summary：`ff49cee419a2cc90230fb0dad44058b9e61bb73fd90c38b77509b91b512c13be`；
- endpoint scores：`544e1b9ef499592d69f690a1ae411998ffead3d292be369666633e4ab4d246da`；
- pair predictions：`81def1b43a8dc14dbd724f6906bc5a3b7d056788d8d0c004f8176ba018498dc1`；
- independent verification：`40193ce983294a78c7de554639d07093fad277f1a4fec170ad013d624e3aa5d5`；
- syscall audit：`ef6e590f12a286c07c3b2c5f02b76be139dca1528708d0bdd2eef504ba2e1740`；
- completion receipt：`06a1ac0021344e265e8e609db51b60588e473756fa84a1e000e2784ac80bdf9d`；
- Git-LFS `full_artifacts.tar.gz`：
  `286677c36286566b5a2b0d3efb506e37648a041d8bbcdf9096b59dcb6e17ab00`。

## 裁决

这是一次可审计的支持性 prediction escrow 和 future-cohort 基础设施验收，不是准确率、搜索收益或方法正结果。
唯一 primary extension arm 仍是完整多视图臂，唯一 comparator 仍是 2026-08-13 已激活的 char-TFIDF；只允许在
自动 activation 之后生成、且未来满足 1,500 pairs / 150 decision runs / 15 tasks / dominant task≤0.25 的
strict cohort 上一次性检验。Guided Evolution 已覆盖 graph binary predictor 引导 program search，因此即使未来
效果为正，也只能写作真实 LLM-MLE choice set 上的迁移证据与 benchmark baseline，而非算法首创。
