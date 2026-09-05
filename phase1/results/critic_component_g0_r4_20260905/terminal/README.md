# G0 12486 终态：真实双卡启动后在 CPU Adam 初始化失败

核验日期：2026-09-05；香港时间 13:07:12 开始、13:10:23 结束。
Slurm `FAILED / NonZeroExitCode / 1:0`，ElapsedRaw=191，分配两张 PRO6000，Requeue=0、Restarts=0。
这不是十步训练成功，也不是 critic 效果结果。没有自动重试、修改 runtime 或启动其它 GPU 作业。

## 根因与交叉证据

1. rank0/rank1 的日志均显示，在 `accelerator.prepare` 将 optimizer 映射为 DeepSpeedCPUAdam 时，
   `CPUAdamBuilder().load()` 因无法运行 `ninja --version` 而失败。发生在 optimizer 初始化阶段，未进入训练更新。
2. 私有 `file_access.strace` 中两个进程对运行环境 bin、/usr/local/bin、/usr/bin、/bin 共八次
   ninja execve 均返回 ENOENT。不是仅凭错误消息猜测“包没安装”。
3. selective runtime 的 `ninja-1.13.0.dist-info` 存在，但没有 console_scripts；RECORD 的实际二进制条目为
   `../../../bin/ninja`。原 overlay 中该文件存在，SHA 为
   `696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67`。
4. 既有 `tmp/g0_selective_runtime_20260903.py` 的环境重建逻辑跳过所有以 `..` 开头的 RECORD 条目，
   只重建 Python console_scripts。因此它复制了包/版本元数据，却遗漏这个非 console-entry 的可执行文件。
   依赖闭包记录 SHA `5fad91f03344543e5389d0bf85438256b3eb4fed5aa0e8928f7c36e9875bf017` 与当前
   ninja RECORD SHA `929c89ba62848ae8012fa24a6ca227dbde2b02ef1b5232b1abfb02a9c283af02` 相符。

这是我方运行环境重建及真实依赖预检的缺口，不是学长语料问题，也不是已观察到的显存不足。
不能声称补上 ninja 后其余编译工具链、CUDA 路径或十步训练必然通过。
日志另有 gradient-accumulation plugin 1 / DeepSpeed 8 的警告；启动器称采用 DeepSpeed 的值，
本次未进行更新，故实际累积行为仍不能由本次失败认证。

## 产物与资源

`FAILED` 和 `training_exit_status=1` 相互一致；`verification.json`、`COMPLETE`、`output/checkpoint-10` 均不存在。
两卡遥测各 15 次采样，采样到的最大使用显存分别为 1819 MiB；不是完整训练峰值估计。
source HEAD `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`，control HEAD
`adbfa80180e44805a6c0231e55c000b4718ad23b`，两者 tracked 工作树均干净。
CORRECTED_READY/RELEASED 哈希未变。运行预检与训练启动日志记录了既定三输入哈希；
本轮未重新读取训练 payload 或全量模型文件，不能据此签发成功后的完整资产复验。

|job|ElapsedRaw 秒|GPU 数|分配 GPU-seconds|状态|
|---|---:|---:|---:|---|
|12181|156|2|312|FAILED|
|12288|4|2|8|FAILED|
|12377|131|2|262|FAILED|
|12486|191|2|382|FAILED|

四次累计 **964 GPU-seconds = 0.2677777777777778 GPU·h**；距原 14400 GPU-seconds 上限剩 13436。
这些是 sacct 分配时间核算，排队不计入；剩余额度不构成下一次提交授权。
`resource_usage.txt` 的 launcher wall 1:13.66 只覆盖训练启动段，不替代整份 Slurm 分配时间。

## 安全与复验范围

- 先在远端扫描和脱敏，再输出操作日志；两份日志和 trace 的 credential-shape 命中为 0。
- 原始 63,762,349-byte trace 留在远端私有目录；SHA
  `3fc3777c59f411b2819ea0c837d0c9822f2ef84de05e26ce2bcb9d43f3125852`。
- 对 trace 的 first960/Target300/Target522/prospective 根路径标记扫描为 0；
  这只是标记扫描，不是完整 PID/cwd/symlink 解析的访问隔离证明。
- 没有读取保护 cohort 的 payload，也没有导出历史 dev 指标来选模型。
- 第二个诊断脚本首版因缺少词边界将普通长标识内的 `sk-` 子串误判为 credential，输出前停止；
  原首版保留远端。修正词边界后验证该类误报 2 处，真实 credential shape 为 0。
  首版失败不计通过，也没有回显命中内容。

## 只读原始回执

|文件|SHA-256|
|---|---|
|terminal_diagnostic.json|1da81720ff6b1cd06a9e59309746dd0b637d9a05447ede94f2a494597fd7109f|
|ninja_evidence.json|2eb14f01cb65253932edc86aa70333d59c65e7b7bcf2da4e640cf66f16b62509|
|ninja_package.json|5d44f26ba1b6fc48ceb92f7636e384d66da3879fd7357cdd8826124d7784a8ba|

回执由远端 `/tmp/g0_12486_terminal_readonly_20260905.py`、
`/tmp/g0_12486_ninja_evidence_20260905_r2.py`、`/tmp/g0_12486_ninja_package_readonly_20260905.py`
以现有 exp Python 执行，仅检查该作业、既定环境文件和 Slurm 记账；安全 JSON 下载后再核字节哈希。

## 下一步边界

本作业失败终态已由 Slurm、双 rank 日志、实际 execve 和失败标记交叉确认；到此结束该作业守护。
建议后续修复只补齐精确哈希的缺失入口，不改 optimizer、训练配置或 agent 底座；先在实际启动 PATH 下
验证 ninja/编译工具链及 CPU Adam 初始化，再绑定新的不可变 runtime 回执和准确剩余预算。
这些修复与重试尚未执行，下一次 GPU 提交必须另行批准，禁止重复提交旧作业或把 READY 改成 COMPLETE。
