# 给学长：9月5日 G-reuse 正结构结果、G0 终态与最小解锁项

这是一页状态交接。主线仍是 Decision Corpus + Predictor Benchmark + Audit Protocol；没有恢复HCE、多保真、
Probe或底座训练，也没有读取first960/Target300/Target522结果。最新公开入口为`CURRENT_DIRECTION.md`顶部。

## 0. 开正式15-fit前新增一个功效门

只用历史评测结构的28个匿名task pair-count做了结果盲敏感性。真实+2pp时，task-CI门在事前
optimistic/reference/stress假设下功效为99.60%/61.40%/25.10%，80%约需12/43/126个同结构任务。
这只是CI门；主协议还要求观测点差≥2pp、三seed同向和多个比较门，所以整体通过概率更低，真实效应恰为2pp时
仅点差门就至多约50%。因此同producer包交付时，请同时给exact frozen evaluation的匿名逐task pair数；我们会在
训练前重算，不降2pp门，也不在揭盲后补样本。当前语料总体51任务不等于评测支持51任务。完整回执见
`results/g_reuse_effect_power_b27115a_20260905/README.md`；这不是critic负结果，而是防止花完15 fits才发现CI先天过宽。

## 1. 今天得到的三个正结构结果

我们把方法候选收窄为：在同一批已执行L端点上，增加由已有执行分数导出的global比较，再适配local sibling。
这叫G-reuse→L，仍待模型效果验证。

最新scoop补检需再收窄措辞：ACL Findings 2025的JPO已有跨instruction-response联合偏好胜同context DPO；
EMNLP 2025的Licht等已有连通comparison graph上的pointwise/pairwise微调、edge-count控制和vertex split讨论。
因此不再说首次跨context/global preference或首次连通图微调。我们的区别只能是固定agent底座的MLE critic、
同执行程序人口global→local顺序、执行成本/physical-run来源和前瞻盲审计组合；效果不通过就没有方法正主张。

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

## 1.5 本交接提交后的两项补充

1. 4K/8K/16K/raw四种长度口径下，790-edge basis的总体G-token reduction均为70.43%--71.48%，
   leave-one-task最差仍为68.08%--69.36%，最大任务saved-token share为16.60%--17.80%。但四种口径下都达到
   单任务50%节省的只有19/28，低于预注册20/28门；总状态诚实记为NOT ROBUST，不能说逐任务普遍节省。
2. 更关键的正结果：在endpoint-level comparison graph上，full 2745边相对同rank的790-edge basis把汇总
   有效电阻降低55.33%；任务中位降低61.33%，27/28任务严格下降，最大等权任务贡献5.92%，预注册五门全过。
   主实现用Laplacian eig，独立verifier用inverse公式；首次outer byte-exact门因`1.82e-12`浮点抖动失败并保留，
   只按事前容差修复后全新根通过。这个结果说明cycle不只是rank冗余，因此full G应保留为效果主臂，basis只作
   成本challenger；它仍不是critic accuracy。见
   `results/g_reuse_cycle_information_782a7c7_20260905/README.md`。
3. 固定每任务full与basis之间一半额外token预算后，cost-aware spectral selector的D-opt capture为72.68%，
   高于cheapest 59.98%和SHA-order 62.22%；未直接优化的A-opt capture为87.44%，也高于59.24%/73.65%；
   27个cycle任务中24个不劣于两baseline。但预注册绝对门是D≥75%、任务中位≥70%，实得72.68%/68.70%，
   所以总状态记为NOT SUPPORTED，不能降门。可用信息是“相对简单baseline更有效”，不能写成达到预定保真度。
   见`results/g_reuse_spectral_midpoint_7648451_20260905/README.md`。
4. 事前固定25%/50%/75%三个同预算点后，spectral在每一点的D与A capture都严格高于cheapest和SHA-order；
   三点spectral D为47.09%/72.68%/89.52%，A为68.45%/87.44%/96.15%，D同时不劣两baseline的任务数
   为26/24/26（分母27）。七项相对优势门全过，producer A/B、独立verifier和下载hash复验通过。
   这把“中点偶然胜出”升级为跨固定预算曲线的相对正结果，但不撤回中点D≥75%与任务中位≥70%的绝对门失败。
   因此spectral可作为后续模型效果实验的成本challenger，仍不能称critic效果或算法首创。见
   `results/g_reuse_spectral_frontier_8ab7d3c_20260905/README.md`。

效果实验现已收敛为两级、避免臂膨胀：先用full G-reuse做原五臂×seed6/7/8 core，只有主部署门通过才增加
3个spectral50 fit；50%因为它在完整曲线前已冻结，不按75%更漂亮的结构数事后换点。cost stage要求G token
至少省25%、总token至少省10%，且相对full的task-CI下界>-1个百分点；不通过就停，不试另两个点救回。
旧历史输入下50%预计G-stage省35.67%、总量省13.50%，但权威同producer包到来后必须在看效果前重算。
完整边界见`G_REUSE_EFFECT_TRANSLATION_DECISION_20260905.md`。

这套15+3层级矩阵现已固化为`g_reuse_effect_protocol_v1.json`。主/独立验证器对协议SHA
`2e95b73ca6a21c45502bc64919dd1dc5f447bd5f21f61f939dbbcfd97f080ed5`、臂数、seed数和blocked状态一致；
16项攻击/回归通过。它不会自行把pending来源或G0改成通过，也不授权GPU；因此材料到达时可以直接验收、
材料未到时会拒绝开跑，避免把旧9392-row文件临时改名为新方法输入。

最新scoop核验需补一个重要边界：RecSys 2026已有“固定候选池每个候选带离线标量标签、pairwise LambdaRank以五seed
胜single-action RL”；ACL Findings 2026已有“标量MOS转pair、gap分层和难对奖励”；UAI 2025已有absolute+comparative
组合。因此我们不能声称稠密复用标量标签、gap分层或一般混合监督首创。仍可防守的是MLE执行成本/physical-run来源、
同执行人口global→local受控消融和前瞻盲审计的组合；见`GLOBAL_LOCAL_RELATED_WORK_BOUNDARY_20260905.md`。

随后更贴近部署语义的结构检查显示：full有96.76%边跨local parent context，触达928/1473 contexts，双端覆盖
1934/4689 local pairs；parent-rank gain=787且28/28任务为正。spectral50省35.67% G token并完整保留parent-rank
和context coverage，但双端local-pair coverage只保留full的70.73%，未过预注册75%门；总状态必须NOT SUPPORTED。
因此full主臂得到更直接结构支撑，而spectral50风险也被提前暴露：只允许core成功后真实训练检验，不能凭谱数字称无损。
见`results/g_reuse_decision_context_reach_d379f00_20260905/README.md`。

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

包级交付格式和验收器现已在`G_REUSE_SOURCE_PACKAGE_DECLARATION_V1.md`与
`validate_g_reuse_source_package_v1.py`就绪（安全加固版Linux 11项攻击测试通过）。它先核七个角色、hash/LFS、路径安全及
producer receipt一致性；即使通过也只叫hash-bound declaration，仍需下面的逐run来源v2和真实payload隔离核验。

已有验收字段和脚本在`SOURCE_DECLARATION_V2_20260904.md`及
`validate_senior_source_provenance_v2.py`。若历史来源无法权威恢复，直接声明不可恢复并提供新的连贯开发包即可；
不要为了复现3058/2745/790这些诊断数而改生产规则。

## 4. 新语料

Drive中发现并原样同步0903目录的9个新压缩归档，共299,168,545字节；未解包/读member/覆盖旧文件。
它们要到UTC 2026-09-05 00:09:48.832417后才满足固定六小时稳定门，当前source archive=325、eligible仍619/960。
稳定门过后继续走原credential-first intake和独立结构复核，不能提前加数。
