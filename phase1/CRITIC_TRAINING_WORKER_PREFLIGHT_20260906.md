# 正式训练worker的预算与进程边界（准备，不投递）

2026-09-06。接上training entry此前声明但没有实现的parent-worker职责；不写sbatch投递器或自动重试器。
ADMITTED_RELEASES保持空，真实来源、完整ZeRO3实卡、存储和精确矩阵预算到位后才可单独登记实际launch-v2。

- 实际Slurm主作业必须为登记的RUNNING、两PRO6000、projgpu39、12CPU、无requeue/restart；后续换硬件需另审。
- 所有本阶段历史作业的ID/state/elapsed/GPU/exit必须与登记的终态账一致；主作业行计一次，不重复计batch/extern。
- 累积上界=实际已占GPU秒+本作业两卡×(登记walltime+退出宽限+调度余量)。启动前核实际剩余时限。
- 同时保留launch SHA与固定training-definition SHA，改合法恢复目录不改变科学身份；没有准入不查询作业或读数据。
- 子进程只继承scheduler/CUDA分配与固定离线运行变量，不把任意API key/proxy/PYTHONPATH传给训练。
- 不创建训练基座或修改agent；仅执行既定独立critic入口。本worker不声称其进程退出就是独立训练验收。
- 模块不调用sbatch/scontrol release/scancel，不改12535；当前不存在真实production launch或worker执行。
- 测试为确定性预算/解析负例与Linux自有child/grandchild的timeout/kill；后者只在真实Linux执行，不把Windows skip当通过。
- CPU测试≤120秒、无真实数据/GPU/API；保留exact commit、原始测试输出与失败。不是模型收益或实际Slurm worker验收。

仍须生产来源、隔离、完整训练/预算/存储launch清单、实际GPU验收与独立完成验证，不能用本测试填写这些门。
