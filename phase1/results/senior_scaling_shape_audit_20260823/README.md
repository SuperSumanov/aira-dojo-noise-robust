# Senior 0820 scaling-shape audit

状态：`POST_HOC_DESCRIPTIVE_ONLY_TEST_TOUCHED`。

输入是学长已经公开的 0820 outcome 表，不是新 frozen outcome。来源绑定：

- branch commit：`ac008af8b907d319b694f26b0ba9cf4053b3bf69`；
- outcome document Git blob：`b41ab437395df034104624afbb678a1c0f987343`。

主要纠偏是：value→filtered-local 的单 seed 曲线仍随规模保持有序且 0.6B→14B 为正；真正没有规模顺序的是直接
local-only 训练。因此后续假设应写成“global scaling 部分迁移、naive local optimization 可能擦除”，不能写
“global 完全不迁移”。所有排列结果只是五点/四点曲线的事后有序度描述；旧 outer test touched、seed 极少、共享
endpoint，不能作为 confirmatory p-value。

纯 Python 计算与独立远端 SciPy `spearmanr` 的 rho/排列命中数逐项一致。机器可读值见 `summary.json`；修订实验
设计见同日 `GlobalLocalScaling_趋势复核与负控修正.md`。
