# Balanced continuation E1：揭盲前 QOS 操作修订

日期：2026-08-14。状态：在任何 rollout、API、candidate execution 或 sealed outcome 产生前冻结。

前三次启动均在付费动作前 fail-closed：

1. 第一次没有从远端 mode-600 `.env` 导出 operator credential；
2. 第二次错误地假设登录节点具有仅 GPU 节点可见的 `libnvidia-nvvm.so.4`；
3. 第三次在远端 phase1 `188/188` 测试、数据门和 assignment 独立复算通过后，被
   `QOSMaxSubmitJobPerUserLimit` 拒绝，Slurm 未接受任何 job。

三次均为 0 API、0 GPU、0 candidate、0 sealed outcome，失败目录保留。因为本账户最多同时提交 4 个
job，不能同时挂起两个各含 4 个元素的数组。冻结矩阵、assignment、seed、cap、模型、prompt、estimand、
score visibility 与 E1 撤回边界均不变；只把调度改为 QOS-aware 顺序提交：

- monitor 先提交 stage1 的 4 个 rollout；
- 只有 capability/worker/独立 verifier/safety 四项工程 receipt 全为零，才提交仍带
  `afterok:<stage1_job>` 的 stage2；
- QOS 拒绝时，仅在没有获得 parsable job id 时重试 scheduler submission；
- 绝不重试 candidate、operator API 或 replacement sample；
- 绝不读取 D_search/D_val 后决定是否提交 stage2；完整 8-rollout coverage 关闭后才揭开 D_val。

因此本修订只修正集群调度可行性，不改变实验问题、样本、预算矩阵或统计口径。

随后 stage1 job `10813` 的四个元素均在 1 秒内发现 `exp` venv 的 Python 是指向 GPU 节点不可见 home/UAC
目标的符号链接，统一在 capability/candidate/API 前 `exit 3`；stage2 未提交、sealed outcome 未打开。独立的
0-API/0-candidate 工程探针 job `10817` 在同一 `gpu27` 上用共享 `/research` 内的 `aira` Python 完成全部 E1
host-module import 与 NVVM/ICD 文件检查，12 秒、exit 0（约 0.0033 GPU·时）。因此正式 job 改用该共享解释器，
并把解释器 path 与 SHA-256 加入 run plan、在每个 job 中复核；其余实验契约仍不变。
