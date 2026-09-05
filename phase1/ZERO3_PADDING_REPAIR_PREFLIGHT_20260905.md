# 12510失败后的有界修复：仍非GPU验收完成

12510实际两PRO6000、149秒、FAILED/1:0，消耗298 GPU-seconds。初始化后的全状态观察器报非有限值，
没有完成训练轨迹或checkpoint。原日志没有张量名，因此不能仅凭该日志断言具体失败张量。

实际安装的DeepSpeed partition_parameters.py SHA为
`8b3c65d20fada0fc85c3685615b0da65247f4e8739313ca1de01b1a3102f2500`。
其初始分片使用torch.empty；末尾不足整片时只复制有效前缀、不初始化padding。
确定性uninitialized填NaN开启时，实际源码CPU接收器8种size/rank情况复现：奇数参数末rank有NaN padding。
修复只在prepare期间首次分片后将已验证的无语义padding置零、在FP32 masters建立前执行。
原有效参数逐位保留；2个真实NaN反例仍拒绝，嵌套hook拒绝，退出时还原原方法。
训练/保存/恢复不装hook，所有model/master/AdamW仍逐元素finite检查，额外输出具体状态路径。
首个CPU接收器遗漏分布式日志mock而失败；修正仅日志依赖，未替代实际分片计算。101原单测通过。

## 固定矩阵与预检

- 原预算4320 GPU-seconds不增加；失败298加新两卡26分钟、KillWait300秒、调度余量60秒，
  累计上界4138、余182；控制器读取终态记账重算，未知作业/变动fail-closed。
- 新作业一份，held核验后release，projgpu39/两PRO6000/12CPU/mem0/gpu_24h/qos gpu/no-requeue。
  运行内timeout24分钟+kill60秒；不另行启动G0或真实训练。
- 原模型结构4433随机参数、bias保留、BF16、CPU-offload DeepSpeedCPUAdam/AdamW、seed6、
  G_to_L同一合成token plan和五条full/prefix2/resume2/prefix3/resume3轨迹不改。
- 原训练源码5f3bc362db922c8edee2ef134656dfdb9a2b74fb及R5环境不变；实际ninja/CUDA路径照旧验收。
- 修复源码先固定commit；实际DS CPU接收器A/B独立进程必须相同，单测/运行库hash/只读source门通过。
- 一GiB真实分配/fsync/同inode回收检查；不以磁盘标称配额当可用空间，不删除语料/模型。
- 无真实数据/预训练权重/API；test查重、任务分层、功效分析不适用于这个合成工程验收，
  不宣称任何模型效果或science-support。正式训练仍须来源包资格。
- 保留原失败、编译日志、trace、退出码和遥测；新检查点保存AdamW/master/各rank RNG与消费cursor。
- 结束后独立检查所有文件hash、真实payload逐位比较、消费顺序、计数器和累计成本，再查trace/security。
  验收器读取自己的合成checkpoint，不读取任何保护cohort。
- 发布前credential-shape扫描；不扩大数据范围、不重抽任何冻结run、不修改效果成功门。

当前只完成CPU根因复现；真实GPU修复效果需新作业证明。不要将本文件当作通过回执。
