# Parent-matched failure-risk pair support v1

日期：2026-08-17。裁决：`VERIFIED_FAILURE_RISK_PAIR_SUPPORT`。

结果前 commit `526e3ad6c0d444f22d3fee99f9ab5506d7a06c39` 冻结 691 个 train execution failures 的
credential-scan-before-parse code 支持审计。远端完整 `phase1/tests` 为 `354 passed in 27.96s`；正式双跑
逐字节一致，SHA256=`77b81f8d4356d74f14647c8a12281af201fe34c75da04ed077febdac17b400f1`。

691/691 failure nodes 均找回非空代码。按每 parent 只取一个 failure，再确定性匹配同 parent、同 physical run、
代码 SHA 不同的 retained success sibling，得到 494/494 unique failure parents 的 494 对，覆盖 13 tasks / 126
physical runs。8 个任务至少 20 对；dominant task=134/494=`0.27125506072874495`；frozen run overlap=0，
identical-code-only parent=0，inconsistent-run parent=0，credential target SHA=0。全部冻结支持门通过。

第一次远端 wrapper 在测试/输入读取前遇到 GitHub HTTP 500；同 commit 重试成功。仓库只提交聚合结果，
不提交代码、diagnostic、grade 或 pair identity。完整产物在
`/research/d7/spc/yzyang4/failure-risk-pair-support-v1-526e3ad/`。

该结果允许构造 train-only、parent-matched 的 failure-risk benchmark；不说明静态代码可预测 failure，
更不说明 controller 提高搜索 utility。方法资格由单独冻结的 LOTO 实验决定。
