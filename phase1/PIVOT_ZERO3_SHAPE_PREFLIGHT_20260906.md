# 正式尺寸的独立critic运行验收：容量恢复后准备新路径

最新执行状态（UTC02:57:20）：source50f2967ad2637850742075454440aea2c5fa8a28；
171项Linux CPU、49源文件/运行时、真实64GiB容量检查通过。新job12577经独立held核验后已release，
PENDING/Resources，暂估香港19:38:15开始，非保证。原12535仍held。
19份安全原始回执见results/pivot_12577_submission_20260906；尚无GPU终态或模型效果验收。
以下“准备中”“未提交”只记录各自较早时点，不允许据此再次submit或release。

2026-09-06容量恢复后更新：旧submission-20260906保留失败终态，未产生GPU作业。
用户在清理完成后明确要求继续向critic收益/干净scaling推进，本轮采用新的
submission-20260906-capacity-recovered；不是原地重跑或自动重投。
同一矩阵、同一模型/科学代码/数据/seed/预算，仅更换exclusive准备与临时缓存目录，
并核验旧失败未提交、清理回执及新的真实64GiB分配。清理成功不替代本轮/作业开始时空间门。
该更新写入时仍为准备状态；不承诺PRO6000排队时长，正式四fit来源资格仍需单独满足。

下面原UTC01:12:03失败记录完整保留。

实际状态更新：2026-09-06 UTC01:12:03，source ef19d100ac6cb1a747c332eb1b8596051f47a695。
Linux160项CPU检查和模型/运行时绑定通过，但64GiB真实分配EDQUOT(errno122)，实际分配0。
未产生READY或SUBMITTED，也没有新GPU job。原准备路径已失败结束，不得原地重跑或绕过空间门。
证据见results/pivot_space_failure_20260906。下面保留失败前固定的矩阵，不代表已经实际跑过。

2026-09-06。用户本会话已明确批准合理改动和继续执行；本矩阵已在运行前向用户说明。
这是新的1.7B/16K工程阶段，不沿用旧tiny approval中禁止预训练权重的权限。
旧12535保持held；不修改或放行那个旧源码作业。四fit数据准入仍为空。

## 唯一问题

已经通过tiny双GPU恢复检查的**同一新consumer与生产model factory**，在
Qwen3-1.7B-Base、16K、两PRO6000、microbatch8/accum8下，能否完成更新、完整保存、
新进程恢复，并继续一个更新？这里不是准确率、收敛、模型收益或正式语料资格检查。

## 结果前固定的矩阵

- 官方既有Qwen3-1.7B-Base snapshot ea980cb0a6c2ae4b936e82123acc929f1cec04c1；
  同原manifest SHA ceb388235719297e3647478ad2d96486a41d1f84e4c3fd8301c4772d6840e148。
- 新consumer，原生产factory：独立critic、bf16/FA2/ZeRO3 CPUAdam、weight decay0、
  1e-5 warmup-then-constant、固定seed6、2×8×8；不改agent或训练臂配置。
- **纯合成整数token/目标**，每个endpoint恰为16384 tokens，不读旧G0 train/dev或任何真实语料。
  G128pairs、L128pairs，G完全复用L的256endpoints；两次128pair完整更新，共8388608 valid tokens。
  这不是真实代码序列化验证，也不能拿最大长度的运行耗时冒充实际新数据的速度。
- 第一进程组完成G更新并保存checkpoint1；第二全新进程组恢复，完成L更新并保存checkpoint2。
  原tiny已测不中断/两个断点的严格最终比较。本尺寸仅做保存恢复接入和容量检查，
  **不宣称在1.7B尺寸额外重做了完整不中断最终等价对照**。
- 一次2PRO6000/projgpu39/12CPU/mem0作业，26min wall，driver最多1200s，kill60s。
  上界3840GPU秒，计入300秒退出与60秒余量；不自动重试、降batch或切attention backend。
- 明确列出的前序工程实际7006GPU秒，连本次保守上界10846，不超过14400。
  该账是逐job复核的工程总账，不是全项目或正式四fit费用；旧tiny和本新阶段权限分开。

## 硬门

实际tiny12575 payload、FINAL读出和trace/只读总验收全部完成后才放行。
本次模型完整manifest重hash、精确源码/运行栈、GPU类型、Slurm资源及CPU负控须先通过。
研究盘先做64GiB实际分配检查（68719476736bytes），不是df空闲量或稀疏文件：
两份checkpoint仅FP32 master+Adam矩下界即41293848600bytes。初稿44GiB只对该下界留余量，
预检发现还须覆盖BF16/重复保存与格式开销，故在实际分配/提交前提高到64GiB；不改变训练矩阵。
检查仅创建/删除本任务自身、inode已核对的可再生预留文件；失败保留回执，不清理用户资产。
提交前检查并非对未来容量的保证，作业开始时再核；存储失败不得开始模型。

## 13项预检映射

1. 从实际GPU与session binding核旋钮；2. 新fixture/预算/入口/保存分支先CPU测；
3/7. 合成输入不读取任何train/dev/test，保留文件trace；4. 不产出逐任务效果或均值改善；
5. 两阶段同plan/seed/模型/优化器；6. 保存完整参数、master、Adam、scaler及三类RNG；
8. 新进程先扰动RNG再验证真实restore；9. 源码及公开回执凭据扫描；
10. 固定墙钟和逐job实际费用、旧速度只作量级参考；11. 不声称两步足以训练或证明功效；
12. 独立保存子进程/worker/Slurm退出码；13. 保护人口和所有冻结协议逐字保持。

通过时仅关闭“新consumer在正式尺寸下无法保存/恢复”的工程门。真实来源、experiment隔离、
实际编码计划、四fit总预算和最终开发效果仍需另行满足。失败按真实失败保留，不改成PASS。
