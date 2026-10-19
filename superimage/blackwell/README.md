# Blackwell Superimage

这是供 MLEBench agent 执行代码的镜像，沿用上层 `superimage` 的工具、Python 包和
SSH 接入方式。目标机器是 Linux x86_64、RTX PRO 6000 Blackwell，计算能力为 12.0
（`sm_120`）。原有 `superimage/apptainer.def` 保持不变。

## 1. 环境组成

| 项目 | 版本 / 配置 |
| --- | --- |
| 基础镜像 | `nvidia/cuda:12.8.1-devel-ubuntu22.04` |
| Python | 3.11 |
| PyTorch / torchvision | `2.7.1+cu128` / `0.22.1+cu128` |
| RAPIDS | 25.04，显式安装各组件 |
| CuPy | 13.6.0 |
| FAISS | 1.12.0，从源码编译 `sm_86` 和 `sm_120` |
| implicit | 0.7.2，Conda GPU 构建 |

PyTorch 2.7 开始提供 Blackwell 和 CUDA 12.8 wheels。FAISS 使用 CUDA 12.8 的
编译器生成目标 GPU 的代码，因此基础镜像选用包含编译器的 `devel` 版本。
FAISS 默认使用 4 个编译进程；Apple Silicon 模拟构建时，编译会明显慢于原生 x86_64。

旧 RAPIDS 总包依赖的 `rapids-xgboost` 在本次依赖求解时无法获取，所以这里直接列出
cuDF、cuML、cuGraph、cuVS、cuCIM、cuSpatial 等组件，XGBoost 沿用 Pip 安装。
`constraints.txt` 约束关键二进制包，后续安装 agent 常用包时继续使用同一组版本。
镜像内默认设置 `PIP_CONSTRAINT=/opt/blackwell/constraints.txt`。

当前节点实测驱动为 `570.211.01`，`nvidia-smi` 显示 CUDA 12.8。
镜像按这组驱动选择 CUDA 12.8；构建机器可以没有 GPU。

## 2. 在 Linux 构建

从仓库根目录执行：

```bash
mkdir -p build/superimage
cd superimage/blackwell
apptainer build --fakeroot \
  ../../build/superimage/superimage.root.2026-10-blackwell-v1.sif \
  apptainer.def
```

有 root 权限时可以改用 `sudo apptainer build ...`。使用 Singularity 的机器将
`apptainer` 换成 `singularity`。构建阶段执行不需要 GPU 的包检查，GPU 检查单独运行。
构建目录固定为 `superimage/blackwell`，以便 `%files` 找到当前目录和上层的文件。

## 3. 在 macOS / Docker 构建

从仓库根目录执行，Docker Desktop 需要提供 amd64 模拟和足够的磁盘空间：

```bash
mkdir -p build/superimage
docker volume create aira-blackwell-apptainer-cache
docker volume create aira-blackwell-apptainer-tmp
set -o pipefail
docker run --rm --privileged --platform linux/amd64 \
  -v "$PWD:/workspace" \
  -v aira-blackwell-apptainer-cache:/root/.apptainer/cache \
  -v aira-blackwell-apptainer-tmp:/var/tmp/apptainer \
  -e APPTAINER_TMPDIR=/var/tmp/apptainer \
  -w /workspace/superimage/blackwell \
  ghcr.io/apptainer/apptainer:1.4.2 \
  apptainer build \
  /workspace/build/superimage/superimage.root.2026-10-blackwell-v1.sif \
  apptainer.def \
  2>&1 | tee build/superimage/blackwell-build.log
```

重试覆盖同名文件时，在 `apptainer build` 后加 `--force`。
这个配置复用 `superimage/build-openssh.sh`，传到构建机时请保留整个 `superimage` 目录。

## 4. 在 PRO 6000 节点测试

传回 SIF 后，从仓库根目录执行：

```bash
export SIF="$PWD/build/superimage/superimage.root.2026-10-blackwell-v1.sif"
nvidia-smi
set -o pipefail
singularity exec --nv --cleanenv "$SIF" \
  env HOME="$HOME" \
  python superimage/blackwell/verify.py --gpu --require-blackwell \
  2>&1 | tee build/superimage/blackwell-gpu-check.log
```

这条命令使用当前仓库里的检查脚本，并显式传入宿主机的 HOME，现有镜像也可以直接测试。
CuPy 默认在 `$HOME/.cupy/kernel_cache` 写入编译缓存。新构建的镜像保留运行用户的 HOME，
并将 `/opt/blackwell` 下的配置和脚本设为所有用户可读。
此前构建出的镜像里这些文件可能是 `0600 root:root`，普通用户无法读取镜像内的
`/opt/blackwell/verify.py` 和 `constraints.txt`；这条权限修正需要重建镜像生效。
同样的权限问题也影响旧镜像里使用 `PIP_CONSTRAINT` 的 Pip 安装。

检查分成三部分，遇到错误直接退出：

1. 核对 Conda CUDA 构建及原生库包记录、最终 Python 包版本、PyTorch CUDA 版本、
   torchvision 算子和 FAISS GPU 接口。
2. 在每张可见 GPU 上运行 PyTorch 前向/反向、cuDNN 卷积、BF16 矩阵乘法、
   torchvision CUDA NMS。
3. 在第一张可见 GPU 上运行 CuPy kernel、cuDF 求和、cuML KMeans、cuGraph
   PageRank、FAISS GPU 检索和 implicit GPU ALS。

3090 可以复用同一条检查命令，去掉 `--require-blackwell` 即可。
`implicit` 的 Conda GPU 包仍需在目标节点实际执行 ALS 确认；若出现
`no kernel image is available`，保留完整日志，需要继续处理这个包的 GPU 构建。
这组检查覆盖列出的库；agent 使用其他 CUDA 扩展时，也需要执行相应任务验证。

构建会把环境清单写入镜像的 `/opt/blackwell/manifest/`：

```bash
singularity exec --cleanenv "$SIF" cat /opt/blackwell/manifest/pip-freeze.txt
singularity exec --cleanenv "$SIF" cat /opt/blackwell/manifest/conda.json
```

## 5. 接入 Dojo

将文件放到项目使用的 `SUPERIMAGE_DIR`，配置：

```yaml
superimage_version: "2026-10-blackwell-v1"
```

文件名保留 `superimage.root.<version>.sif` 的格式。这个目录负责 agent 执行环境；
VERL 训练所用的 `verl_vllm.sif` 继续使用各自的构建流程。

## 6. 构建时的依赖检查

这里使用 Conda 安装 RAPIDS、CuPy 和 CUDA 原生库，Pip 安装 PyTorch 和其他 Python 包。
RAPIDS 25.04 的部分 Conda 包保留了与 Conda 构建不一致的 Python 依赖元数据。例如，
`rmm-25.4.0-cuda12_py311_250409_7c7c1fbb` 的 Conda 依赖要求
`cuda-python >=12.6.2,<13`，包内的 Python 元数据却要求 `cuda-python >=11.8.5,<12`。
Pip 也无法把 Conda 的原生库包当作同名 Python distribution 识别。

因此，`pip check` 会报告 `librmm` 等库缺失、`cupy-cuda11x` 缺失和 CUDA Python
版本冲突。这些报告不能直接用于判断这套混合环境是否完整，构建流程使用
`verify.py` 核对 Conda 包记录和 CUDA 构建，以及实际安装的 Python 包版本。
目标节点上的 `--gpu` 检查进一步确认这些库能执行 GPU 运算。
遇到上述报告时，保持当前 CUDA 12.8 依赖；安装 `cupy-cuda11x` 或降级
`cuda-python` 会破坏这组配置。

## 参考

- NVIDIA GPU 计算能力：https://developer.nvidia.com/cuda/gpus
- PyTorch 2.7 Blackwell 支持：https://pytorch.org/blog/pytorch-2-7/
- PyTorch 官方版本配对：https://pytorch.org/get-started/previous-versions/
- RAPIDS 安装要求：https://docs.rapids.ai/install/
