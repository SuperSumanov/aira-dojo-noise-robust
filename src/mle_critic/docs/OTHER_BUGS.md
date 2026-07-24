# Jupyter 端口冲突（Slurm `srun_pool`）

`srun_pool` 的多个 step 会共享同一节点网络。原实现没有指定
`KernelGatewayApp.port`，每个 Jupyter server 都从 8888 开始自动找端口；任务失败
并重试时，多个进程会同时扫描同一组端口，可能卡住 300 秒启动超时。

现在 Jupyter interpreter 在 Slurm 环境中使用 `SLURM_JOB_ID` 和 `SLURM_STEP_ID`
稳定计算一个 20000--49999 的端口，并把它显式传给 Apptainer/Singularity 的
KernelGateway，作为端口扫描的起点。这样同一 step 重启会从同一端口开始；如果该
端口偶然被占用，Jupyter 仍可继续扫描后续端口。非 Slurm 本地运行保持原来的自动
分配行为。

# 储存大小

将`HF_HUB_OFFLINE`设为`0`之后，每个独立任务都有一个独立的运行目录，可能导致大量下载。
为了保证不超出储存空间限制，请定期手动运行以下命令。
先预览将被删除的目录：
```bash
target_dir="logs/aira-dojo"; find "$target_dir" -type d -name workspace_agent -prune -print
```
确认后递归删除所有 workspace_agent 及其内容：
```bash
target_dir="logs/aira-dojo"; test -n "$target_dir" && test "$target_dir" != "/" && find "$target_dir" -type d -name workspace_agent -prune -exec rm -rf -- {} +
```
删除不可恢复，建议先运行预览命令。


# GLIBC

当使用某些ubuntu版本较老的节点时，运行实验可能会遇到以下报错

```python
  File "/research/jcheng3/hcyang/anaconda3/envs/aira-dojo/lib/python3.12/site-packages/google/auth/crypt/__init__.py", line 41, in <module>
    from google.auth.crypt import es
  File "/research/jcheng3/hcyang/anaconda3/envs/aira-dojo/lib/python3.12/site-packages/google/auth/crypt/es.py", line 21, in <module>
    import cryptography.exceptions
  File "/research/jcheng3/hcyang/anaconda3/envs/aira-dojo/lib/python3.12/site-packages/cryptography/exceptions.py", line 9, in <module>
    from cryptography.hazmat.bindings._rust import exceptions as rust_exceptions
ImportError: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.33' not found (required by /research/jcheng3/hcyang/anaconda3/envs/aira-dojo/lib/python3.12/site-packages/cryptography/hazmat/bindings/_rust.abi3.so)
```

原因是`GLIBC_2.33`只在高版本ubuntu提供，而高版本`cryptography`依赖这个`GLIBC_2.33`，建议降级`cryptography`

```bash
conda install -c conda-forge cryptography=49.0.0
```