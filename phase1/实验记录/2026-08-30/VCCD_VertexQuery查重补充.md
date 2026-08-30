# VCCD vertex-query 查重补充

## 新发现

把查询从“比较 edge”收窄到“读取 vertex scalar value”仍不构成一般方法新颖性。Graph-signal sampling 至少从 2015 年起
已用 experimental design 选择观测节点，2022 年工作更明确采用 D-optimal / volume-maximization 近似；JMLR 2014 则已把
optimal design 用于 ranking comparison graph。

## 对论文措辞的影响

不得宣称首次 D-opt vertex sampling、首次付费节点观测或首次 ranking optimal design。未来可检验的窄主张只有：已知设计
思想在 MLE 搜索树的特殊 oracle 下是否有效——一次 endpoint execution 给出 scalar grade，但比较标签只在 sibling clique 内
派生；候选受 task、physical run 与 parent topology 限制；critic 必须迁移到 disjoint future runs；完整报告 dependent rank、
噪声、泄漏和实际执行成本。

这只收窄 novelty，不改变 Target-522 已冻结的三臂、预算、统计门或自动执行链，也不削弱数据集、benchmark 和 audit protocol
作为论文容器的主贡献。
