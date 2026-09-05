# ZeRO3修复重试与0904来源接收：尚未完成GPU验收

GPU结果前固定code=`09911b15ca065442386120707dccf036e262dadd`。
0904下载code=`88e5f9fec01a74828b27b8d16df5b5be5f992138`，实际脚本SHA=
`d47db65a3c5a565ebc1838cee468a9400c44e08a0e61d9dce37f08b952e2da75`。

## 实际完成

- 12510终态FAILED/1:0，两GPU149秒，298 GPU-seconds；初始化状态检查异常、0完整轨迹/0checkpoint。
  `failure_12510/`保留失败日志、记账、源码CPU诊断及大trace的SHA。没有把失败写成完成。
- 固定DS实际分片方法CPU接收器A/B同结果：8个size/rank情况复现uninitialized padding，真实参数不变；
  两个真实NaN负控制和嵌套hook拒绝。仅日志被mock，无真实DS engine/GPU参与。
- 新control下101原单测通过；独立验收器另作A/B各17 tests通过。这些不是GPU成功证据。
- 新作业12535先held核26分钟/两PRO6000/12CPU/mem0/projgpu39/no-requeue，再release。
  一GiB真实分配/fsync通过；30源码重新核hash无漂移。此前失败298加重试最多3840，累计上界4138<=4320。
  `submission_12535/`是实际准备/提交/放行回执；原READY的4320为总授权，RETRY_READY细化剩余预算。
- 核查时12535仍PENDING/Resources、实际0 GPU秒；21:46香港调度估计9月6日19:38:15开始，非保证。
  当前不存在该作业成功trajectory或通过的独立GPU终态报告。

## 修复范围与失败保留

DS当前源码初始torch.empty分片可能保留NaN padding；旧12510错误不含张量名，所以只能说源码复现支持此原因，
不能从旧日志唯一定位异常张量。新driver记录padding数量，状态观察器新增具体路径。
只在prepare期间首次分片初始化合法padding，FP32 masters构建前生效；hook随后撤除，真实参数/保存/恢复finite门保留。
没有去掉bias、改dtype/seed/优化器/原五条轨迹，也没有在错误后修改科学成功阈值。

初次临时目录复制因文件系统不支持保留权限中断，改新临时目录按内容复制；没有修改原control。
CPU接收器首轮缺分布式日志mock而失败（`cpu-reproduction.log`），后仅替换无关日志调用并通过。
补丁后实际GPU原因和恢复等价性仍需12535证明，不能将CPU通过当作修复已获GPU认证。

## 学长的新归档与实际来源缺口

新发现0904六份归档，179805006压缩字节，325→331归档。全部独立复核hash、mtime、只读与目录清单。
没有解包、读取protected记录/候选身份/标签/预测值。最早稳定时间为UTC2026-09-05T19:44:48.903091，
香港9月6日03:44:48；仍须原协议摄取。不能把新归档数当新增runs，也不因此增加eligible计数。
`source_0904/`仅公开安全汇总，私有manifest和原始压缩包都留远端。
当前LATEST未变，649 physical / 623 eligible、3919 structural pairs、51 tasks、closure=false。
旧intake守护已自然结束，Target522旧失败链不恢复；没有新自动化。

来源构建链已补到确切脚本/配置字段/目录层级，但实际开发资格、experiment映射和运行版本记录仍缺；
详见`../../PRODUCTION_SOURCE_FACTS_20260905.md`。不靠声明布尔值或当前SHA解锁正式fit。

安全导出tar SHA=`689093997f3332e9616f05a446323d35229bf8e5db679e90b8ad508331723403`，
`export_inventory.json`包含16个导出回执文件的hash；`sacct.txt`与该inventory本身为另附文件。
未导出真实语料、私有文件名或检查点；全部记录只是工程/来源资产，**没有新的模型效果正结论**。
