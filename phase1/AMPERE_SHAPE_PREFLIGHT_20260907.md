# 两RTX3090、1.7B、16K真实尺寸资格验证（仅合成输入）

2026-09-07，承接用户本次六小时会话自主授权。不是新科学效应矩阵，不替代PRO6000验收或数据准入。

首次Linux CPU准备在测试前被新扫描器截住，未提交模型job。只报位置/长度/hash的诊断确认唯一命中位于
verify_critic_component_g0.py:465，匹配前为字母；原有规范扫描器带单词边界，该项不命中。
新入口遗漏边界导致普通连字符标识中的sk-后缀被误认为key；现与source-package既有规范逐字对齐，
同时覆盖AWS形状，增加五类凭据阳性/普通标识阴性回归。未回显命中内容，原失败CPU目录保留，另新目录运行。
先前备选路线现细化为独立入口，原PRO源/矩阵/冻结结果均不修改。失败记录原样保留，不自动重试。

问题：在实际可排到的两张RTX3090上，独立critic能否完成最长输入的G更新/全状态保存，
然后新进程恢复全部状态并完成L更新/第二次保存？不检验accuracy、不比较两个方法，不声称完整尺寸最终参数等价。

固定1个作业：gpu28，gpu_24h，12CPU，2×RTX3090，mem=0，60min；驱动3000秒，FA2数学180秒。
1.7B-Base固定snapshot，1720577025参数，BF16/FlashAttention2/ZeRO3+CPUAdam，seed6，学习率1e-5。
上下文16384；每rank每microbatch为1pair，累积64次，global pair batch128。
两个阶段各128pair、全程8388608有效tokens；同一256synthetic endpoints，G/L边不交叉。
显式改变硬件和micro形状，但不改变完整长度、总pair/token、模型与数学阈值；不混合两种硬件的吞吐结果。

预算：新尺寸7920 GPU秒保守上界（2×(3600+300+60)），全工程上限36000。
旧18次9423实际GPU秒，R4构建实际3199；新Ampere构建上限5760，并为原PRO尺寸保留3840。
控制器按实际sacct逐一核对，拒绝未知job/漂移；最多一条尺寸轨迹提交或运行，防止空间预留释放后并发写超额。
预计尺寸20—50分钟，非实测吞吐；截止前不足完整墙钟则不启动。每次更新都在新进程里，稳态timing样本为0。

## 13项预检与验收边界

1. 实际Slurm型号/数量/CPU/节点/时限、模型参数、attention backend、dtype均从真实产物复核。
2. 新入口和失败负控先本地及实际Linux；已通过tiny真实save/restore的sha绑定，但不冒充大模型验收。
3. 不调用任何真实训练或保护评测数据。固定synthetic-only guard在runtime import前拒绝非本配置plan。
4. 逐rank/逐阶段，不能只有汇总；两个设备分别做FA2数学验收。
5. 无accuracy/抽样成绩；FA2 dense129和varlen31+97，以FP32 causal GQA为参考，前向/dq/dk/dv同时满足relL2≤.02且maxabs≤.05。
6. 两次完整checkpoint，随后独立逐字节hash和真实六角色payload检查；没有保存就不算完成。
7. 训练驱动运行在文件访问trace下，检查保护路径标记；此trace不包括网络调用，不冒称完整sandbox。
8. 固定RNG，在新进程故意设置错RNG后恢复；核对CPUAdam native bias-power缓存恢复，不降低到model-only。
9. 源/回执/发布先credential shape scan，只推安全结构结果；不含raw历史程序或密钥。
10. kernel后重新核剩余3000秒驱动+60秒清理余量；记录完整墙钟、初始化、保存；每段首更新与稳态分开。
11. 合成序列仅为长度/显存/软件路径验收，不代表真实tokenization、训练功效或泛化。
12. shell先捕获真实rc，子任务有界终止，原日志不覆盖；退出0之后还须独立验收。
13. 不更改语料抽签/first960/Target300/522；ADMITTED_RELEASES不改、正式四fit未启动。

独立目录包含完整预检、held提交、独立review、source/实际64GiB容量/已完成构建绑定；
Ampere的sm80库只能经本入口显式接受，原sm120门仍拒绝。GPU数值门不因耗时或失败而放宽。
当前源是准备状态，是否真实执行以及是否通过，以后续Slurm和独立postflight为准。
