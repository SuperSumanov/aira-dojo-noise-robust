# 使用 Conda Python interpreter 替代 Superimage

日期：2026-07-27

本文说明在没有 Apptainer/Singularity，或 Docker NVIDIA Container Toolkit 不可用时，如何直接
使用 README 中创建的 `aira-dojo` conda 环境运行 agent。该方案不构建或启动
`superimage`，而是使用仓库自带的 `PythonInterpreter` 在当前 conda 环境的子进程中执行候选代码。

这是一条适合可信本机实验和调试的路径。它不提供容器隔离：agent 生成的代码会以当前用户权限访问
宿主文件、网络和 GPU。

## 1. 适用范围和运行模型

默认的实验配置通常选择 Jupyter interpreter，例如：

```yaml
defaults:
  - override /interpreter: jupyter
```

Jupyter interpreter 需要 `superimage`、Jupyter Kernel Gateway 和容器运行时。命令行覆盖为
`interpreter=python` 后，调用链变为：

```text
main_run
  -> PythonInterpreter
  -> 当前 aira-dojo Python 的 multiprocessing 子进程
  -> exec(agent 生成的 Python 代码)
```

因此不需要以下 superimage 组件：

- Apptainer/Singularity/Docker；
- `jupyter-kernel-gateway`、SSH daemon、overlay；
- superimage 中的 `/opt/conda`；
- `apptainer.def` 的 Ubuntu apt 包。

需要注意，Python interpreter 仍然使用 `PythonInterpreter` 的超时和工作目录机制，但不再有
Jupyter kernel 或容器级文件系统隔离。

## 2. 创建或确认 README 环境

如果尚未创建环境，按照仓库 README 执行：

```bash
conda env create -f environment.yaml
conda activate aira-dojo
python -m pip install -e .
```

如果环境已经存在，先确认解释器和核心数值栈，不要为了匹配 superimage 而降级它们：

```bash
conda activate aira-dojo
python --version
python - <<'PY'
import numpy, pandas, scipy, sklearn

print("numpy:", numpy.__version__)
print("pandas:", pandas.__version__)
print("scipy:", scipy.__version__)
print("scikit-learn:", sklearn.__version__)
PY
```

README 环境当前预期为 Python 3.12、NumPy 2.2、pandas 2.2 和 SciPy 1.15。`environment.yaml`
本身使用 pip requirements transaction，因此后续 Python 包也建议用当前环境中的
`python -m pip` 安装，而不是对已有环境执行一次大范围的 `conda install` 求解。

## 3. 先安装 CUDA PyTorch

superimage 固定使用 PyTorch 2.5.1 / torchvision 0.20.1 的 CUDA 12.4 wheel。先安装这一对，
再安装其他深度学习包；不要在后续步骤中使用 `pip install --upgrade`，否则 pip 可能把它们换成
新的 CUDA 13 wheel。

```bash
python -m pip install \
  --index-url https://download.pytorch.org/whl/cu124 \
  torch==2.5.1 \
  torchvision==0.20.1
```

验证编译 CUDA、驱动可见性和 GPU 数量：

```bash
python - <<'PY'
import torch
import torchvision

print("torch:", torch.__version__)
print("torchvision:", torchvision.__version__)
print("built CUDA:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("GPU count:", torch.cuda.device_count())
for index in range(torch.cuda.device_count()):
    print(index, torch.cuda.get_device_name(index))
PY
```

至少应满足：

```text
torch: 2.5.1+cu124
torchvision: 0.20.1+cu124
built CUDA: 12.4
CUDA available: True
```

这个 wheel 自带 CUDA runtime 依赖，宿主机只需要兼容的 NVIDIA driver。是否安装
`nvcc` 或 Docker NVIDIA Container Toolkit 不影响这条路径。

## 4. 广覆盖 Python 包

以下列表从 [superimage/pip.requirements.txt](../../../../../superimage/pip.requirements.txt) 提取，去掉了
重复项，并调整了会破坏当前 README 环境的版本。已经存在于 `requirements.txt` 的包会被 pip
识别为 satisfied，不会重复安装。

### 4.1 传统 ML、表格、科学计算、图像和 NLP

```bash
python -m pip install \
  absl-py \
  arrow \
  backoff \
  bayesian-optimization \
  biopython \
  catboost \
  contractions \
  "datasets>=4,<6" \
  demoji \
  funcy \
  gensim \
  hmmlearn \
  imagecodecs \
  imbalanced-learn \
  implicit \
  librosa \
  lime \
  loguru \
  mapclassify \
  markovify \
  mlxtend \
  nltk \
  numba \
  onnxruntime \
  opencv-python-headless \
  pdf2image \
  pydicom \
  pyocr \
  pypdf \
  rank-bm25 \
  scikeras \
  shap \
  shutup==0.2.0 \
  spacy \
  statsmodels \
  textblob \
  textstat \
  umap-learn \
  vaderSentiment \
  xarray \
  xgboost \
  faiss-cpu \
  fasttext-wheel \
  gymnasium \
  albumentations
```

其中 `shutup` 是运行 `PythonInterpreter` 所必需的：它在子进程启动时被导入，但没有列在仓库
主 `requirements.txt` 中。

几个包名有意与 superimage 不同：

| superimage 条目 | 直接 conda 环境中的选择 | 原因 |
| --- | --- | --- |
| `fasttext` | `fasttext-wheel` | Python 3.12 有预编译 wheel，避免本地编译 |
| `spacey` | `spacy` | `spacey` 是拼写错误 |
| `gym` | `gymnasium` | 旧 Gym 已停止维护，和 NumPy 2 兼容性较差 |
| `imgaug` | `albumentations` | `imgaug==0.4.0` 使用已移除的 NumPy API |
| `faiss-gpu` | `faiss-cpu` | GPU 版会引入额外 CUDA/RAPIDS 求解；PyTorch GPU 不受影响 |

如果某个具体 competition 明确 `import gym`，可以单独测试 `gym==0.26.2`；不要把它无条件加入
公共环境，因为它没有现代 Python/NumPy 兼容保证。

### 4.2 深度学习、Transformer 和图学习

先完成第 3 节的 PyTorch 安装，再执行：

```bash
python -m pip install \
  accelerate \
  "fastai<2.9" \
  kornia \
  "peft<0.18" \
  "pytorch-lightning<2.6" \
  "sentence-transformers<6" \
  "tf-keras==2.21.0" \
  "transformers==4.49.0" \
  timm \
  torch-geometric \
  torchinfo \
  torchmetrics
```

`tf-keras` 是必装项，不是只在编写 TensorFlow solution 时才需要的可选包。当前 README/MLE-bench
环境会安装 TensorFlow 2.21.0 和独立的 Keras 3；但是仓库固定的 Transformers 4.49.0 在导入
`Trainer` 等组件时可能继续加载 TensorFlow integration，而该版本不支持 Keras 3。实测
`chaii-hindi-and-tamil-question-answering` 多 seed 任务因此反复在 `from transformers import ...`
阶段失败，错误明确要求安装 backwards-compatible `tf-keras`。

这里将 Conda 环境、仓库主 requirements 和 superimage 统一固定为 Transformers 4.49.0。原来的
superimage 配置使用不带版本号的 `transformers`，每次构建会安装当时的 PyPI 最新版，实际上
不可复现。4.49.0 是仍从顶层导出旧版 `transformers.AdamW` 的最后一个 4.x 版本，可兼容较多
历史 Kaggle/agent 代码；4.50.0 起已移除该导出。新代码仍应优先使用 `torch.optim.AdamW`，但固定
4.49.0 可以避免旧代码仅因这一处导入立即失败。

`torch-geometric` 的基础包可以直接安装；某些稀疏/采样算子还需要额外的
`pyg_lib`、`torch_scatter`、`torch_sparse` 等和具体 Torch/CUDA 版本匹配的 wheel。只有任务实际
使用这些算子时再按照 PyG 官方 wheel 页面补装，避免破坏已验证的 Torch 2.5.1/cu124 组合。

### 4.3 观测、追踪和可选工具

superimage 还包含 `weave`。它不是 agent 求解必需依赖，但如果实验配置或用户代码使用 Weights &
Biases Weave，可以单独安装：

```bash
python -m pip install weave
```

`weave` 会带来一组额外的 OpenTelemetry、GraphQL 和 PDF 相关依赖；建议不要把它和基础安装放在
同一个不可调试的大 transaction 中。

## 5. 可选的非 Python 工具

Python 包 `pdf2image`、`pyocr` 和某些图像/视频任务还需要外部程序：

```bash
conda install -n aira-dojo -c conda-forge \
  ffmpeg \
  poppler \
  tesseract \
  graphviz
```

对应关系：

- `ffmpeg`：音频、视频和 `librosa` 相关处理；
- `poppler`：`pdf2image` 调用的 PDF rasterizer；
- `tesseract`：`pyocr` 的 OCR backend；
- `graphviz`：图结构和模型可视化。

编译器、`cmake` 和 `pkg-config` 只有在某个包没有可用 wheel 时才需要。优先使用 wheel，避免
在当前环境中编译整个 superimage 的源码依赖。

## 6. 明确不建议直接安装的条目

### 6.1 会破坏主环境版本的条目

superimage 的 conda transaction 固定：

```text
numpy==1.26.4
pandas==2.1.4
scipy==1.11.4
rapids==25.02
faiss-gpu=1.12.0=*cuda12.4*
```

这些版本和当前 README 环境以及 MLE-bench 的 `pandas>=2.2` 要求不一致。不要把
`rapids`、`cudf`、`faiss-gpu`、`cuda-version` 和 `implicit-proc=*=gpu` 加入现有
`aira-dojo` 环境的同一次 conda solve。

如果确实需要 RAPIDS/cuDF，建议创建独立的 Python 3.12 + NumPy 1.26 环境，并让专门的任务
interpreter 使用那个环境；不要覆盖主 `aira-dojo` 环境。

### 6.2 可安装但维护/构建风险较高的条目

以下包暂不列入公共安装命令：

- `bayespy`：其 `truncnorm` 依赖在 Python 3.12 下可能无法生成 metadata；
- GitHub 版 `lightfm`：需要源码编译；
- `tensorpack`：偏旧的 TensorFlow 生态，和现代 TensorFlow/Keras 不一定兼容；
- `node2vec`：当前版本明确要求 `numpy<2`；
- `gym`、`imgaug`：旧 API 与 NumPy 2 兼容性差；
- superimage 的 `datasets==2.1.0`：版本过旧，使用现代 `datasets`；
- `implicit` 的 GPU 构建：pip wheel 通常是 CPU 版本，GPU 版本需要单独的 CUDA 编译方案。

## 7. 安装后完整检查

先检查依赖元数据：

```bash
python -m pip check
```

然后检查导入和 GPU：

```bash
python - <<'PY'
modules = [
    "torch", "torchvision", "xgboost", "lightgbm", "catboost",
    "sklearn", "imblearn", "statsmodels", "cv2", "PIL",
    "albumentations", "imagecodecs", "transformers",
    "tensorflow", "tf_keras",
    "sentence_transformers", "datasets", "peft", "timm",
    "fastai", "pytorch_lightning", "torch_geometric",
    "faiss", "implicit", "librosa", "gensim", "spacy",
    "shap", "shutup",
]

for name in modules:
    try:
        module = __import__(name)
        print(f"OK   {name:24} {getattr(module, '__version__', '')}")
    except Exception as exc:
        print(f"FAIL {name:24} {type(exc).__name__}: {exc}")
PY
```

再单独触发一次 Transformers 的 TensorFlow/Keras integration；仅执行 `import transformers`
不一定会加载到发生冲突的模块：

```bash
python - <<'PY'
import tensorflow as tf
import tf_keras
from transformers.activations_tf import get_tf_activation

print("tensorflow:", tf.__version__)
print("Keras 2 compatibility package:", tf_keras.__version__)
print("Transformers TF integration: OK", get_tf_activation("gelu"))
PY
```

如果这里仍出现 `Your currently installed version of Keras is Keras 3`，说明 `tf-keras` 没有安装到
当前正在运行 agent 的同一个 Python 环境；用 `which python` 和
`python -m pip show tf-keras` 检查，不要让候选代码在 workspace 中临时 `pip install --target`
另一个 Transformers 副本。后者可能遮蔽主环境的依赖并重复触发相同错误。

如果 `pip check` 只报告 `streamlit`/`protobuf`，这是当前环境与 MLE-bench TensorFlow 版本的
已知冲突，不一定影响 agent 主流程：

```text
streamlit 1.44.1 has requirement protobuf<6,>=3.20,
but you have protobuf 7.x
```

不要为了消除这一条警告盲目降级 NumPy 或 TensorFlow。只有在确实运行 Streamlit UI 时，才应
单独决定升级 Streamlit 或为 UI 创建独立环境。

## 8. 安装完成后将 Conda 环境标记为 externally managed

完成前面所有依赖安装和验证后，建议用 PEP 668 的 `EXTERNALLY-MANAGED` marker 阻止 agent
直接修改共享的 `aira-dojo` 环境。

虽然通常把 Conda 环境中的第三方包目录统称为 “site-packages”，但 marker **不能**写在
`site-packages/EXTERNALLY-MANAGED`。pip 25.0 实际检查：

```python
Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED"
```

在当前环境中，它通常是
`$CONDA_PREFIX/lib/python3.12/EXTERNALLY-MANAGED`；真正的 site-packages 则是其下一级
`$CONDA_PREFIX/lib/python3.12/site-packages`。把文件写进后一个目录不会生效。

激活目标环境后执行：

```bash
conda activate aira-dojo

python - <<'PY'
import sys
import sysconfig
from pathlib import Path

stdlib = Path(sysconfig.get_path("stdlib")).resolve()
site_packages = Path(sysconfig.get_path("purelib")).resolve()
marker = stdlib / "EXTERNALLY-MANAGED"
prefix = Path(sys.prefix).resolve()

if not stdlib.is_relative_to(prefix):
    raise RuntimeError(f"Refusing to write outside the active Python prefix: {stdlib}")

marker.write_text(
    "[externally-managed]\n"
    "Error=This aira-dojo Conda environment is managed by the operator. "
    "Agent code must not install or remove packages.\n",
    encoding="utf-8",
)
marker.chmod(0o444)

print("Python prefix:", sys.prefix)
print("site-packages:", site_packages)
print("PEP 668 marker:", marker)
PY
```

不需要 `sudo`，前提是当前用户拥有这个 Conda 环境。不要对 base 环境或其他用户的环境运行该
命令。写入后用一个不会真正安装包的命令验证：

```bash
python -m pip install --dry-run --no-index packaging
```

预期在依赖解析前失败，并包含：

```text
error: externally-managed-environment
This aira-dojo Conda environment is managed by the operator.
```

`python -m pip check`、导入已有包以及运行 agent 不受影响。以后确实需要维护环境时，可先撤销
marker，完成安装和验证后再重新写入：

```bash
python - <<'PY'
import sysconfig
from pathlib import Path

marker = Path(sysconfig.get_path("stdlib")) / "EXTERNALLY-MANAGED"
if marker.exists():
    marker.chmod(0o644)
    marker.unlink()
    print("Removed:", marker)
PY
```

PEP 668 是防误操作保险，不是权限隔离。pip 的 `--break-system-packages`、
`PIP_BREAK_SYSTEM_PACKAGES=1` 和某些 `--target` 安装可以绕过它，Conda/Mamba 也不读取该 marker；
而且以环境所有者身份运行的代码可以删除 marker。因此还应应用
[forbid_agent_package_installation.patch](../../../patches/forbid_agent_package_installation.patch)，让生成代码的
prompt 明确禁止通过 pip、Conda、subprocess、vendoring 或 workspace-local `--target` 安装依赖。

应用 prompt patch：

```bash
git apply --check src/mle_critic/patches/forbid_agent_package_installation.patch
git apply src/mle_critic/patches/forbid_agent_package_installation.patch
```

## 9. 用 Python interpreter 运行实验

对 README 中默认使用 Jupyter interpreter 的实验，加入 `interpreter=python`：

```bash
python -m dojo.main_run \
  +_exp=run_example \
  interpreter=python \
  logger.use_wandb=False
```

MLE-bench 示例：

```bash
python -m dojo.main_run \
  +_exp=run_example \
  interpreter=python \
  task.name=spaceship-titanic \
  logger.use_wandb=False
```

### 9.1 Spaceship Titanic 实测 smoke test

本文所述路径已经按照
[AIRA_DOJO_MLEBENCH_SPACESHIP_WORKFLOW.md](../../workflows/AIRA_DOJO_MLEBENCH_SPACESHIP_WORKFLOW.md) 的
单次 Spaceship 流程实测。与原 workflow 的区别是：原流程需要先 `salloc`，再用 `srun` 启动
Jupyter/superimage；本机 conda 路径不申请 Slurm 资源，也不启动容器，直接在当前 shell 执行
`main_run`。

前置条件：

- `MLE_BENCH_DATA_DIR/spaceship-titanic/prepared/{public,private}` 已准备；
- `mlebench` 已通过 `pip install -e .` 安装；
- `shutup`、`lightgbm`、`xgboost`、`torch==2.5.1+cu124` 等包已安装；
- `.env` 中的 `PRIMARY_KEY` 或 `PRIMARY_KEY_DEEPSEEK_V4_FLASH` 可用；
- 当前 shell 位于仓库根目录，并已激活 `aira-dojo`。

执行命令：

```bash
conda activate aira-dojo
set -a
source .env
set +a

# 避免本地 Jupyter/HTTP 服务或模型 endpoint 的 loopback 请求走代理。
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost

python -m dojo.main_run \
  +_exp=mlebench/aira_greedy_deepseek_flash_spaceship \
  interpreter=python \
  metadata.seed=42 \
  logger.use_wandb=false
```

运行前可以只解析配置、不调用 LLM：

```bash
python -m dojo.main_run \
  +_exp=mlebench/aira_greedy_deepseek_flash_spaceship \
  interpreter=python \
  metadata.seed=42 \
  logger.use_wandb=false \
  --cfg job --resolve
```

解析结果中必须出现：

```yaml
task:
  name: spaceship-titanic
metadata:
  seed: 42
interpreter:
  _target_: dojo.config_dataclasses.interpreter.python.PythonInterpreterConfig
solver:
  step_limit: 5
```

本次实际运行结果（2026-07-27）：

```text
Python: 3.12
Torch: 2.5.1+cu124
CUDA: available, 4 x NVIDIA GeForce RTX 2080 Ti

first valid candidate:
  5-fold CV Accuracy: 0.81081 (+/- 0.00909)
  submission: valid
  private test fitness: 0.82414
  gold threshold: 0.82066

final run:
  process exit code: 0
  final fitness: 0.82414
```

Smoke 的输出和 checkpoint 默认位于：

```text
$LOGGING_DIR/aira-dojo/user_<user>_issue_deepseek_flash_spaceship_smoke/
```

其中 `results/grading_report.json` 保存最终评分，`checkpoint/journal.jsonl` 保存每个候选节点的
执行结果。后续候选代码可能因为模型生成的代码错误而失败；这不代表 Python interpreter 或
数据准备失败。上面的运行中首个 LightGBM 候选已经完成有效 submission 和评分，后续失败节点
没有覆盖当前最佳结果。

### 9.2 为 Python interpreter 做的仓库改动

原来的 `src/dojo/tasks/mlebench/task.py` 在评分后使用：

```python
interpreter.run(f"!rm {self.cfg.submission_fname}")
```

这是 Jupyter shell magic，不是普通 Python 语法。使用 `interpreter=python` 时它会产生
`SyntaxError`；虽然原代码没有检查这个清理调用的返回值，但旧的 `submission.csv` 可能因此残留
并污染后续候选。

当前代码已改为 backend-neutral 的纯 Python 删除：

```python
interpreter.run(
    f"from pathlib import Path; "
    f"Path({self.cfg.submission_fname!r}).unlink(missing_ok=True)"
)
```

这段代码同时适用于 Jupyter 和 Python interpreter。修改后使用 `solver.step_limit=2` 做了一个
额外短 smoke，并用独立的 `PythonInterpreter` 测试创建/删除 `submission.csv`；清理成功，工作目录
中没有残留文件。

除上述清理修复外，本次完整 smoke 没有修改 solver、task、数据或 `.env` 配置，也没有依赖
Apptainer/Singularity、Docker、Slurm 或 superimage。

## 10. 安全和资源边界

Python interpreter 不等价于 superimage：

- 候选代码可以读取当前用户可读的宿主文件；
- 候选代码可以访问宿主网络；
- 候选代码可以看到当前环境安装的全部 Python 包；
- `CUDA_VISIBLE_DEVICES` 可以限制 CUDA 程序选择的 GPU，但不是安全隔离；
- 不应在此模式下运行不可信 agent 或不可信 competition 代码。

这条路径的目标是绕过容器运行时故障，同时保留尽可能完整的研究环境；如果需要真正的代码
隔离，仍应修复或恢复 Apptainer/Singularity 路径。
