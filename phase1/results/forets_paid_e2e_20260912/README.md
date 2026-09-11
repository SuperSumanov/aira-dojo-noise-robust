# 固定收费八run结果

这是真实端到端失败结果：8个worker进程完成，0个有效最终解，40次程序执行全部exit1。
不能把null/空成绩解释为0分或两臂打平。所有槽位保留，没有挑选中途submission补分。

- summary.json / runs.csv / pairs.csv / blocks.csv：冻结读出器原始输出，没有回填API列。
- runtime-manifest-20260912.json：两块终态后的实际运行绑定。
- measurements.json / runs_cost_work.csv：另行提供的真实API费用、执行量与剪枝机会计数。
- independent-failure-verification.json：独立核对journal、执行回执、最终事件缺失与费用整数和。
- image-api-facts.json：原任务镜像的只读包版本和函数签名，不是新GPU验收或代码可运行证明。

主运行源码tree为f9087ae47470f7f1868c61405c3b827327f31c2c，controller commit为f051cfde。
报告及补充分析的Git版本不是实际执行版本。私有候选代码、prompt、原始终端日志和密钥没有放入此目录。
