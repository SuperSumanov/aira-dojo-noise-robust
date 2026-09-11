# ForeTS：已保存开发候选池的全执行诊断（2026-09-11）

## 执行前固定方案

主线仍是同预算 e2e 收益。免费生成入口暂不可用；本项不重试 API，使用13004已经保存、完整的
leaf/seed6/step1三候选池，检查**固定历史 critic 排序与即时程序成绩的关系**。这是开发诊断，
不是确认集、跨 seed 结果、搜索反事实或干净 scaling，也不重新运行13004搜索/旧pool恢复。

- 全部3个原程序，每个2次；顺序0/1/2，再2/1/0，不因中途结果调整。重复执行不是新的搜索seed。
- 原代码逐字节不变；保存的 critic 分数不重算，不调模板，不重选top-k（固定2）。
- gpu28，1×RTX3090、6 CPU，原2026-07-macos-v1 SIF和已实测原生GPU绑定。
- 每程序300秒（与原执行一致），Jupyter启动上限90秒，清理用原server.stop；分配55分钟，
  加观察到的5分钟KillWait总计上限1 GPU·h。与原8-run/19 GPUh e2e计划独立记账。
- 每次全新workspace/kernel；原public数据只读，可信宿主原MLE-bench grader读开发任务答案。
  程序不接触private目录；无API密钥注入、无生成/critic调用、无训练独立critic或agent底座。
- 原生Jupyter client直接执行保存代码，再调用同一原始grader；绕过搜索控制器，仅限即时程序诊断。
  不把该直接执行入口称为完整ForeTS。启动超时从默认300收窄到90，不改变代码执行300秒。
- slot0原生使用GPU；slot1/2原程序默认CPU，保持原样，不隐式更改算法/device/线程数。
  slot0/2请求8线程但仍处于6CPU分配，与原任务相同；记录运行时间，不把线程差异归为critic创新。
- 不复用13004原选择程序的旧成绩，全部在修复后的统一环境重跑；旧OpenCL环境不可作为当前对照。
- 失败、超时、无submission全部保留，不修程序、不补跑、不延长预算。
  基础设施启动/绑定/可信评分器失败则停止本项，余项写未运行，不能当作程序失败或负效果。

## 预先固定的读出

每次一行：slot、重复号、代码SHA、时间、执行/提交有效性、外部logloss、环境及代码commit。
固定历史top2等概率选择与全3等概率选择比较：先报有效提交概率，再报有效提交条件下的平均logloss。
若有失败，不把条件成绩差写成无条件收益；不为失败臆造logloss，不以新结果选k。
同时列全部候选两次成绩/中位数、历史排序与成绩次序（并列明确标记）。样本仅一个pool，不给泛化p值。

来源snapshot SHA：`1d0f2e417947d195a34354e436c687f1f495da0de247cd7ada00ea8d14dfee89`。
pool SHA：`557f6233667328b4d662774f229da19a721f165137b644d69d3aedabc3eceb2e`。
所有候选代码均已credential-shape scan=0且人工检查只读public CSV、写submission.csv。
既有测试/保护集不读取。原13004负结果不撤回。

## 轻量预检

13项清单适用项：固定全部候选/顺序/预算与哈希；测试超时/失败的读出与代码漂移拒绝；
公共输入和答案隔离；记录原嵌入seed而不另改；逐次保存结果；源文件/推送密钥扫描；墙钟硬限。
训练容量、checkpoint保存、训练集去重/任务平衡不适用（没有新模型拟合或多任务训练）。
两次执行只检稳定性，不伪造独立run。基础设施已有13076真实验证，不重复G0或人工GPU检查。

## 提交与运行

2026-09-11 09:08:24 UTC提交 **13085**，09:08:48 UTC观察RUNNING/gpu28，首个真实候选容器绑定已产生。
根 `/research/d7/spc/yzyang4/forets-closed-pool-20260911-pDXbiZ93`。
执行代码commit `eb173ba00656721b095cf9e38e99c13f8f5dbc4c`；原task/Jupyter源码tree `3aae90ae26b5ae7b65e6efed14fb49f2907c9c42`。
12文件控制包逐字节与Git相同；3个直接使用的原Jupyter/评分源码与tree相同。
archive SHA `08a1bb957f091eaaeabcd575585397726bf73e97b2ba0d1d0db5f7c94684da8e`；
部署manifest SHA `cb5c43cf212c48807fc42298592d45b5ddb44ed6466596a5ddad3c695c6ed002`。
10项新增CPU测试通过；新增fake-kernel测试首试两例因Windows路径断言失败，改成as_posix后通过，
不是GPU失败或新增效果。远端真实依赖导入及原snapshot代码校验通过，无额外人工GPU检查。
还没有完成结果，不能称正向收益；完成后统一读出并独立核验。
