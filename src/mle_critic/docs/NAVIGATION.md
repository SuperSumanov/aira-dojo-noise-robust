# `src/mle_critic/docs` 文档导航

这里的文档按用途分组。文件名保留原样，方便在代码、实验记录和历史讨论中检索。

## 运行流程

用于从任务配置到实际采集运行的端到端说明。

- [Spaceship Titanic 主流程](workflows/AIRA_DOJO_MLEBENCH_SPACESHIP_WORKFLOW.md)：当前 checkout 的 AIRA-Dojo × MLEBench 复现、Slurm/Singularity smoke test 和采数流程。
- [Spaceship Titanic 学生研究流程](workflows/AIRA_DOJO_MLEBENCH_SPACESHIP_STUDENT_WORKFLOW.md)：历史 `phase1-value-critic` 等研究分支的差异说明；不代表当前分支代码。
- [Lookahead reward model 实验](train/LOOKAHEAD_REWARD_MODEL_EXPERIMENTS.md)：L1、L2、LOTO、rescue、checkpoint sidecar 的运行命令和注意事项。
- [Lookahead 数据来源](train/LOOKAHEAD_DATA_PROVENANCE.md)：7,190-card corpus、迁移文件清单，以及未提交 L2 v2 数据的复原边界。

## MLEBench 任务筛选

用于决定哪些任务适合批量采数，以及估算数据规模和训练时间。

- [Low 任务](mlebench/INTRODUCTION_LOW_TASKS.md)
- [Medium 任务](mlebench/INTRODUCTION_MEDIUM_TASKS.md)
- [High 任务](mlebench/INTRODUCTION_HIGH_TASKS.md)
- [Split 中缺失的任务](mlebench/INTRODUCTION_MISSING_TASKS.md)

## 运行时与集群基础设施

涉及解释器、容器、GPU 调度、Slurm 迁移和运行环境排障。

### 解释器

- [Conda 直接解释器配置](runtime/interpreters/CONDA_DIRECT_INTERPRETER_SETUP.md)：不使用容器时的可信本机运行路径。
- [local GPU pool + Conda Python interpreter](runtime/interpreters/LOCAL_GPU_POOL_CONDA_PYTHON_INTERPRETER.md)：无 Slurm/容器时的本地 GPU 调度路径。
- [Chroot/Namespaces Python 隔离计划](runtime/interpreters/CHROOT_PYTHON_INTERPRETER_ISOLATION_PLAN.md)：实验性的宿主文件写隔离方案。

### 容器

- [Apptainer 到 Singularity 调查](runtime/containers/APPTAINER_TO_SINGULARITY_INVESTIGATION.md)：运行时差异和迁移边界。
- [macOS 构建 Superimage](runtime/containers/BUILD_SUPERIMAGE_ON_MACOS.md)：在 Docker Desktop 中构建集群使用的 SIF。

### 调度

- [本地 GPU pool + Singularity 设计](runtime/scheduling/LOCAL_GPU_SINGULARITY_DESIGN.md)
- [Slurm / srun pool 迁移调查](runtime/scheduling/SLURM_MIGRATION_INVESTIGATION.md)

### 运维与排障

- [共享模型 Cache 工程计划](runtime/operations/ENGNEERING_PLAN.md)
- [已知问题记录](runtime/operations/OTHER_BUGS.md)：端口冲突和 `CUDA_VISIBLE_DEVICES` 相关问题。

## LLM 后端与结构化输出

- [DeepSeek 结构化输出兼容性与修复记录](llm/AIRA_DOJO_DS_STRUCTURED_OUTPUT.md)

## 建议阅读顺序

第一次了解当前实验时，先看“运行流程”，再根据采数目标看对应的 MLEBench 任务筛选文档；需要部署或排障时进入“运行时与集群基础设施”。学生历史分支的说明只在需要对照 `phase1-value-critic` 时阅读。
