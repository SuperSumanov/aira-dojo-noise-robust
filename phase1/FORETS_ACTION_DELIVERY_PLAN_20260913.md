# 原子动作交付：未来被动双读出，不追改旧结果

2026-09-13 04:54 UTC记录；当前13213/13214未闭合且未揭盲。

源代码证据：现有incumbent只在完整expand_batch后持久化；在第二候选/debug之前，第一候选可能已执行、解析并接树。
旧seed30/31的部分批次最后journal没有可核定的已解析候选，因此不能事后猜测交付收益或补写截止前时间。
未来增加独立的逐动作记录，才能回答这是不是实际损失，而不只是源码上的可能。

## 最小实现

- 只在ForeTS自身的log_journal之后观察，原父类行为不变。要求最新节点已执行、解析并在journal内。
- 只选当时原journal.get_best_node；不按外部分数、archive有效性或后来的节点重选，不重试候选或调用LLM。
- 写独立action-incumbents子目录，与原step-*.commit.json完全分开；附带当时journal的搜索可见字段快照。
- 未完成analysis、未返回执行、预算后完成写入、只有data没有commit的记录不得用于新读出。
- fsync耗时也计入原600秒；保存目录及归档在任务sandbox外，不向生成器/critic提供额外观察。
- 功能默认关闭。仅未来明确冻结的新运行可两臂共同启用；当前source及原主终点不改。

## 未来分析及边界

同一新轨迹保留原完整迭代终点，以及截止前最后有效动作记录，两者均按原搜索可见选解规则。
用各自原submission独立评分，逐run公布方向、时间和差值，包括变差/无变化/缺失。
这不是外部oracle最优历史分数，不保证单调提高；同轨迹差也不是无记录开销的反事实。
应将其作为交付机制而非新算法，与critic选择收益分别报告。无需GPU/API的接线通过不等于已证交付收益。

重新核对：[MLE-STAR](https://research.google/pubs/mle-star-machine-learning-engineering-agent-via-search-and-targeted-refinement/)
已有针对代码组件的局部改进；[FML-bench](https://arxiv.org/abs/2605.17373)已有统一编辑设施及策略研究。
因此不把“改少量代码”“提供基线代码”包装为新颖突破。更强生成器也已做三批24程序，不能忘记旧结果重新重复。

本次只实现离线可测试组件，不提交新GPU，不激活新收费账，不改变保护cohort。
