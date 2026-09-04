# G0启动前失败与可恢复修复 — 2026-09-04

本轮解决一个真实执行阻塞；**没有训练完成、吞吐计价、accuracy、scaling或搜索收益**。
公共基线提交 `bbc860f221671348540929fb6d72ec5847902ccd`，当前科学主线与冻结门不变。

## 实际发生了什么

Slurm记账：12288在香港12:19:37获配2 GPUs，12:19:41 `FAILED/1:0`，总4秒。
worker日志115字节，唯一错误是源码工作树不干净；未跟踪文件只有`uv.lock`。没有preflight完成回执、
launcher日志、GPU telemetry、output、checkpoint或dev评估。原worker在该检查前尚未安装FAILED标记处理，
所以没有FAILED文件不代表成功；依据Slurm及原worker日志判断。没有修改旧worker或补造其标记。

锁文件1035259字节，SHA `e4ce9bf353c905d9c360e9bd3eb869f7db3281f4cb23ef203cd590253feaeb0d`，
mtime为香港02:03:53.877038445；与本会话此前误用默认uv环境吻合。此前清理`.venv`后没有重新核验整个工作树，
是我方流程疏漏。不能把本次失败归为显存/NCCL或双卡计算问题，因为尚未执行到那里。

## 修复与独立复核

脚本位于 `phase1/scripts/repair_g0_untracked_lock_20260904.py`。执行前精确核source commit、完整git状态、
文件大小/SHA/owner/inode、安全形状扫描和空队列；仅移动一个已验证文件，不递归移动或删除。
远端独占目录：`/research/d7/spc/yzyang4/critic-component-g0/source-repair-12288-20260904`。
`quarantined-uv.lock`保留原字节和inode，权限0400，可由所有者恢复；该原文件没有下载或上传Git。
专用source root权限0700→0500，防止根目录再次生成锁文件或默认环境；**不是整个目录树的不可变证明**。
跟踪源码未改；clean gate没有关闭或放宽；G0参数和开发/冻结协议未改。

固定源码 `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`；控制源码
`94ad7dafff1866c6d50eb54927a4bf56547facc2`；运行库为原selective环境。
从隔离目录（非源码目录）执行 `g0_readonly_asset_recheck_20260904.sh`，原assets检查重新哈希历史train/dev/Cards
与10个模型文件，只加载config/tokenizer，CUDA不可见，没有权重构造/训练。随后执行原来已审阅的
`/tmp/g0_recovery_bound_recheck_20260903.py`（其版本已存在9月3日launch_helpers），核65项依赖版本、5项关键文件，
把原CPU保存回归与当前框架重新绑定，没有重跑合成训练。脚本退出0、COMPLETE存在；完整日志保留远端。
除`created_at_utc`外新assets回执与旧回执完全一致，runtime binding整个JSON一致。

`verify_g0_source_repair_20260904.py`是独立只读实现，不导入修复器/原assets检查器。
它检查原始日志、git、源文件哈希、隔离inode/SHA、静态回执一致性、Slurm实际记账与空队列；不打开真实数据或模型。
两次执行的输出保存为 `independent_verification_a.json` / `independent_verification_b.json`，逐字节一致。
原失败日志诊断、before/repair/assets/runtime JSON已保留；凭据形状扫描无命中。

- assets SHA `fc68a2602429e42d6096f800646dfd9df5b071cafccbd780c5925fd7bf8f4cd8`
- repair SHA `84109372c55a780b7c1650030769a2d37ad59788ea8c6588e5af0544133d30d0`
- worker log SHA `e3d31e64e13a74a38ef31273826fc51f2317c26c9e583eab341bc60cd8a97776`

本地相关27项回归通过：新回执绑定、G0原契约、历史开发v1及冻结v2。这些是工程正确性检查，不是新的研究样本。
另从已暂存Git树导出新旧回执，在干净目录复验5项通过，避免本地工作树字节掩盖发布问题；不是全项目或GPU复验。
推送前文件名和凭据形状扫描均0。一次跨Git实现的文件名扫描失败已弃用，随后Windows同一shell重查成功，见`validation.json`。

## 预算与下一门

12181（156秒×2卡）与12288（4秒×2卡）合计320 GPU秒。建议**另批一次2卡117分钟**；
连同历史失败的累计最坏上限14360 GPU秒 = 3.988888888888889 GPU·h，低于原4 GPU·h。
数值由独立脚本从Slurm记账计算，不用人工估算标题数字。先前只授权一个successor，已被12288使用；
因此本轮没有重新投递。若获准，使用新独占submission目录/no-requeue，完整11项预检及当时存储预留复查后才能提交。
9月3日4 GiB空间预留成功是历史证据，本轮未重复实际空间预留，不能当作当前空间承诺。

G0仍只做固定10步/一次历史dev/唯一checkpoint的工程计价，不选模型、不进入五臂效果评估。
正式15 fits需要独立GPU预算和来源门，不因为G0修复或用户要求加快而绕过。

## 同步科研状态

05:00:24 UTC只读结构检查见`structural_status.json`：316归档、619/960 eligible runs、config-v2=0、closure=false；
摄取PID3884166 live/poll119 rc0。学长仍b8d0951，无新commit/outcome或来源补充包。全部冻结前瞻值保持不可读。
Global→Local来源问题及给学长清单见`SENIOR_GLOBAL_LOCAL_UNBLOCK_20260904.md`，未创建新训练池或筛掉异常pair。
先取得同版本历史开发包、exact-config/experiment边界和G0计价，再执行获准后的跨seed同预算验证；这是待验证方向，不是正结果承诺。
