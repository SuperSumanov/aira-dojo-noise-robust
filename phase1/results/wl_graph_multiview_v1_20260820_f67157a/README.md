# WL graph / multi-view scorer bundle v1

正式状态：`INDEPENDENT_WL_GRAPH_MULTIVIEW_REFIT_VERIFIED`。这是一个 v11-train-only、outcome-unread 的
benchmark extension bundle，不是 accuracy 或 search-utility 结果。

## 固定范围与结果

- build source commit：`f67157ad35385019f11a79291a1df8cdf4311806`；
- 训练范围：5,499 endpoints / 4,263 sibling pairs；只读 v11 train b0；
- 四臂：`step_only_lr`、`wl_graph_lr`、`wl_graph_static_lr`、`wl_graph_static_tfidf_lr`；
- graph：WL=2、65,536 hashed dimensions、8,192-node cap；5,499/5,499 使用 Python AST，254 个触发 cap；
- build runtime=`1316.8736707940698` 秒；`/usr/bin/time` wall=`21:57.84`，peak RSS=`5841032` KiB；
- independent refit runtime=`744.517504921183` 秒；wall=`12:25.60`，peak RSS=`5879468` KiB；
- producer bundle roundtrip 最大分数差=`6.483702463810914e-14`；
- 不 import producer 的 verifier 对所有数值数组最大差=`0.0`，对 5,499 reference rows 最大分数差=`0.0`；
- focused tests=`10 passed`、该 commit 的 phase1 全套=`473 passed`；后续 escrow commit 全套=`477 passed`；
- GPU=0、API=0、base LLM update=0；v11 frozen/extension、0812 label vault、first-960 outcome 均未读，
  `outcome_metrics_computed=[]`。

关键 SHA256：

- bundle：`df02cd1f5ba74be6b171ee9c377eeb58cf209a310a470b2ade671f2db03ee19e`；
- build summary：`d8d1b57172e4b63f391a0ca93b1213c0f040adf9592637c38d057ad6576622f5`；
- train reference：`51cd9589ccae31162816485a60b8af1675127b416c55264fdead8bc8d69a8b1b`；
- independent verification：`9918e6797b8f48fa9bb72e8cb740d1d5fab0ef81c0a961809fef40250b3e6b6e`；
- `full_artifacts.tar.gz`：`c8b3bd9044e61e3d911f4763a613cb1b3a8240ad376447cba58a0abfc1541f2a`。

完整 tar 在 Git LFS 中，包含 NPZ、train reference、summary、独立复核、build/verify 日志、rc、status、
SHA manifest 与 syscall traces；打包前逐文件 credential-shape scan=`0`。远端原始 append-only root 为
`/research/d7/spc/yzyang4/wl-graph-multiview-f67157a-v1`。

## 边界

原协议的手填 `frozen_at_utc` 已由远端时钟证明是未来时间戳并永久作废；bundle 的配置、输入与独立数值复核仍
有效，但该字段不能用于 temporal precedence。后续已在 commit `031edb34400781ca026bc9833ac7f850312ffb1c`
预注册自动 activation receipt：只有 receipt 之后生成的 physical runs 才能承担严格方法效果；更早 blind
prefix 只作支持。Guided Evolution 与 GRAF 已覆盖 graph/binary program predictor 的一般方法主张，所以本 bundle
只用于补齐 baseline family，不申算法 novelty。
