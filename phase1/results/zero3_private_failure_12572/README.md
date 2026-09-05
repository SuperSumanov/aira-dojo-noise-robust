# 12572真实双卡尝试：初始化失败，未生成checkpoint

Source `11ff14a7f6fe9a4a2ab9b830a9829f07b0249b2c`。本轮实际134项Linux CPU检查通过。
两RTX3090于香港2026-09-06 07:44:57启动，07:46:10结束；Slurm FAILED/1:0，73秒、146GPU秒。
加上12570的2和12571的5GPU秒，截至此轮实际累计153GPU秒。

真实节点CUDA12.8私有prefix和C++编译器预检均通过。driver启动，但第一条full轨迹初始化时两个rank均SIGSEGV；
完成轨迹0、checkpoint manifest0，不是训练/恢复验收成功，也没有任何模型收益。
文件trace尾部两rank都在枚举irdma1后SEGV_MAPERR(0x7)。这支持RDMA初始化故障假设，
**不是native stack或因果证明**，不能直接归因为PyTorch/模型/显存容量问题。
后续只把固定Socket单机通信作为有界workaround另行登记，不在此轮自动重试。

CPU元数据确认R5解释器和包入口正确，其Torch目录符号链接共享exp中的同一2.11.0+cu128包；
本轮trace的父/子execve也均为R5解释器。日志出现exp路径不足以证明混用了不同PyTorch版本。
原解释器/包布局未改，原12535未改。后续新Socket job12573不属于本失败记录。

独立failure audit source `b84e8baea4de65a16038b4136cee094d29716964`；安全扫描0命中、保护路径标记0命中。
23个原始文件（含MANIFEST）逐字节导入；完整文件trace保留远端，Git仅保存其摘要和故障尾部。

- failure audit SHA `4e2b7fe6caac2e756f9762be2b2a20535d5126d83a4454139824f45cf501b963`
- original trace SHA `39c71ce4e6b3584b782d20efa65d7d68dd5ce780b9f580b976b19e479ff90fce`
- export archive SHA `944d8fd6e7c14cc104ccb1f5234fc3ee2c5651c96b5722e4071a5a8e3813476c`
- export manifest SHA `9cde13a1216ef69cf8ed34db823ce78cd2f75c95651b702593593faae3f4c899`

实际GPU花费必须保留；代码测试通过不等于真实分布式环境通过，不能把这次失败删去。
