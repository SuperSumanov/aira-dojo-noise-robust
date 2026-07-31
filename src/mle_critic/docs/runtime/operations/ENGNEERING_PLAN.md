# 共享模型 Cache 工程计划

## 背景

当前集群环境已经提供了共享路径上的 cache：

- `HF_HOME=/research/d2/gds/zzchen2/transformerscache`
- `TORCH_HOME=/research/d2/gds/zzchen2/torchhome`
- `XDG_CACHE_HOME=/research/d2/gds/zzchen2/.cache`

但 Singularity 使用 `--cleanenv --no-home` 启动 Jupyter，宿主机的这些变量和目录不会自动进入容器。当前把 `HF_HUB_OFFLINE` 改为 `0` 只能允许 Hugging Face 访问网络；如果 cache 没有挂载，模型仍会下载到每个实验自己的 `/workspace/.home`，导致重复占用空间。

## 目标方案

让所有任务共享一个可写的 team cache，同时保持 cache 路径和环境变量显式、可审计：

```text
宿主机 cache 目录 --rw bind--> /shared-cache/*
容器环境变量 -------> /shared-cache/*
```

建议映射：

```text
/research/d2/gds/zzchen2/transformerscache -> /shared-cache/huggingface
/research/d2/gds/zzchen2/torchhome         -> /shared-cache/torch
/research/d2/gds/zzchen2/.cache            -> /shared-cache/xdg
```

容器内显式设置：

```text
HF_HOME=/shared-cache/huggingface
HF_HUB_CACHE=/shared-cache/huggingface/hub
HF_DATASETS_CACHE=/shared-cache/huggingface/datasets
TORCH_HOME=/shared-cache/torch
XDG_CACHE_HOME=/shared-cache/xdg
HF_HUB_OFFLINE=0
```

## 代码修改边界

1. 在 Jupyter interpreter 配置中增加 `read_write_binds`，与现有只读 `read_only_binds` 分开，避免误把数据目录变成可写。
2. 在 Singularity command builder 中把该配置转换为 `--bind source:destination:rw`。
3. 在 Apptainer backend 中提供等价的读写 bind 行为，或明确记录该 backend 的兼容限制。
4. 只 allowlist cache 相关环境变量，不要把宿主机环境全部继承进容器；特别是不要暴露 `HF_TOKEN` 等凭证。
5. 保留 `HF_HUB_OFFLINE=0` 作为显式配置，不要在代码中静默覆盖用户设置。
6. 更新 Slurm 节点路径检查，读写 bind 的宿主路径在启动前也必须存在且可访问。

## 并发和空间风险

Hugging Face cache 使用 lock 文件和临时文件，多个 step 首次下载同一个模型通常可以并发工作，但 NFS 的锁和 metadata 性能需要实测。任务被强杀时可能留下不完整 cache，需要后续清理或重新下载。

当前 `/research/d2` 是 NFS，共享文件系统使用率约 93%；已有 Hugging Face cache 约 100 GB、Torch cache 约 4.3 GB。因此上线前需要：

- 监控 cache 的总大小和增长速度；
- 约定可清理的旧 revision/模型范围；
- 不删除仍在使用的 cache 条目；
- 测试并发下载、强杀恢复和 cache 损坏后的重试行为。

## 验证计划

1. 容器内打印上述环境变量，并确认路径可写。
2. 两个并发 step 首次加载同一个 timm 模型，确认最终只有一份有效权重。
3. 再次运行同一模型，确认命中共享 cache，不重复下载。
4. 使用 torchvision (`TORCH_HOME`) 和 timm/Hugging Face (`HF_HOME`) 各做一次下载测试。
5. 强杀一个正在下载的 step，确认另一个 step 能恢复或重新下载。
6. 确认 agent 代码无法读取不在 allowlist 中的宿主机凭证。

在该方案实现前，短期可以只把 `HF_HUB_OFFLINE` 设为 `"0"` 来运行低资源任务；这能验证网络和模型下载，但不会解决每个实验重复写 cache 的问题。
