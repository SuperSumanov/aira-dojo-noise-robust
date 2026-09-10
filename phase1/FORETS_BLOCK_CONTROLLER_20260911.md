# 新固定分块控制器：核心接入与上下文整理（2026-09-11）

## 本轮实际做了什么

目标仍是同预算下critic对最终外部分数的影响。本轮不调用生成器、模型、任务数据或GPU。
旧campaign固定seed6/7、30分钟step、40次请求、首对后停止，不能直接用于新seed8/9的两块方案。

新增 `forets_block_controller_20260911.py`：

- 每块恰好4run，预先固定顺序；从已完成的prepared/config字节绑定，不重新生成或换seed。
- 复用真实pinned SrunPoolLauncher的运行与dispatch方法，只加新矩阵控制层；不修改13004旧源码。
- 核对60分钟step、3540秒worker、100请求上限、零重试；两块上限仍是更正后的280分钟/块。
- 预留900秒启动与30秒最后清理；没有完整下一步时间时不启动，**不因此提前取消仍在跑的前一步**。
- 在路径检查之后、真正dispatch之前再核时限；最后一个run期间仍检查服务存活与清理截止。
- 服务丢失停止后续/活动工作；单run失败不丢弃伙伴、不补跑、不自动扩展至另一块；拒绝旧尝试自动恢复。

CPU测试对确切源码 `3aae90ae26b5ae7b65e6efed14fb49f2907c9c42` 的真实pool方法执行，
仅替换配置fixture、Slurm/process/accounting边界与时钟；连同输入读取保护共13项通过（1.10秒）。
人工用例覆盖两块完整运行、worker失败、已有attempt、启动超时、路径检查超时、最后run服务中断、
下一步预算不足、模拟挂起清理、非法矩阵与服务缺失；另核读取字节上限、hash和越界路径。
人工3930秒时钟不是实际Slurm运行或调度保证。
开发时测试fixture曾因目录层级与人为断服务时间点错误而失败，已修正；不是GPU/模型实验失败。
测试从可fetch的学长commit065b0fba和已提交0013补丁，在临时Git index中重建这一份pool文件；
SHA256固定为12fcf5fc727de820a208ca88ee1bd82c58f97842653c3ce463f8b171903d2b79，不依赖仅本机存在的组合树对象。
这避免新clone为运行本测试而重复构建整份实验源码；不改工作树或学长分支。

远端独立代码根 `/research/d7/spc/yzyang4/forets-block-controller-20260911-t7d8kr`。
两次只读inspect分别绑定已有block1/block2的4份配置，全部仍 `NOT_LAUNCHABLE`；
新包原文件未更改、未部署服务、未派发worker。执行命令：

最终控制器本地/远端源码SHA256均为3d111b66678e656a7a1699f5b15c1ba8213fe0cc56ac6f693601ac45a97d0831。

```text
/research/d7/spc/yzyang4/venvs/aira/bin/python /research/d7/spc/yzyang4/forets-block-controller-20260911-t7d8kr/forets_block_controller_20260911.py --draft /research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4 --block 1
/research/d7/spc/yzyang4/venvs/aira/bin/python /research/d7/spc/yzyang4/forets-block-controller-20260911-t7d8kr/forets_block_controller_20260911.py --draft /research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4 --block 2
python -m pytest phase1/tests/test_forets_block_controller_20260911.py -q --disable-warnings --maxfail=1
```

复核配置仅为新控制器的输入绑定，不是重跑上一轮配置生成或独立verifier。

## 尚未完成与可说的结论

**没有新的critic收益/干净scaling结论，也没有完整生产启动器。** 当前CLI只有inspect，无execute选项。
真实适配层仍需把服务启动/清理实际限制在预算中；核心事后时限检查本身不能中断一个阻塞的path-check/service启动。
OpenCL隔离事实与checkpoint历史输入模板均待外界回复；固定路由新鲜检查也尚未做。
旧服务、旧环境、原SIF和prepared.json不改，不能靠翻转readiness或复用旧execute()绕过这些缺口。

新控制层解决的是怎样正确运行既定对照，而不是新学习算法。能否形成正结果要靠真实、全部保留的跨seed配对。
6步增加可发生筛选的决策数；共同随机排列降低同池重采样混淆，但两者均不保证critic有信息或最终成绩提高。
若后续为负，保留事实；不得挑seed、改最终读出、把新语料不同预算混入或把当前模型套进确认cohort。

## 上下文维护

重写两份当前记忆文件：CONTEXT_HANDOFF_CURRENT.md从181行降到82行，NIGHT_WORK_20260911.md从54行降到38行。
前者只留现在的目标、实测、已完成勿重做、未解依赖、精确路径；后者只留窗口内未完成任务。
旧的“17 GPUh”“未生成配置”“未开monitor”等状态从当前索引移除，但原文件全文在Git
`aac4acc0d74c3ac27a64f4959b1225ee9df54951` 留存，详细结果/失败报告未删除。
不另造一套memory索引，不用旧摘要覆盖CURRENT_DIRECTION最新裁决。

本轮最后队列检查：2026-09-10 21:19:52 UTC，仅12535 held。学长branch仍065b0fba，未改其分支。
