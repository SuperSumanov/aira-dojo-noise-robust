# 13085：真实开发候选池全执行结果

2026-09-11。此目录是**已读出的开发诊断**，不是冻结test、确认性效果或新训练包。
三个代码可以用于复现/查错；不得在它们上调策略或训练后，再把本目录当独立评测。

- [完整方案、结果与边界](../../FORETS_CLOSED_POOL_20260911.md)
- [一行一次执行的原始CSV](runs.csv)
- [原定top2与uniform3读出](summary.json)
- [独立NumPy数值重评分及设备核验](independent-verification.json)
- [候选原代码与冻结计划](candidate-fixture.zip)：4成员、6776字节，SHA256
  `a72d2b7adcbd0f58ce58fac2c8127bc4b3a7565257fe230b6b06d6b1dc0efabd`。
  包含3份原代码及plan.json，无API凭据、任务数据、答案或逐行submission。
- [原任务同代码超时](prior-timeout.json)，不要与其后debug得到的最终2.5208混用。
- [实际资源](scheduler-completed.json)：1243秒单GPU，0.3452777777777778 GPUh。

程序仍需用户自己有权限的MLE-bench leaf-classification数据。环境为gpu28/RTX3090、6CPU、
原2026-07-macos-v1任务SIF及现行native绑定；代码SHA由plan.json固定。
完整任务运行入口/版本：`eb173ba00656721b095cf9e38e99c13f8f5dbc4c`，
数值verifier：`a1606bcb179215a7fa650cbbc45cde35d3228fb2`。
远端原始submission和native回执保留在
`/research/d7/spc/yzyang4/forets-closed-pool-20260911-pDXbiZ93`。

原程序：slot0用GPU，slot1/2默认CPU；未修改。三者排序由历史critic分数决定，非当前结果选出。
复测不等于新增独立搜索seed。所有失败保留，没有第三次补跑或延长候选预算。

额外路由只读定位单独记账：2次GET尝试，首试未载入网络设置而ConnectError，载入env_setup后HTTP200。
不包含私人余额/原始key响应，不是模型生成。它未暴露剩余免费请求配额，不能据此放行端到端实验。
