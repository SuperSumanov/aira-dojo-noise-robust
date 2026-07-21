# Jupyter 端口冲突（Slurm `srun_pool`）

`srun_pool` 的多个 step 会共享同一节点网络。原实现没有指定
`KernelGatewayApp.port`，每个 Jupyter server 都从 8888 开始自动找端口；任务失败
并重试时，多个进程会同时扫描同一组端口，可能卡住 300 秒启动超时。

现在 Jupyter interpreter 在 Slurm 环境中使用 `SLURM_JOB_ID` 和 `SLURM_STEP_ID`
稳定计算一个 20000--49999 的端口，并把它显式传给 Apptainer/Singularity 的
KernelGateway，作为端口扫描的起点。这样同一 step 重启会从同一端口开始；如果该
端口偶然被占用，Jupyter 仍可继续扫描后续端口。非 Slurm 本地运行保持原来的自动
分配行为。
