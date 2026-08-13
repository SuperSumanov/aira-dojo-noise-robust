# Schema/probe smoke：Singularity runtime 基础设施修正记录

日期：2026-08-13  
性质：生成结果出现前的基础设施修正，不改变实验处理、样本或裁决阈值

## 观察

首次可调度的生成作业 `10603` 在两个 entry 启动 interpreter 时均以 rc=1 退出。host 日志的共同
错误是 `apptainer: command not found`，随后旧脚本尝试写 `/scratch` 也失败。两个 entry 均没有进入
LLM 调用、没有生成 code，search export/静态门禁/replay 均未发生；链式 monitor 按设计停止。

为验证根因，提交了只读/无 API 的 runtime smoke：

- `10604`：在 gpu37 直接检查 `apptainer`，命令不存在，作业 rc=1；
- `10605`/`10606`：在 gpu27 尝试兼容入口，预检脚本本身失败，未运行容器；
- `10610`/`10611`/`10613`：在 gpu39 逐步确认 compute node 实际提供
  `/usr/bin/singularity` 3.5.2，不提供 `apptainer`；旧版 `instance list -a` 与其不兼容；
- `10612`/`10614`：分别在 gpu39/gpu37 核对 runtime 文件；二者均只有
  `/usr/bin/singularity`；
- `10615`：复制 `/usr/bin/singularity` 为临时兼容名并去掉不支持的 `-a` 后，容器内 Python
  smoke 成功。但这只是诊断，不作为正式 workaround。
- `10616`：正式 interpreter smoke 在 import 时因未加载 `LOGGING_DIR` 退出，尚未启动 runtime；
  测试脚本只补充与真实生成一致的 `env_setup.sh` + 远端 `.env` 加载，不改变 interpreter；
- `10617`：正式 `JupyterInterpreter` smoke 通过。compute node 为 gpu39，runtime 为
  `/usr/bin/singularity` 3.5.2，superimage SHA-256 为
  `801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda`；public train 只读绑定可见，
  固定代码 exit_code=0，host roundtrip 文件一致，干净关闭。解释器内实际执行墙钟 7.242226 秒，
  Slurm 作业 `COMPLETED|0:0`。

同时核对学长当前采集分支 `fork/dojo-reproduce@2cb6f0c`。该分支已在历史 commit `db67d6b`
和 `4eeef40` 中提供正式 `SingularityJupyterServer`，`jupyter.yaml` 明确使用
`container_runtime: singularity`；最近 Qwen/K2 采集正基于这套实现。隔离实验分支缺失这组已验证
runtime 支持，是本次失败的根因。

## 修正

从学长远端分支的已跟踪版本原样移植以下六个文件（不是读取 tarball，也没有接触 `.env` 内容）：

- `src/dojo/config_dataclasses/interpreter/jupyter.py`
- `src/dojo/configs/interpreter/jupyter.yaml`
- `src/dojo/core/interpreters/jupyter/apptainer_jupyter_server.py`
- `src/dojo/core/interpreters/jupyter/jupyter_interpreter.py`
- `src/dojo/core/interpreters/jupyter/singularity_jupyter_server.py`
- `tests/test_singularity_jupyter_server.py`

该实现直接调用 compute node 已有的 `singularity`，给每个 Slurm step 分配稳定端口，将 agent
workspace 和 public data 分别以 rw/ro 绑定，并对日志中的 token/key 环境变量做脱敏。不会改变
schema/probe prompt、DeepSeek 模型、task、seed、预算、checkpoint 或 PASS/PARTIAL/FAIL 定义。

## 重提前新增门禁

1. 官方 targeted tests 全部通过；
2. Hydra 两任务解析均显示 `container_runtime: singularity`；
3. 先提交一个无 LLM 的 `JupyterInterpreter` GPU smoke，要求：启动同一 superimage、只读绑定
   public data、执行一段固定代码、host 读回预期输出、干净关闭，rc=0；
4. 只有 1--3 全通过才允许原矩阵重提；重提使用新的基础设施 commit，并在外部 prereg 目录记录
   `10603` 失败证据和本修正的文件哈希；
5. 仍禁止换 task/seed、重看生成结果后改 prompt、或把诊断 smoke 算作实验样本。
