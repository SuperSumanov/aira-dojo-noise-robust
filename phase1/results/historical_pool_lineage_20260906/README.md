# 实际 launcher 来源恢复（2026-09-06）

本轮推进正式训练的生产来源阻塞；不是新的模型收益，也不恢复旧HCE、多保真或lookahead。
用户已批准合理修复，本轮只用两CPU做固定历史档案核验，无GPU/API/fit。

## 最终合并结果

code `e7244fb247cd68bea7b827071691e7f42897f608`；lineage SHA
`fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981`。
两次全量实际扫描183/186秒，15项便宜测试通过；全部143份archive回执、汇总和lineage逐字节相同，独立图算法复核通过。

|实物证据|核验结果|
|---|---:|
|定位到真实launcher的固定历史run|676/676|
|manifest / 记录实例|144 / 143|
|srun_pool / local_gpu_pool清单|85 / 59|
|Slurm step一致 / 不一致|447 / 1|
|有local execution_id记录的固定run|228|
|原hold闭包组件 / 阻断run|139 / 538（不变）|
|全成员在固定范围的manifest / 涉及run|98 / 495|
|原hold及未解决关联排除后结构条件完整的run|84，覆盖24个recorded config strata|
|代码快照路径无权限 / 不存在|85 / 58|

**84不是可直接训练的合格包，local execution_id有记录也不等于其实际GPU/环境已独立核验。**
160条本归档未绑定记录另查：8条已在同实例其它归档绑定，2条只有目录候选且实例未确认，
150条仍无匹配来源，涉及140种config ID；不能把条数叫额外physical runs，也不能混称“全部范围外”。
不因此释放任何旧hold、扩大范围或读其结果。143个instance也不天然等于143个独立scientific experiments。

最终公共回执在`combined_stage/`；首阶段仍保留在`srun_stage/`；两阶段私有目录均已锁为500/400。
原始来源配置/journal定位与本轮launcher证据合起来已大幅缩小问题，但仍需可读实际快照/评分执行证据。
接下来按`../../SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md`的最新交接取已有记录；资格通过后自行做新Cards/G/L构建实录。

## 已完成：从配置分组推进到实际启动记录

输入沿用676-run实际source ledger，SHA
`8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1`。
原S0失败、两个旧错误归档和全部原hold保留；正确leaf是独立固定副本，没有覆盖旧证据。

首阶段code `14e38d2cd9a8cf6408df87d4c67a1f4d9d2860fe`：

- 完整扫描143种已固定archive SHA，仅解析严格路径的srun_pool manifest；85份实际清单，关联448个固定历史run。
- 447个Slurm step与config对应，1个不一致。后者有两次尝试记录，但config step不匹配任何一次，也不是allocation-only；未解释、未放行。
- 136条任务记录未能在同归档绑定。后续全ledger核对：134条没有匹配来源，2条有目录候选但未确认同一实例；
  不能把136全部说成“固定范围不存在”。未按任务结果猜测缺失原因，也没有扩读其config/journal。
- 48份manifest的成员全部在固定范围，涉及303run；与原hold闭包相交后，40run所在组件不含缺失成员/未覆盖run/step异常。
  **40不是已获准训练量**，完整实验语义和运行环境仍待证据。
- 新联系未增加旧hold闭包：仍139组件、538run阻断。85个manifest记录的snapshot路径均permission denied；没有绕过访问控制。
- A/B两次真实扫描185/183秒，全部archive回执与lineage逐字节一致。独立833bd44另用图遍历核验membership/闭包通过。

首阶段lineage SHA：`c081680b69389e233838a6f2ed4b887f02f8f3a99101d6822960b8118507e070`。
原始聚合回执在`srun_stage/`，含实际命令/时间/Python、每次运行CSV和公共文件哈希。
私有逐run路径、task IDs、完整清单仅留远端只读目录，不上传Git。

## 两个重要边界

1. **真实launcher实例不自动等于完整科学experiment。** 实例记录来自原manifest的创建时间、snapshot、python、pool目录及全task集合，
   不再把config的meta_id当真实实例；但未匹配成员和可能的跨launcher关系不能用声明抹掉。
2. **安装recipe不等于运行时证明。** 查到22个可读recorded commit的MLE-bench README内容相同，固定
   `d0f60ad0d3b2287469ac3c8ac9767330c928c980`，且说明cache patch。
   之前仅在顶层requirements/pyproject寻找版本不充分。这个新证据不证明当时实际安装了该版本，也不补造clean snapshot。

## 本轮失败/限制记录

探索性路径检查最初因Python环境目录无权访问退出，改为明确permission_denied分类，没有提权或绕过。
后续header定位脚本先遇旧error行无sha256键，在打开归档前失败；修复为先判status，未改变输入范围。
这些辅助脚本失败不与正式A/B成功混称。独立核验是存储回执连接、另一个图算法与A/B字节核对；
不是独立重解析全部tar，也不是OS沙箱证明。文件访问trace只作辅助证据。

发布前严格Git-blob对实跑源码SHA检查曾拒绝，未推送。核查发现Windows git-archive输出CRLF，Git blob为LF；
已对两个实际固定源码包的全部Python文件验证：包SHA等于结果前固定值，主脚本SHA等于实跑回执，
逐文件换行归一化字节完全相同且AST相同。原始回执未改写；完整双SHA见`source_export_integrity.json`。
后续导出显式`git -c core.autocrlf=false archive`，并在执行前比对导出文件与Git字节，不再只核包SHA。

第一次local扩展53a6b21在43归档遇attempt_schema拒绝，仅A轮、无最终lineage。遗漏来自只读了创建/启动函数，
没有先覆盖_finish_task写入的result字段。补读实际生产源码确认该字段是worker退出元数据；
e7244fb仅接受此键，不访问/投影其内部对象。未知其它字段继续拒绝，旧失败保留，不按成功任务挑来源。
两个缺失recorded SHA按准确值fetch仍返回128；只报告获取失败，不据此断言生产方从未保存它们。

本轮不读journal/env/log payload，不读first960/Target300/522结果，不构建Cards/G/L。
12535仍为原授权双卡作业，未新增提交；G0真实执行与新consumer恢复验收仍严格分开。
