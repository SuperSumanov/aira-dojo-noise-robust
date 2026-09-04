# 给学长：9月5日 G-reuse 正结构结果、G0 终态与最小解锁项

这是一页状态交接。主线仍是 Decision Corpus + Predictor Benchmark + Audit Protocol；没有恢复HCE、多保真、
Probe或底座训练，也没有读取first960/Target300/Target522结果。最新公开入口为`CURRENT_DIRECTION.md`顶部。

## 1. 今天得到的三个正结构结果

我们把方法候选收窄为：在同一批已执行L端点上，增加由已有执行分数导出的global比较，再适配local sibling。
这叫G-reuse→L，仍待模型效果验证。

1. 原3058条G-reuse对L图增加924 incidence rank；结果前的跨任务门全部通过：28/28任务正gain，
   最大任务只占8.55%，删除最强任务仍保留91.45%。这排除“总体增益由少数任务制造”。
2. 再排除143条observed config不等或193条旧source projection未解析边的并集，只留既有四格中的2745条，
   仍保留790/924=85.50% rank gain；28/28任务正gain，最大任务占9.11%。这只叫记录缺陷敏感性，
   不能把2745命名为clean训练池。
3. 对2745条按两端valid-token做确定性最小生成森林，只需790条边即可逐任务保留全部790 gain；
   G阶段token从19,601,875降到5,773,896，减少70.54%，L+G从51,789,617降到37,961,638。
   最大endpoint degree 14→6，top-decile访问占比31.79%→20.82%。这只是待效果验证的comparison basis；
   cycle边可能帮助噪声鲁棒/优化，不能提前称模型无损。

三项均为结果前提交源码、producer A/B、独立verifier A/B、输入/源码/下载manifest哈希复验；GPU/API/fit=0。
正式目录分别是：

- `results/g_reuse_task_breadth_39aee47_20260905/`；
- `results/g_reuse_record_consistent_e4d89b0_20260905/`；
- `results/g_reuse_min_token_basis_319ba30_20260905/`。

## 2. G0 12377 没有训练，已修到真实launcher边界

Slurm记账：12377为FAILED/exit1，双卡131秒，即262 GPU-seconds。失败发生在真实launcher开始后0.02秒：
共享env先在只读source下建默认`outputs`，permission denied；没有模型加载、DeepSpeed/NCCL或十步成本结论。

控制侧现只把共享env的默认OUTPUT/LOG指向本次run root，学长launcher/source及所有训练参数不改。真实只读source
初始化A/B和exact launcher fake-accelerate C/D均通过；真实train/dev/cards SHA、双进程、16K、有效batch128、
十步、seed6、final-only和无test参数已走到`accelerate launch`边界。仍不能代替真实双卡验证。

前两次失败累计已分配582 GPU-seconds。若继续遵守累计≤4 GPU·h，则新双卡successor最大墙钟必须为
6909秒（1:55:09），而不是117分钟；最坏累计恰为14400 GPU-seconds。successor尚未提交，需用户重新批准。

## 3. 仍最关键的上游解锁项

上述结果没有解决版本来源。当前L/Cards/G来自不同历史包，`equal observed config`不是producer attestation，
旧manifest的`unique`也不是权威source修复，完整experiment split未证明。请优先提供一个同producer版本、
历史开发专用的Cards/G/L/split/source包，而不是仅增加pair行：

- 各文件完整SHA/LFS OID、producer commit与生成命令；train/dev/frozen物理分开；
- 每run不可变来源声明：run_id、task、launch/source date、batch/archive SHA、journal member、producer instance；
- 实际完整generator/config绑定，并按whole experiment做train/dev/frozen，之后再验pair/card/run零交集。

已有验收字段和脚本在`SOURCE_DECLARATION_V2_20260904.md`及
`validate_senior_source_provenance_v2.py`。若历史来源无法权威恢复，直接声明不可恢复并提供新的连贯开发包即可；
不要为了复现3058/2745/790这些诊断数而改生产规则。

## 4. 新语料

Drive中发现并原样同步0903目录的9个新压缩归档，共299,168,545字节；未解包/读member/覆盖旧文件。
它们要到UTC 2026-09-05 00:09:48.832417后才满足固定六小时稳定门，当前source archive=325、eligible仍619/960。
稳定门过后继续走原credential-first intake和独立结构复核，不能提前加数。
