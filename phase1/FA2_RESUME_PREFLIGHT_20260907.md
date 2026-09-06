# 官方FA2构建：有界续编，不重跑科学实验

## 准备阶段格式纠正（尚未提交）

首次R4准备被ninja_log_version门挡住：实际固定ninja 1.13.0日志是v7，检查器误假定v5。
本机原日志有32完成对象，旧partial submission目录和副本保留，不覆盖；无新增job/GPU费用。
修复只接受实际v7，保持五字段严格解析、未知版本拒绝与完整hash门。
[官方v1.13.0 build_log.cc](https://github.com/ninja-build/ninja/blob/v1.13.0/src/build_log.cc)
定义v7签名和五字段写入格式；不将v5转换成v7或重写原ninja日志。
新submission-v7采用独立源码目录，只有验证旧准备未达到READY/提交后才能接续。

2026-09-07六小时会话内。12641实际FAILED/1:0，2126秒、1保留GPU；
真实原因为compile阶段2100秒超时，并非新的CUDA编译错误。原始失败日志与回执保留。
CPU目标仍是补齐12577缺少的FA2依赖；不能把构建称为真实模型收益。

## 新矩阵与预算（由用户本次全权授权内决定，执行前公开）

单个续编作业，gpu37/1保留GPU/4CPU/mem0，最长90分钟；实际compile最多4800秒。
由于该账户QOS要求最少1GPU，虽不创建CUDA context，仍完整记录保留GPU成本。
保持2个compiler worker、NVCC_THREADS=2、sm120、显式原g++13及其hash，官方2.8.3源码和所有kernel不改。
不换torch/ABI、不换模型或attention后端、不缩短16K、不改变两卡验收数值门。

历史7297GPU秒+12641实际2126=9423；本续编保守5760加后续双卡3840，组合19023GPU秒。
旧4GPUh不足，本次明确采用6GPUh/21600GPU秒工程链上限，不把超出旧预算隐藏掉。
不包含任何真实数据训练fit；新作业仍先held、独立核对后只release一次，无自动retry/requeue。

## 续编复用与独立验证

新回执/日志/wheel/overlay位于独占flash-attn-build-20260907-r4；原r3失败回执只读保留。
只继续r3的编译工作目录：先冻结ninja命令图、完成日志副本和每个成功对象的bytes/SHA，
逐文件核对官方sdist源码及原runtime，禁止重复/越界/非ELF对象，未知状态停止。
完成后所有原成功对象和ninja命令图必须逐字节相同，官方源码再次核对；这不是从头丢弃失败重来。
原r3的.ninja_log将随续编增长，其旧字节副本保留；不能宣称r3工作目录完全未改变。
旧slurm/compile/timeout/source回执不会覆盖。原r5环境不改，装入r4隔离overlay。
新完整wheel/overlay hash、CPU导入之后，仍须双PRO6000数值门与完整1.7B/16K保存恢复验收。
旧未运行的r3消费者配置不能直接使用，会在新产物正式完成后显式换绑r4及真实job/source。

## 13项预检适用性

1. 参数、commit、官方源码、编译命令图、二进制和实际Slurm成本全部留证。
2. 新代码有格式、路径、重复对象、非ELF、原终态/预算漂移、重复JSON负控，Linux实测后提交。
3–5. 无数据切分、pair分布或accuracy评估；不冒称通过相应统计条件。
6. 构建中间对象保留且可校验复用，原失败日志不可覆盖；训练checkpoint门不因此替代。
7. 不读任何语料/保护cohort；不调用API，不访问密钥。
8. 无随机抽签/训练seed；后继验收仍seed6，不改变恢复测试。
9. push前凭据形状及staged文件名扫描，安全元数据以外不外发。
10. 编译内外超时分别4800/5400秒，保守计费5760；失败停止，无循环续编。
11. 不把依赖修复称为训练功效或方法证据，ADMITTED_RELEASES不改。
12. 真实rc、Slurm终态、完整wheel、原成功对象不变均须核对，不能凭echo接受。
13. 不扩开发范围/改hold/换数据；0905仍只走原结果盲摄取链。
