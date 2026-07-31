# Jupyter 端口冲突（`srun_pool` / `local_gpu_pool`）

`srun_pool` 的多个 step 会共享同一节点网络。原实现没有指定
`KernelGatewayApp.port`，每个 Jupyter server 都从 8888 开始自动找端口；任务失败
并重试时，多个进程会同时扫描同一组端口，可能卡住 300 秒启动超时。

现在 Jupyter interpreter 会按 launcher 的执行身份稳定计算一个 20000--49999 的端口，
并把它显式传给 Apptainer/Singularity 的 KernelGateway，作为端口扫描的起点：

- Slurm 使用 `SLURM_JOB_ID` 和 `SLURM_STEP_ID`；
- `local_gpu_pool` 使用 worker 启动时生成的 `DOJO_EXECUTION_ID`。

这样并发 worker 不再同时从 8888 开始扫描，同一个执行身份也会得到同一个起始端口；
如果哈希端口偶然被占用，Jupyter 仍可继续扫描后续端口。没有 scheduler execution
identity 的普通本地直接运行保持原来的自动分配行为。

# Agent 修改 `CUDA_VISIBLE_DEVICES`

Singularity legacy `--nv` 可能把所有 NVIDIA device node 带入容器，
`CUDA_VISIBLE_DEVICES` 只提供协作式 GPU 可见性限制。如果 Agent 生成的代码主动设置、
删除或覆盖该变量，可能绕过 `local_gpu_pool` 分配的 GPU mask。

对应的 prompt 补丁位于：

```text
src/mle_critic/patches/preserve_cuda_visible_devices_in_code_prompts.patch
```

它会在 AIRA 和 AIDE 的 draft、debug、improve、crossover prompt 中加入一条简短要求：
不要修改 `CUDA_VISIBLE_DEVICES`，直接使用 runtime 已经暴露的 GPU。应用方式：

```bash
git apply src/mle_critic/patches/preserve_cuda_visible_devices_in_code_prompts.patch
```

这只能减少 Agent 无意修改 mask 的情况，不构成 device cgroup 级强隔离。

# Singularity 中 LightGBM 无法使用 NVIDIA OpenCL

在 `local_gpu_pool` 中，PyTorch CUDA 可以正常识别分配的 GPU，但 LightGBM 使用
`device="gpu"` 时可能报错：

```text
LightGBMError: No OpenCL device found
```

这里的 LightGBM `gpu` backend 使用 OpenCL，不等同于 PyTorch 使用的 CUDA。
在 `build/superimage/superimage.root.2026-07-macos-v1.sif` 上实测发现：

- Singularity `--nv` 会带入 CUDA、`libnvidia-opencl.so.1` 和
  `libnvidia-ptxjitcompiler.so.1`；
- 它不会自动带入宿主 `/etc/OpenCL/vendors/nvidia.icd`；
- 当前 Singularity 3.10.1 的 `/etc/singularity/nvliblist.conf` 没有包含
  `libnvidia-nvvm.so`，因此 OpenCL kernel compiler 也不会进入容器；
- 只挂载 ICD 后能够枚举 NVIDIA OpenCL device，但 kernel 编译仍以
  `CL_BUILD_PROGRAM_FAILURE` 失败；
- 同时挂载 NVIDIA ICD 和与宿主驱动匹配的 `libnvidia-nvvm.so.4` 后，LightGBM
  能正常编译 GPU program 并训练。

对应的可选补丁位于：

```text
src/mle_critic/patches/singularity_nvidia_opencl_runtime.patch
```

应用补丁：

```bash
git apply --check src/mle_critic/patches/singularity_nvidia_opencl_runtime.patch
git apply src/mle_critic/patches/singularity_nvidia_opencl_runtime.patch
```

回滚补丁：

```bash
git apply -R src/mle_critic/patches/singularity_nvidia_opencl_runtime.patch
```

补丁不会写死当前机器的驱动版本。`SingularityJupyterServer` 启动时会：

1. 只检查 `/etc/OpenCL/vendors/nvidia.icd`，并确认其内容指向
   `libnvidia-opencl`，不会把 Intel 等其他 ICD 一起带入；
2. 通过 `ldconfig -p` 查找 `libnvidia-nvvm.so.4`，再解析到当前驱动实际文件；
3. 将 ICD 只读挂载到容器的 `/etc/OpenCL/vendors/nvidia.icd`；
4. 将 NVVM 只读挂载到已位于容器 `LD_LIBRARY_PATH` 中的
   `/usr/local/nvidia/lib64/libnvidia-nvvm.so.4`；
5. 如果宿主缺少完整 NVIDIA OpenCL runtime，只记录 warning，不影响普通
   PyTorch/CUDA 任务；
6. 如果用户配置的 `read_only_binds` 占用了上述自动管理目标且来源不同，拒绝
   启动，避免静默覆盖。

补丁带有 ICD 校验、`ldconfig` 解析、驱动版本无关性、缺失 runtime 降级和 bind
冲突测试。当前机器上的真实验证使用 RTX 2080 Ti 和上述 SIF，通过完整
`SingularityJupyterServer -> Jupyter kernel -> LightGBM device="gpu"` 链路完成，日志包含：

```text
Using GPU Device: NVIDIA GeForce RTX 2080 Ti, Vendor: NVIDIA Corporation
GPU programs have been built
OPENCL_PATCH_PASS
```

镜像中的 LightGBM 没有启用 CUDA Tree Learner，因此把配置改成 `device="cuda"`
不是替代方案；它会报 `CUDA Tree Learner was not enabled in this build`。

同一依赖链在 `ChrootPythonInterpreter` 上可能以另一种形式出现：chroot 会直接看到宿主的
NVIDIA driver libraries，因此不会遇到 Singularity `--nv` 漏带 NVVM 的问题；但某些 K8s Pod
只注入 `libnvidia-opencl.so.1`、`libnvidia-nvvm.so.4` 和 device nodes，没有安装
`/etc/OpenCL/vendors/nvidia.icd`。这属于部署环境兼容问题，不是 chroot 隔离的必然要求。

对应的可选补丁位于：

```text
src/mle_critic/patches/chroot_nvidia_opencl_runtime.patch
```

应用后，它会在每个 agent workspace 中生成私有 NVIDIA ICD，将 `OCL_ICD_VENDORS` 指向该目录，
并为 chroot 集成测试增加一轮真实 LightGBM OpenCL 训练。默认 chroot 实现不修改 OpenCL 环境，
避免影响已有完整 ICD、其他 OpenCL vendor 或没有 NVIDIA runtime 的机器。

```bash
git apply --check src/mle_critic/patches/chroot_nvidia_opencl_runtime.patch
git apply src/mle_critic/patches/chroot_nvidia_opencl_runtime.patch
pytest -q tests/test_chroot_python_interpreter.py
```

回滚：

```bash
git apply -R src/mle_critic/patches/chroot_nvidia_opencl_runtime.patch
```

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

# Proxy问题

很多集群都有乱七八糟的网关和防火墙，可能影响到kaggle的下载。这里没有深究，但

```bash
export KAGGLE_PROXY="${HTTPS_PROXY}"
```

是有效的。
