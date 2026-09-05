# 双3090 RDMA初始化故障后的单机Socket验证

2026-09-06。12572已FAILED 73秒/146 GPU秒，零完成轨迹/零checkpoint；不能称恢复通过。
原source11ff14a、退出码和46MB文件trace保留。两个rank都在枚举irdma1后SEGV_MAPERR(0x7)，
这支持RDMA初始化故障假设，但文件访问尾部不是native stack或因果确认。
父/子execve均R5解释器；R5 Torch包本来符号链接到exp的同一2.11.0+cu128包，不能凭traceback路径断言版本混用。

## 变更与一次性界限

仅新单机通信profile=NCCL_NET=Socket、NCCL_IB_DISABLE=1；加INFO/faulthandler以定位失败。
不修改驱动/系统、不重新安装依赖，不改模型、fixture、seed、优化器、恢复断点和容差。
这是明确的传输workaround，不是修好RDMA硬件/驱动，也不用于和原网络计时比较。
依据[NVIDIA官方NCCL说明](https://docs.nvidia.com/deeplearning/nccl/archives/nccl_2243/user-guide/docs/env.html)，禁用IB/RoCE后使用IP Socket。
实际日志还须出现Using network Socket，不能只凭导出的变量宣布生效。

新job1×2RTX3090×18min，driver900s+kill60s；2880GPU秒上限含300s退出及60s余量。
此前12570/12571/12572均终止，实际2+5+146=153GPU秒，组合153+2880=3033≤原3120独立上限。
旧12535仍单独排队不动；新job无自动重试、不扩大原总预算。

## 13项预检（沿用原工程问题，显式更新通信）

1. 产物记录真实toolchain与NCCL profile，并核实际Socket日志。
2. 原134项Linux CPU检查+新profile/budget检查通过后才held提交。
3. 全部自生成fixture，不读真实训练或确认数据。
4. 两个断点×两个rank全状态/实际payload逐一比较，任意一项不等就失败。
5. 训练数学/预算不变；网络profile只为本工程验证，不形成性能或科学对照。
6. 真实checkpoint/optimizer/RNG保存，新job独占目录。
7. 独立审核文件trace与秘密形状；不读取保护语料或撤回checkpoint。
8. seed6及原RNG扰动/恢复流程完全相同。
9. 公开前扫描；offline模型、无付费API/密钥注入。
10. 原已终止jobs按真实用量入账，时间仍硬限，不自动续投。
11. 微型工程不算模型效果，不决定是否升级训练投入。
12. worker、Slurm、payload与trace分别记录实际状态。
13. 原四fit/五臂/确认协议与入库人口不变，ADMITTED_RELEASES仍空。

如果Socket仍失败，保留faulthandler/native线索再作诊断，不能连续换参数直到“绿灯”。
