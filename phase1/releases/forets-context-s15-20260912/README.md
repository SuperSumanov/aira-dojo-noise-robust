# 实际seed15运行包（不包含实验结果或私有候选）

对应job13128、controller f53ed6693d029070662c50f81ea7146f0a9e4d35、
source tree 54e353963a6899965896b2e8ea492207829b3cbd。

`release-code-capsule-s15-v1.tar.gz`包含237份实际任务源码、28份部署controller文件、四run配置、
来源/版本清单与原许可证，共284文件。SOURCE/config是实际跑的版本，不是只附本地草稿。
SHA256：784a535057aad68b1712feedf3f927d50a7b943f4ff77f728f2f721d988b0808。

本地独立核对237源码与Git blob逐字节一致，28controller哈希匹配、两许可证与Git blob一致，凭据形状扫描0命中。
不含模型权重、MLE数据、生成的候选、API响应、API key或运行结果；这些不能通过本包推断。
配置中的绝对研究盘路径是原环境记录，复现时需要合法数据/镜像及自行配置环境，不能无审阅直接投到其他硬件。

科学对照及边界见[seed14结果](../../FORETS_SMALLPOOL_S14_RESULTS_20260912.md)与[固定复验条件](../../FORETS_SMALLPOOL_S14_LAUNCH_20260912.md)。
seed15尚在运行，本包不代表任何收益结论。此前取消seed13的旧capsule不能替代本包。
