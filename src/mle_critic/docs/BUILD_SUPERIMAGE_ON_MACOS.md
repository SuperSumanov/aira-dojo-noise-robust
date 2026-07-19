# 在 macOS + Docker 上构建 aira-dojo Superimage

本文说明如何在安装了 Docker Desktop 的 macOS 机器上，使用仓库现有的
`superimage/apptainer.def` 构建供 Linux 集群上的 Singularity 使用的 `.sif` 文件。

## 结论和边界

- macOS 不能原生运行 Apptainer/Singularity；这里实际是在 Docker Desktop 的 Linux VM
  中运行 Apptainer builder。
- 最终产物必须是 Linux 镜像，而不是 macOS 镜像。
- 当前目标集群是 `x86_64`，所以即使构建机器是 Apple Silicon，也必须指定
  `linux/amd64`。
- Apptainer 与 Singularity CE 都使用 SIF。由 Apptainer 构建的 `.sif` 通常可以直接由
  Singularity CE 运行。
- 构建镜像不要求 NVIDIA GPU。GPU 驱动由集群运行时通过 `singularity --nv` 注入。
- 运行时迁移已经完成：默认 Jupyter 配置使用前台 `singularity exec`，不依赖 instance、
  fakeroot、动态 writable overlay 或 Apptainer 日志目录。Apptainer backend 仍保留用于兼容
  原环境。

## 推荐路线

不要把 `apptainer.def` 手工重写成 Dockerfile。直接在一个特权 Docker 容器中运行
Apptainer builder，可以继续把仓库中的 definition file 作为唯一镜像定义：

```text
macOS
  -> Docker Desktop Linux VM
       -> Apptainer builder container (linux/amd64, root)
            -> superimage.root.<VERSION>.sif
                 -> 拷贝到 Linux 集群
                      -> singularity exec
```

## 1. 前置检查

在 macOS Terminal 中进入仓库根目录：

```bash
cd /path/to/aira-dojo-noise-robust
test -f superimage/apptainer.def
docker version
docker info
```

确认目标集群架构。当前项目使用的集群是 `x86_64`：

```bash
ssh USER@CLUSTER 'uname -m'
```

预期输出：

```text
x86_64
```

如果 Mac 是 Apple Silicon，下面的命令会用 QEMU/Rosetta 模拟 amd64。这个镜像依赖很多，
还会编译 OpenSSH，因此构建可能需要数小时。Intel Mac 通常更快。

建议在 Docker Desktop 中至少分配：

- 16 GB 内存，推荐 24–32 GB；
- 8 个 CPU；
- 120 GB 可用 Docker 磁盘空间，推荐 150 GB；同时确保 macOS 宿主机也有足够空闲空间。

镜像定义安装 PyTorch、CUDA toolkit、RAPIDS、FAISS、Transformers 等，构建过程和最终
SIF 都比较大。

## 2. 准备输出目录和 Docker volumes

以下命令都从仓库根目录执行：

```bash
mkdir -p build/superimage
docker volume create aira-apptainer-cache
docker volume create aira-apptainer-tmp
```

使用 Docker volume 保存 Apptainer 下载缓存和构建临时文件，比把大量小文件直接写到
macOS bind mount 通常更快。

选择一个不会与现有镜像混淆的版本号：

```bash
export SUPERIMAGE_VERSION=2026-07-macos-v1
```

## 3. 拉取并检查 builder

本文使用发布在 GitHub Container Registry（GHCR）的官方 Apptainer 容器。先拉取固定
版本：

```bash
docker pull --platform linux/amd64 ghcr.io/apptainer/apptainer:1.4.2
```

检查容器中的 Apptainer：

```bash
docker run --rm \
  --platform linux/amd64 \
  ghcr.io/apptainer/apptainer:1.4.2 \
  apptainer version
```

GHCR 镜像没有把 `apptainer` 设置为默认 entrypoint，所以不能只写 `version`；每条
builder 容器命令都要显式写出 `apptainer`。

如果 Docker 提示 amd64 模拟不可用，先在 Docker Desktop 设置中启用 Apple Silicon 上的
Rosetta/x86-64 emulation，然后重启 Docker Desktop。

## 4. 构建 SIF

运行：

```bash
docker run --rm \
  --privileged \
  --platform linux/amd64 \
  -v "$PWD:/workspace" \
  -v aira-apptainer-cache:/root/.apptainer/cache \
  -v aira-apptainer-tmp:/var/tmp/apptainer \
  -e APPTAINER_TMPDIR=/var/tmp/apptainer \
  -w /workspace/superimage \
  ghcr.io/apptainer/apptainer:1.4.2 \
  apptainer build --force \
  "/workspace/build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif" \
  apptainer.def
```

这里故意没有使用 `--fakeroot`：builder 容器通过 Docker `--privileged` 以 root 身份执行
构建。macOS 本身的 root 权限并不重要，真正执行 Linux 构建的是 Docker Desktop VM。

`-w /workspace/superimage` 不应省略，因为 definition file 的 `%files` 使用了以下相对
路径：

- `build-openssh.sh`
- `entrypoint.sh`
- `pip.requirements.txt`

构建成功后应得到：

```bash
ls -lh "build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif"
```

### 构建中断后重试

可以直接重新执行同一条 `docker run ... build --force ...` 命令。下载缓存保存在
`aira-apptainer-cache` volume 中，但 `%post` 中的安装步骤仍会重新执行。

如需彻底清理构建缓存：

```bash
docker volume rm aira-apptainer-cache aira-apptainer-tmp
```

这只删除 Docker 构建缓存和临时文件，不删除已经输出到 `build/superimage/` 的 SIF。

## 5. 在 macOS 上做静态检查

先查看 SIF 元数据：

```bash
docker run --rm \
  --privileged \
  --platform linux/amd64 \
  -v "$PWD:/workspace:ro" \
  ghcr.io/apptainer/apptainer:1.4.2 \
  apptainer inspect "/workspace/build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif"
```

再检查关键命令和 Python 包。Mac 没有 NVIDIA GPU，所以这里不要加 `--nv`：

```bash
docker run --rm \
  --privileged \
  --platform linux/amd64 \
  -v "$PWD:/workspace:ro" \
  ghcr.io/apptainer/apptainer:1.4.2 \
  apptainer exec "/workspace/build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif" \
  python -c 'import torch, pandas, sklearn, transformers; print(torch.__version__); print(torch.cuda.is_available())'
```

在 Mac 上 `torch.cuda.is_available()` 预期为 `False`，这不表示镜像构建失败。

检查 Jupyter Kernel Gateway：

```bash
docker run --rm \
  --privileged \
  --platform linux/amd64 \
  -v "$PWD:/workspace:ro" \
  ghcr.io/apptainer/apptainer:1.4.2 \
  apptainer exec "/workspace/build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif" \
  python -m jupyter kernelgateway --version
```

## 6. 生成校验和并传到集群

macOS 使用。先进入输出目录，确保校验文件只记录文件名而不是 Mac 上的目录：

```bash
cd build/superimage
shasum -a 256 \
  "superimage.root.${SUPERIMAGE_VERSION}.sif" \
  > "superimage.root.${SUPERIMAGE_VERSION}.sif.sha256"
cd ../..
```

传输文件，例如：

```bash
scp \
  "build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif" \
  "build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif.sha256" \
  USER@CLUSTER:/path/to/shared/sif/
```

大文件传输更推荐支持断点续传的 `rsync`：

```bash
rsync -ah --progress --partial \
  "build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif" \
  "build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif.sha256" \
  USER@CLUSTER:/path/to/shared/sif/
```

在集群端验证：

```bash
cd /path/to/shared/sif
sha256sum -c "superimage.root.${SUPERIMAGE_VERSION}.sif.sha256"
```

## 7. 在 Singularity 集群上验证

先进行不依赖 fakeroot 的只读验证。当前集群使用较旧的 Singularity 3.5.2，镜像把
`HOME` 固定成了 `/root`，因此显式换成可写的 `/tmp`：

```bash
export SIF=build/superimage/superimage.root.2026-07-macos-v1.sif

singularity inspect "$SIF"
singularity exec --cleanenv "$SIF" env HOME=/tmp python --version
singularity exec --cleanenv "$SIF" env HOME=/tmp python -m jupyter kernelgateway --version
```

在 GPU 计算节点上，先打印宿主机驱动和镜像实际安装的 PyTorch CUDA 版本。不要只根据
`apptainer.def` 中写的版本推断最终环境，因为后续 Conda/Pip 安装可能覆盖它：

```bash
nvidia-smi --query-gpu=driver_version,name --format=csv,noheader

singularity exec --cleanenv "$SIF" env HOME=/tmp \
  python -c 'import torch; print("torch:", torch.__version__); print("built CUDA:", torch.version.cuda)'
```

再使用与当前集群日常任务一致的 `--nv --cleanenv` 和 bind 方式验证。

```bash
singularity exec --nv "$SIF" \
  python -c "import torch; print(\"torch:\", torch.__version__); print(\"built CUDA:\", torch.version.cuda); print(\"CUDA available:\", torch.cuda.is_available()); print(\"GPU:\", torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"unavailable\")"
```

预期结果：

- `torch.cuda.is_available()` 为 `True`；
- 能输出计算节点的 GPU 名称；
- PyTorch 的 built CUDA 不高于宿主机驱动支持的 CUDA API。

## 8. 配置 dojo 使用该版本

镜像文件名必须遵循当前 wrapper 的约定：

```text
superimage.root.<VERSION>.sif
```

例如本文生成：

```text
superimage.root.2026-07-macos-v1.sif
```

在 `.env` 中设置镜像目录：

```bash
SUPERIMAGE_DIR=/path/to/shared/sif/
```

在 `src/dojo/configs/interpreter/jupyter.yaml` 中设置相同版本：

```yaml
superimage_version: "2026-07-macos-v1"
read_only_overlays: []
```

`SUPERIMAGE_DIR` 是目录，`superimage_version` 只写版本部分，不要写完整文件名。

## 9. 常见失败

### `operation not permitted`、loop device 或 mount 错误

确认构建命令包含 `--privileged`。如果仍失败，说明当前 Docker Desktop VM/版本不能满足
Apptainer 构建所需的 mount 能力。不要尝试在 macOS 宿主机直接安装并运行 Linux
Apptainer；改用一台 x86_64 Linux 构建机或云 VM 构建 SIF。

### Apple Silicon 构建极慢或某个 amd64 包异常

这是跨架构模拟的限制。先确认所有 Docker 命令都包含：

```text
--platform linux/amd64
```

若仍不稳定，推荐在 x86_64 Linux VM/服务器上执行完全相同的 builder 命令。不要构建
`linux/arm64` SIF 后传给 x86_64 集群；它不能在目标节点原生运行。

### Docker Desktop 磁盘耗尽

增加 Docker Desktop 的虚拟磁盘上限，然后清理临时 volume 再重试：

```bash
docker volume rm aira-apptainer-tmp
docker volume create aira-apptainer-tmp
```

谨慎使用 `docker system prune`，它会影响这台 Mac 上其他 Docker 项目的缓存和停止状态
容器。

### FAISS 包解析失败

这通常不是 Singularity 问题，而是 definition file 中的包版本或 channel 在构建时已经
变化。当前 definition 并没有锁定所有包的精确版本，所以同一个文件在不同日期构建可能
得到不同解析结果。应记录：

- Git commit；
- `SUPERIMAGE_VERSION`；
- builder 镜像版本；
- 完整构建日志；
- 最终 SIF SHA-256。

不要在失败时静默删除依赖，否则新镜像就不再等价于仓库定义的 superimage。

如果日志在安装 `faiss-gpu` 时出现下面的错误：

```text
mamba: .../libsolv... solver_addrule: Assertion `!p2 && d > 0' failed.
Aborted
exit status 134
```

这是 `mamba/libsolv` 依赖求解器自身崩溃，不是 FAISS 源码编译失败。当前未锁版本的
`faiss-gpu` 可以匹配到多个 CUDA 构建，而前一步已经安装了 `pytorch-cuda=12.4`；混合
`pytorch`、`nvidia`、`conda-forge` channel 时可能触发这个 solver bug。日志中的
`Pinned packages: python=3.12` 只是求解条件之一，不等于 Python 3.12 本身不受支持。

推荐在 `superimage/apptainer.def` 中把原来的：

```bash
mamba install -c pytorch -c nvidia -c conda-forge faiss-gpu -y
```

改成使用 classic solver，并锁定与 CUDA 12.4 对应的构建：

```bash
conda install --solver=classic -y \
    -c pytorch -c nvidia -c conda-forge \
    "faiss-gpu=1.12.0=*cuda12.4*"
```

然后重新运行完整 SIF 构建。Apptainer 的 `%post` 不能从失败位置续跑，但 Docker volume
中的下载缓存仍可复用。不要只反复运行原始未锁版本的命令；随着 channel 元数据变化，
它可能继续崩溃或解析出与 CUDA 12.4 不一致的新版 FAISS。

### RAPIDS 包失败

如果安装 RAPIDS 时同时出现：

```text
tarball has incorrect SHA256
extraction failed
Write failed
Truncated ZIP file data
```

优先按磁盘不足或下载被截断处理。一次 RAPIDS transaction 的“下载 5 GB”不等于只需要
5 GB 空间：求解器会同时保留压缩包、解压目录、已安装前缀和 Apptainer 临时 rootfs，
峰值可能需要数十 GB。

先在 Mac 上检查宿主机和 Docker Desktop 存储：

```bash
df -h /
docker system df -v
docker run --rm \
  -v aira-apptainer-tmp:/mnt \
  alpine:3.20 \
  sh -c 'df -h /mnt; du -sh /mnt'
```

如果空间紧张，在 Docker Desktop 设置中把虚拟磁盘上限提高到至少 120 GB，推荐
150 GB，并确认 Mac 物理磁盘有相应空间。随后删除失败构建留下的临时 volume 并重建：

如果空间充足、清理临时 volume 后仍反复在同一个包上得到相同的错误 SHA256，再检查
公司/校园代理、VPN 或 CDN 缓存；这种情况下文件可能在网络传输途中被截断或替换。

### 集群上 `singularity exec --nv` 报 CUDA/driver 错误

definition file 以 CUDA 12.4 为起点，不代表最终 Python 环境仍是 CUDA 12.4。旧版
`pip.requirements.txt` 包含未锁版本的 `torch` 和 `torchvision`，后续 Pip transaction
会覆盖 Conda 安装的 PyTorch。已有构建产物
`superimage.root.2026-07-macos-v1.sif` 实际被覆盖成了 `torch 2.13.0+cu130`。

当前仓库改用官方 `torch==2.5.1+cu124`、`torchvision==0.20.1+cu124` wheels，并在
`%post` 中增加构建期检查。重新构建时应保持以下约束：

- 不要把 Conda torchvision 0.20.1 加进 RAPIDS 25.02 的 native dependency solve；其
  旧 ffmpeg/zlib 依赖和当前 RAPIDS/conda-forge ABI 无法共同求解；
- 从 PyTorch 官方 cu124 index 安装严格匹配的 Torch/Torchvision wheels；
- 不要让 `pip.requirements.txt` 中未锁版本的 `torch`/`torchvision` 再次升级它们；
- 安装 cu124 wheels 后以及完整 requirements 安装后分别 import `torchvision` 并检查 `_has_ops()`，同时检查
  `torch.version.cuda`；版本或原生算子不符就让构建失败；
- 集群端先用宿主机 `--nv` 注入的 driver；不要盲目优先使用镜像内更旧的 compat driver。

这些修改不会改变已经生成的 SIF；必须基于修正后的 definition file 重新构建并传输新文件。

构建 Mac 是否有 GPU 与最终兼容性无关；关键是最终 PyTorch wheel/Conda package 的 CUDA
版本与运行节点 NVIDIA driver 的匹配关系。

### `torchvision::nms does not exist`

这通常不是“没有安装 torchvision”，而是安装了不匹配的 binary variant。典型情况是
`torch` 来自 CUDA 12.4 build，但 Conda 为同版本号的 `torchvision` 选择了 CPU build。
Pip 日志中没有再次显示 `Successfully installed torchvision`，也可能只是因为 Pip 发现
Conda 已安装同一版本号，于是复用了这个错误的 binary。

当前 definition file 不再使用 Conda torchvision，而是安装官方 cu124 wheels。构建时
应先看到：

```text
Wheel torch: 2.5.1+cu124
Wheel torchvision: 0.20.1+cu124
Wheel built CUDA: 12.4
```

Pip 安装后还会重复一次检查。任一检查失败都不应继续使用该构建产物。

### Pip 报 RAPIDS dependency conflicts

RAPIDS 通过 Conda 安装时，`libcudf`、`libcugraph` 等原生 Conda 包不一定以 Pip
distribution metadata 的形式出现。因此 Pip 可能声称这些包“没有安装”，即使 Conda
已经安装了对应 native library；不要仅为消除 Pip 警告安装 `cupy-cuda11x` 或手工降级
`cuda-python`。

当前 Conda solve 会选择 `cuda-python 12.9.7`；这仍是 CUDA 12 RAPIDS build 的合法
Conda 解，包版本号不等于目标 CUDA toolkit minor version。强行按照 Pip 的旧 metadata
降到 `cuda-python<12` 可能破坏 Conda 环境。

`xarray`、`mapclassify`、`numpy` 则同时在 Conda transaction 和 Pip requirements 中
固定为分别兼容 `pandas==2.1.4`、`scipy==1.11.4`、FAISS 1.12 的版本。若想系统性确认
Conda 侧完整性，应查看 `conda list`，而不是只依据 Pip 对 Conda native packages 的
检查结果。

### Mac 构建时 RAPIDS 错选 CUDA 11

Docker Desktop 的 Linux VM 没有 NVIDIA driver，Conda 因而看不到 `__cuda` virtual
package。仅使用 `nvidia/cuda:12.4.1` base image 并不足以让求解器自动选择 CUDA 12；
旧 recipe 因此实际选择了 RAPIDS 的 cuda11 build，日志中的 `cupy-cuda11x` 就是证据。

definition file 现在显式设置：

```bash
export CONDA_OVERRIDE_CUDA=12.4
```

并要求 `rapids=25.02=*cuda12*`、`cuda-version=12.4`。不要删除这两个约束。

## 10. 建议保存构建日志

为了以后判断两个 superimage 是否等价，建议正式构建时保存完整日志：

```bash
mkdir -p build/superimage/logs
set -o pipefail

docker run --rm \
  --privileged \
  --platform linux/amd64 \
  -v "$PWD:/workspace" \
  -v aira-apptainer-cache:/root/.apptainer/cache \
  -v aira-apptainer-tmp:/var/tmp/apptainer \
  -e APPTAINER_TMPDIR=/var/tmp/apptainer \
  -w /workspace/superimage \
  ghcr.io/apptainer/apptainer:1.4.2 \
  apptainer build --force \
  "/workspace/build/superimage/superimage.root.${SUPERIMAGE_VERSION}.sif" \
  apptainer.def \
  2>&1 | tee "build/superimage/logs/build-${SUPERIMAGE_VERSION}.log"
```

这里的 `tee` 在 macOS 宿主机执行，因此日志会保存在仓库的 `build/superimage/logs/` 中。

## 最终检查清单

- [ ] 目标集群是 `x86_64`，构建指定了 `linux/amd64`。
- [ ] 使用仓库当前的 `superimage/apptainer.def`。
- [ ] builder 版本已记录。
- [ ] 构建日志已保存。
- [ ] SIF 文件名符合 `superimage.root.<VERSION>.sif`。
- [ ] SIF SHA-256 已记录并在集群端验证。
- [ ] `singularity exec` 可以导入关键 Python 包。
- [ ] GPU 节点上的 `singularity exec --nv` 可以识别 GPU。
- [ ] dojo 的 Singularity/no-fakeroot wrapper 兼容修改已经完成并通过 smoke test。
