# CUHK CSE GPU-HPC 上手文档

> 账号：`yzyang4`（CSE 邮箱与存储，linux5 上也是它）
> 存储：`/research/d7/spc/yzyang4`（1TB，到期 2026-09-29）
> 提交节点：`linux5`（linux5.cse.cuhk.edu.hk，学长指定）
> 计算方式：SLURM 集群，用 `srun` / `sbatch` 申请 GPU
> 注：proj103 是老网关机，不在上面跑实验，VSCode 也连不上它

---

## 第 0 步：连接（用 linux5）

本地 `~/.ssh/config` 已配好（已加入 linux5），直接：

```bash
ssh linux5
```

看到 `yzyang4@linux5:~$` 即成功。

VSCode：装 Remote-SSH 插件后，左下角蓝/绿按钮 → Connect to Host → 选 `linux5`。
linux5 系统较新，**大概率能直接连上**（不像 proj103 因 glibc 太老被拒）。若仍报
"prerequisites for glibc/libstdc++"，先在 linux5 上跑 `ldd --version` 看版本，
≥ 2.28 才支持新版 VSCode Server。

---

## 第 1 步：确认 linux5 能提交 SLURM 作业

连上后逐条运行：

```bash
which srun sbatch sinfo      # 有路径输出 = 装了 SLURM
sinfo                        # 看有哪些队列(partition)、GPU 空闲情况
sacctmgr show assoc user=$USER format=account,qos%30   # 看你能用的 account / qos
```

- `sinfo` 能列出队列 → linux5 就是提交节点，继续往下。
- 命令 not found / 空白 → 回邮件问 Gary，或问学长确认提交方式。

可用的公共队列（配 `--account gpu --qos gpu`）：
`gpu_2h`(调试) / `gpu_8h` / `gpu_24h` / `gpu_72h`(训练,3天) / `batch_168h`(7天)。
带 PI 名字的私有队列(pheng_gpu 等)一般提交不了，组内队列问导师。

---

## 第 2 步：放置环境变量（env_setup.sh）

在 linux5 家目录创建文件：

```bash
nano ~/env_setup.sh
```

粘贴 `env_setup.sh` 的内容（我给你的那份），重点补两处：
- `HF_TOKEN=` → 填你在 huggingface.co/settings/tokens 生成的 token
- 用中转站时填 `OPENAI_API_KEY=` 和 `OPENAI_API_BASE=`

保存（Ctrl+O, 回车, Ctrl+X）。然后让它每次登录自动生效：

```bash
echo 'source ~/env_setup.sh' >> ~/.bashrc
source ~/env_setup.sh           # 立即生效一次
```

验证存储能访问、缓存目录已建好：

```bash
ls -ld /research/d7/spc/yzyang4   # 应能看到你的目录
echo $HF_HOME                     # 应输出 /research/d7/spc/yzyang4/cache/huggingface
```

> ⚠️ 家目录配额很小，所有缓存/数据/环境都放 `/research/d7/spc/yzyang4`，别堆在 `~`。

---

## 第 3 步：建 Python 环境（推荐 uv）

安装 uv（比 conda 快很多）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc        # 让 uv 进入 PATH
# 若 curl 被墙：改用 pip install uv --user
```

把虚拟环境建在大存储里（不要建在家目录）：

```bash
uv venv /research/d7/spc/yzyang4/venvs/exp --python 3.11
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
```

装包（示例，按需改）：

```bash
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install transformers datasets accelerate vllm wandb
```

> 用 conda 也行：`bash Miniconda3-latest-Linux-x86_64.sh -p /research/d7/spc/yzyang4/miniconda3`，同样装到大存储。

---

## 第 4 步：交互式调试 GPU（srun）

需要边敲边看、调通代码时，开一个交互式 GPU shell：

```bash
srun -p gpu_2h --qos gpu --account gpu --gres=gpu:1 --pty /bin/bash
```

回车后你就在一台 GPU 节点上了，验证：

```bash
nvidia-smi          # 看到分配给你的 GPU
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
python -c "import torch; print(torch.cuda.is_available())"   # True 即成功
```

`gpu_2h` 上限 2 小时，调试足够。退出用 `exit`，GPU 立即释放。

---

## 第 5 步：正式训练（sbatch 批量提交）

长时间训练别用交互式（断网就没了），改用 `run_experiment.sbatch`。先准备：

```bash
cd /research/d7/spc/yzyang4/my_project
mkdir -p logs
```

打开脚本，改三处：`--partition` 换成第 1 步记下的长队列、激活环境那行、最后的训练命令。然后提交：

```bash
sbatch run_experiment.sbatch        # 返回作业号，如 Submitted batch job 12345
squeue -u $USER                     # 查看排队/运行状态
tail -f logs/12345.out              # 实时看输出
scancel 12345                       # 需要取消时
```

作业在后台跑，你可以断开 SSH，不影响。

---

## 第 6 步（可选）：Singularity 容器

集群不给普通用户 Docker 权限，需要 Docker 镜像时用 Singularity（缓存已在 env 里指向大存储）：

```bash
# 把 Docker 镜像拉成 .sif 文件
singularity pull docker://pytorch/pytorch:2.5.0-cuda12.4-cudnn9-runtime

# 用 GPU 运行（--nv 启用 GPU）
singularity exec --nv pytorch_2.5.0-*.sif python train.py
```

在 sbatch 里：把最后的 `python train.py ...` 换成 `singularity exec --nv 你的镜像.sif python train.py ...` 即可。

---

## 常用命令速查

| 目的 | 命令 |
|---|---|
| 连接 | `ssh linux5` |
| 看队列/GPU | `sinfo` |
| 交互式 GPU | `srun -p gpu_2h --qos gpu --account gpu --gres=gpu:1 --pty /bin/bash` |
| 提交作业 | `sbatch run_experiment.sbatch` |
| 看我的作业 | `squeue -u $USER` |
| 取消作业 | `scancel <作业号>` |
| 看日志 | `tail -f logs/<作业号>.out` |
| 激活环境 | `source /research/d7/spc/yzyang4/venvs/exp/bin/activate` |
| 查剩余配额 | `quota -s` 或 `du -sh /research/d7/spc/yzyang4` |

## 几个提醒

- **Claude Code / Codex**：香港服务器直连不了官方 API，要走中转站，把 `OPENAI_API_BASE`/`OPENAI_API_KEY` 填成中转站给的值。中转站是第三方，别上传敏感数据。
- **WandB**：已设 `offline`，训练日志存本地；要同步再在能联网的机器上 `wandb sync`。
- **清理空间**：1TB 会比想象中快满，定期 `du -sh /research/d7/spc/yzyang4/*` 看谁占地方，删掉不用的 checkpoint。
- **常用数据集**：CSE 可能已提供公共数据集，先查 https://i.cse.cuhk.edu.hk/technical/gpgpu-hpc-service/commonly-used-dataset/ ，别重复下载占配额。
