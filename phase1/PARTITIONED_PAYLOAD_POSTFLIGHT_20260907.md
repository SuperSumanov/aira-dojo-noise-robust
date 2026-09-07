# 12664检查点实物复验分段续跑

2026-09-07，用户要求会话中断后继续在会话内处理。仅恢复未完成的CPU复验，不扩大GPU/训练/数据权限。

## 已知事实与修改范围

原GPU已COMPLETED/0:0；原CPU核验于900秒守界停止，无VERIFIED。AUTHENTICATED SHA为
522cf8f5e8d3a4ca4f033494e11dc8c7526c2035eb623469b58d30661729e7ce，原目录不改。
实际四组payload合计41294576300字节，各组10323644043或10323644107字节。旧核验将前后整包hash和全部状态读取
置于一个900秒事务，无阶段完成回执。可确认是限时未完成，不能仅凭这一点断言数据错误或磁盘是唯一瓶颈。

只增加外层分段账本：prefix1/resume2×rank0/1四项，每项先核验三份payload的完整hash，
调用原六role实物检查器，再核相同文件全部hash和stat。最后第五项重新核两个完整manifest、所有文件hash、
源码/原AUTH、状态绑定、四项唯一覆盖后才写FINAL。不能仅凭旧AUTH或cached-part跳过最终hash。
原训练、原payload函数、数学/有限值/step/RNG/来源门都不改；不把合成工程验收称模型收益。

## 预算、失败及复现

- 1CPU线程、0GPU、0API；四个rank事务每个900秒，最终汇总900秒，子程序限时合计4500秒，另CPU测试180秒。
  每项预留20秒清理，单轮整体上限4800秒；不够剩余时限则不再开始下一项。
  这是新一轮只读审计预算，不把前次900秒失败抹去；估计实际需30—60分钟，非吞吐结果。
- 每事务在独立进程组执行，外层限时终止自身组，失败日志与部分输出保留，不自动重试失败项。
- 只有完整SUCCESS+COMPLETE、准确输入身份及sealed-file元数据一致的项可复用；缺项、重复、未知文件或漂移即停。
- 每段阶段时间落盘，成功回执fsync/只读；断线恢复不重复GPU或已完成的状态核验，最终全量hash仍必做。
- 固定新audit commit、保留旧training commit88522f74cafcd45778751c5315fa0a89a1704965。
  新源码本地负控、实际Linux原payload负控通过后才读取实尺寸payload。
- 每项文件访问trace及credential/protected-marker门，只有自身合成检查点可读。
  pickle仅限预先全hash认证的自有产物，不声称通用恶意pickle沙箱。
- ADMITTED_RELEASES、四fit、first960/Target300/522及旧12535不变；不新增定时任务。
