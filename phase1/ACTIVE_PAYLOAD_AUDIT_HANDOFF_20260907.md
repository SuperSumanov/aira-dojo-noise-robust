# 中断恢复入口：12664的CPU分段实物复验

2026-09-07 09:43 UTC启动。恢复会话先fetch/读CURRENT_DIRECTION，再读本页；不要重新提交GPU。
用户要求在会话中持续工作，不建立定时任务。旧六小时语料摄取租约已经到期，本次没有延长它。

## 准确身份

- GPU原作业：12664，training commit `88522f74cafcd45778751c5315fa0a89a1704965`，已COMPLETED/0:0。
- 新核验源码：`c7c0aa4a0181be51d7c38dfa1942c6b68ca353e9`，68文件/43项实际Linux测试通过。
- 原AUTH SHA：`522cf8f5e8d3a4ca4f033494e11dc8c7526c2035eb623469b58d30661729e7ce`。
- 新SOURCE SHA：`9328c4fefebb2f92302a06c166ce318a39759ec128f77ece595ec89caa5bdbbf`。
- source目录：`/research/d7/spc/yzyang4/partitioned-postflight-source-c7c0aa4-r2-20260907`。
- 输出目录：`/research/d7/spc/yzyang4/critic-pivot-ampere-partitioned-postflight-20260907`。
- 前台supervisor：`/tmp/dispatch_partitioned_postflight_r2_20260907.py`，使用exp/bin/python启动；
  被核验进程仍使用R5/bin/python，源码不变，Torch2.11.0+cu128、DeepSpeed0.19.3。
- `run`启动时第一项为prefix1-rank0，进程组PID2005611；这是历史启动信息，使用前必须核存活/身份。

## 安全接续

1. 先调用上述supervisor的`status`，它只输出四项阶段进度、COMPLETE/FAILED与FINAL是否存在。
2. 检查已在当前会话中的长命令，或输出中的START/EXIT回执与相关PID。运行中不重复调用`run`。
3. 每项完整SUCCESS+COMPLETE才能算分组通过。缓存项只是分组通过，最终仍须重新hash两个完整bundle。
4. 若任一EXIT非0、FAILED或不完整START，保留所有证据并诊断；不直接覆盖日志或自动重试。
5. 只有四组和final的EXIT均正常、访问trace/security门通过，以及FINAL存在，才允许标记实物验收通过。
6. 终验之后还需独立检查SOURCE/四项回执/最终hash绑定及安全导出；不要把工程通过写成模型收益。

总CPU预算沿原INTENT的start/end记录，不因复制测试工具或重启supervisor重置。各项900秒，0GPU/0API。
原12535保持不动，数据准入仍为空，正式四fit与first960/Target300/522均不动。

## 本次已经遇到的失败及修复边界

第一次准备实际在R5缺pytest处失败，尚未读payload；原目录`partitioned-postflight-source-c7c0aa4-20260907`保留。
失败log SHA：`2af30ece6fd47af4b0f8491d078c89ae357e2c091e002ce42a93282db338c358`。
仅给测试进程私有叠加pytest7.4.3、pluggy1.5.0、iniconfig2.1.0共104文件；没有安装/改动R5，
生产核验进程不使用这层pytest路径。独立review检查旧失败目录全部原字节、68源码与两个确切Git版本，
并核对测试实际Torch/DeepSpeed导入来源与CUDA未初始化。
TEST_TOOLCHAIN SHA：`6adc5e739d809697748a36586767d6674a2e9c02321ffbf40831689903ce305e`。

原单事务CPU核验900秒超时也保留，不认为是数据错误或仅磁盘故障；本版增加可恢复事务与分阶段计时，
六role函数和最终整包hash标准不改。最终结果是否产生以实际回执为准，本页写入时尚未完成。
