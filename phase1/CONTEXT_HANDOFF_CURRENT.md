# 当前短交接
更新：2026-10-11香港08:37，本轮排障进行中；六小时窗口至12:37:30。10/10旧窗口已闭合。旧全文保留于Git 3c04f3049fc2004b1ff3ecbd1728ec49ce6b9916；方向/路线旧全文另存于Git96e129c8，不改实验原件。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件；旧8月心跳与旧排队状态不作当前方向/许可。

## 10/11新增：先排障帮助学长现有方向，调度保留探索
- 用户转述学长建议两卡服务六卡MLE、medium，优先既有policy工作、部分投入资源调度，并要查六并发resource unavailable；随后明确去mle Google Drive找。全文要点入ADVISOR_DIRECTIVES X；不是我方底座训练许可或已测容量。
- 本人已快进发布并核验6606350921536098bb9bcc3a68f23bb18ae2f240（readiness修复、独立审计、缓存资格及失败保留）；08:18 fetch学长仍f7ccd79323112b10ccc82d8e9ec9d6cf089df607。未改学长分支；最新18文件/18未发布blob凭据形状0、字节差0；此前MSYS hook警告不是hook通过。
- 定位mle/comparison/1009八包；有界远端内存扫描Spooky/Dog日志，两个精确member独立重读SHA一致，均有OpenBLAS pthread_create失败且RLIMIT_NPROC soft=1024；请求线程数分别3/12。证据sandbox_scheduling/resource_unavailable_20261011/evidence.json，禁止把提示当已证上限命中或六并发阈值。
- 缺故障时同UID总线程数、cgroup pids/memory events与清理后残留；下一步同作业/容器采集后单旋钮验证，不无限提limit、不清别人进程。当前SSH登录soft/hard=1024/1024仅作非现场参照。首Dog扫描ValueError无细节、后续收窄有证据；Spooky跳过8大日志、Dog跳过5且首资源报错即停，不称完整普查。
- 新窗口用户授权：10/11香港06:37:30–12:37:30，会话内先解决六并发故障再推进实验；不靠新automation代替。已独立复核两份日志均为Singularity链，首次OpenBLAS故障邻近Jupyter导入，Spooky未见DataLoader。计数有重放，不当独立事件。
- 本地故障注入确认两个清理缺口：socket关闭异常跳过kernel删除、kernel清理异常跳过server停止；原代码3测试2失败，try/finally补丁后3通过。只在我方源码，未改学长分支；未证明历史六并发根因或真实修复。
- 原诊断17541已闭合：/research/d7/spc/yzyang4/resource-diag-20261011-v5，14计划/7尝试/6完成/1启动TimeoutError/7未开始，实际132GPU秒；单GPU仅因QOS必须预留，代码纯CPU，无MLE质量结论。v1/v2预检失败、v3零GPU/v4CPU比例被拒均无作业；不可抹除失败重算分母。
- 新定位真实管道bug：select(fd)+缓冲readline会吞就绪通知；精确f7源码真实Linux管道可稳定复现。单reader+队列补丁5/5本地及Linux回归通过，未增加超时。历史Spooky故障前26启动/25停止完成，无明显累计清理缺口；OpenBLAS打印1024并不证明命中NPROC，尚需故障现场总UID线程/cgroup证据。
- 17543 readiness-only独立复验已闭合：/research/d7/spc/yzyang4/resource-diag-readiness-fixed-20261011-v1，plan SHA21a063ca6ca7b4d25822b963cd55533ed1ea276caabdc6e4b0cb958fbae30858；1/6/6/1共14/14通过，实际102GPU秒，保留identity发布、不含cleanup补丁。每块清理后5进程/8线程/0zombie；独立审计和14行CSV已归档，f7补丁下既有11单元测试通过。不是历史EAGAIN根治或MLE收益。
- 联合诊断17547已闭合且独立核验：/research/d7/spc/yzyang4/resource-service-diag-20261011-v3，plan SHA3477f072efbd114bda046b9cb0a849b458f6fe9b8d7867773506cdff2fc2e41e；14/14 CPU内核、14/14本地medium请求，stop14，实际1078GPU秒。529快照UID线程峰561、NPROC1024、正cgroup失败计数观测0，结束3进程/3线程/0zombie；未复现EAGAIN。两服务GPU而非六GPU任务；不是完整agent负载/质量验收。模型别名qwen3.8-27b，实际qwen3_5 compressed-tensors INT4/group32。
- 保留v1调度预检失败（18CPU/2GPU须highcpucount）；v2/17545误用Slurm19不支持的--exact在服务前失败，0内核/0请求、实际10GPU秒。v3仅去该参数；本窗已闭合成本17541=132、17543=102、17545=10、17547=1078 GPU秒，所有失败保留。
- 条件八卡17550已闭合失败并独立核验：/research/d7/spc/yzyang4/resource-six-gpu-capacity-20261011-v1，plan SHAa2ae3c0ad57ecd7822f140e8c2adc7ab09fc21033500eb971da0c94983b77243。14计划/1尝试/0完成/13未开始；串行首程序6.5676928190514445秒报错，1/1请求成功，实际4120GPU秒；UID峰334、无资源报错标记、末3进程/3线程/0zombie。尚未进入六并发，不能称容量失败；完整门false，原件不动。原term_out漏存，不能事后断言精确异常。
- 定位入口漏建私有input_cache；原任务镜像零GPU复现FileExistsError，补空私有目录通过。不改源程序/镜像/输入/seed/450s预算，仅私有缓存及远端错误保存。独立17552已闭合2/2，150/588 CUDA步、公开query输出64/278640行，实际496GPU秒；独立资格审计gate=true。plan SHA09fb0ca0488bf29106f0aa71c8f5dbd970debce8d24c60a7ce51e9749d6aa0c6，root=/research/d7/spc/yzyang4/resource-cache-qualification-20261011-v1。不是六并发/新seed/质量确认。
- 17554已闭合并由其冻结原auditor独立核：root=/research/d7/spc/yzyang4/resource-six-gpu-capacity-20261011-v2，plan SHA024b608742e3934a8e716bd4c867243cf1f76be9c4439e25f19b9e54930f2120；14计划/1尝试/0完成/13未开始，1请求完成，首CNN固定450s超时（调用453.42841303208843s），尚未进入六并发；实际7720GPU秒，UID峰344，无资源报错类别，末3进程/3线程/0zombie。完整门false，不延时/换样本改原门。gpu-capacity-v2-failed-audit.json已保存；本地auditor新增诊断字段未用于此原审核。
- 生命周期17555已闭合：resource-persistent-hosts-20261011-v1，plan SHA8435e7595bc316fc4ee08b8e48a710adc5b5bcc5529dcad1bb88336f607d62cb；192计划/6尝试/5成功/186未开始，首轮第六内核120s readiness超时、无算术执行/资源错误，实际132GPU秒；6宿主首轮均回到3线程/5FD。不能推32轮无泄漏。独立persistent-hosts-v1-failed-audit.json保留。当前已闭合成本总额以sacct重新计算，不复用失败预算。
- 查重：bounded_readiness重复info查询已有17322/17326的47/48，不能当新修复；旧gateway观察器被Jupyter CLI exec替换、计数48份均缺失，旧--help已验证直接入口。新17556已闭合：resource-kernel-protocol-20261011-v1，plan SHAdab97495194cf57248451b24c806113456a91dd5d6d5ddb62fafd20c924183ac；48/48 CPU算术通过、48/48网关计数和实际forwarding均存在，UID线程峰255、结束5进程/8线程/0zombie，162GPU秒。原单次info查询、6宿主×8轮；观察器确实生效，但未复现缺失回复，不称因果修复/长期零泄漏。独立kernel-protocol-v1-audit.json已核远近SHA一致。
- 17557于08:33提交并已分配gpu1：resource-unet-six-capacity-20261011-v2，plan SHA0e41eb5b34d3918357b60999ddff2ac929a0498c7aedbd9b4034fefb76943ff1；单一合格UNet源14次原seed、1/1/6/6，两服务＋六执行GPU/32物理CPU、40min≤19200GPU秒，无API。原588步/450s/输出容差1e-5，独立核全部91输出对；刻意收窄负载，不能替换17554双家族失败/称六任务或真实agent质量。未提交v1因批处理外层4170/4140字段断言失败保留，0GPU；v2显式batch且实际入口预检通过。当前只称启动，真实完成看回执。
- 无GPU生产入口导入对照：同8逻辑CPU亲和，数学库线程帽3/未设/未设/3，实际线程7/25/25/7，均成功；网络/dotenv禁用、未实例化solver或运行任务。证据import-thread-profile.json；可解释不同宿主配置的线程余量，不是历史EAGAIN根因或速度收益。当前生产src/dojo未检出显式这些线程帽；外部launch/image环境仍未知。
- stage=/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU；无API，不改系统limit/他人进程/学长分支，原日志不落本地。额度耗尽后按用户授权已用一张现有重置卡，未购买；本窗不得重复消费。最新现场以本段为准，下方10/10为旧窗口。

## 当前窗口与真实现场
- 用户要求的会话内完整六小时已完成：10/10香港04:56:13–10:56:13。只读分支守护exec72234于UTC02:56:22.941自然退出，exit0；无新automation/thread/goal。
- 当前方向R14 MLE沙箱资源调度；本轮GPU工作全部闭合，不追加握手修复/补样本追正结果，不自动复用余款。机制/近邻/证据核验也已完成；后续新矩阵另行冻结。
- 最后队列观察香港10:54:33前仅旧Held12535；不动它。五个本窗job终态和资源账已再核。本窗没有遗留运行或排队的新作业。
- 本窗实际GPU秒：17364=216、17366=1796、17368=27612、17376=63、17380=170；合计29857=8.293611111111112GPUh，上限36900=10.25GPUh。含失败、启动、空闲、清理；API0，底座更新0。
- 我方证据及入口整理已快进push并ls-remote核bd8b1d8df2236b85ee191e272764307410d24b68（香港10:31:51）；守护最后报告学长仍24efc2e0a84ead449fb6dff71414d73693f70893，未改其分支。当前收尾仅更新本短交接，最终发布SHA看Git。
- alignment/GPU覆盖/阶段证据均已发布；18项相关本地CPU回归通过。香港10:42:59独立核7份关键产物远端/本地SHA：7/7存在、0不一致。bd8b发布门5文件/5blob凭据形状命中0、敏感文件名0；更早96e门14blob同样通过。不要重复writer。

## 本窗结果：先看这些，不重跑验收
- 所有本地证据位于phase1/sandbox_scheduling；下列目录的interpretation.json记录精确source/plan/审计hash和边界。
- 17364 / opportunity_recheck_v1_closed：17328两组Pizza原父子（正/平）各原seed重启2次，共8/8；正组两次+0.0197321215020330、平组0。另一已观测父程序更好，故不是全局改进、新seed/任务或调度因果。
- 17366 / neural_extension_v1_closed：同两任务家族新CNN32/UNet3变体，12/12；150/588步、六份/程序输出字节相同。pipeline/share2三比1.248439822872127、1.1602111699705704、1.4896379118094725；中位1.248439822872127，样本SD0.17052995413242686。
- 17366 CNN耗时339.686→168.940秒有强时序漂移，不能把全部加速归因共享。原seed重启不是跨训练seed。primary cfa91a7a48774fc10315423ab5547c6b3d65e60644fb4940647f387103094907；audit d40da2b8bf59f4d761faa046f15538a4743a50f0db5ce60dfa2f24291297fca4。
- 新phase-evidence-v1.json SHA d8102773357d1a34662ad573ba0f1876e1b2eda497433bc7bd42406e5ca4e473：12执行/60回执，三共享块UNet全执行早于CNN首optimizer 77.22765445709229/56.76279044151306/38.496912479400635秒；六块host optimizer envelope重叠0。4本地/远端合成测试与独立双精度核算通过。
- 这是阶段互补线索，不是GPU kernel没有重叠的证明：首optimizer晚于forward/backward，NVML稀疏；pipeline只并行初始化/串行整候选，不是完整phase-aware或first-CUDA准入强参照。
- 17368 / live_twochild_v1_closed：06:19:57–08:53:21，16尝试/15正常、index6模型请求超时，四全池槽结构闭合，27612GPU秒。同27B/两任务/每run1500s/2子、FIFO许可1/2、ABBA、四2300s槽；不与旧root5/600s作因果比较。
- 17368 primary 447ecf6e19aace0029a3d1a0564e7c7589fca869b1152cca71146be70834b00a：有效反馈池差-4/+5，仅3/8双方有效成绩配对且全负，primary/feedback门false。预冻结池最好四任务池对全覆盖不足、差null；不挑observed best救门。
- 两臂各记录4个Improve且两任务都有，不能仅解释为没进入改进阶段。仅两独立池配对，不把run当独立重复或推总体有害。
- endpoint_sensitivity_posthoc.json：全8分配对按可用性优先的秩比较，要求正常完成/允许失败run既有有效产物两定义均2胜5负1双方无有效端点；描述性，不换主门、不补分、不作8独立样本。
- 新return-alignment-v1.json SHA ac9fb76a349e03925a89b68eab9127d8eaaac28283803e512266e3b2b362d6f4：15条顺序全匹配；index9多出的唯一返回在1494.305789416656秒、外部无效、最后一条，随后仅开始一次生成且截止前未返回。80日志节点/81执行返回，不支持丢失好解解释。
- alignment使用冻结native extract_code后做全序列hash比较，不贪心吞重复；8本地/远端合成测试与PowerShell分母/hash核验通过。初次误以为summary含rows，写出前KeyError；改读独立精确pin的runs.json，原件/门不变。
- phase-analysis-v1.json是task-slot时间，不是GPU成本/可省时间；generation_returned在finally发出，包括失败/截止取消。未观察到的尾部不是idle。失败生成event数不等于失败run数。
- execution-gpu-coverage-v1.json SHA72e18bbbb786231a5157643a95826035697add72b5a6b745462d9b889159fdda：四执行块采样利用率0.007832619190892133/2.4975269503007285/0/0.05075266431498896%，监控时间轴覆盖均>99.9%（不是完整kernel观测覆盖），驻留clients峰值各1。3本地/远端测试、远近hash通过；只读旧遥测，无GPU调用。说明当前文本live未暴露持续GPU训练压力，不等于CPU瓶颈证明/可省GPU时，也不豁免原质量门。
- 17376 / neural_reverse_independent_v1_closed：09:00:06–09:01:09，63GPU秒；薄入口遗漏configure导出，warmup ImportError、正式0/12，保留失败，不是性能负结果。
- 17380 / neural_reverse_entry_repair_v1_closed：09:13:02–09:15:52，170GPU秒；入口修复/warmup通过，CNN候选前120秒内核就绪超时，UNet588步完成；12计划/2尝试/1完成/10未开始/0配对。首组门停批，不重投、不称反序确认。
- 17380 primary fbaa468783f3ba1565b28a999171814a77a4298c8dbaa7d94647ef1dbcaa1a38；audit b84191090c0818685e16ecb783a6781dcb39b835776008f2c1b4869a18200c52；8导出hash一致。原反序失败及更早未提交条件root均保留。

## 研究判断与不要重做的事
- 保留“固定小负载可重叠”的有限正信号；没有同预算live最终质量新收益，不能把工程验收写成方法突破。
- 当前不扩大两文本任务live配方/复杂LLM调度器。若下一轮继续，先分离时序漂移并检验廉价阶段准入强参照，不能只换名重跑；本条不是已冻结新矩阵。现有神经fixture仅作数值一致性，不能直接冒充新D_search质量基准；真实GPU搜索需合法独立开发适配，不只替换硬编码任务名。
- 新颖性边界已核SchedMate源码/历史及干扰撤销，MARS跨阶段AIMD/续轮优先，DetShare语义/资源耦合，Synergy CPU/内存敏感度，Agentic CPU-GPU Scheduling profile/交换重测。近邻细节在README/ROUTE。
- 本窗补核OpenMLE共享CPU/GPU沙箱、DSec生命周期/准入/暂停，宽“共享沙箱/阶段管理/无损并发”均不新。仅换成MLE不是科学增量。
- MARS preview只读核7e649f33f40ceb5d977ea4b7c07538effdad88d7：外层新session准入不同于我方执行许可；不可把租约排队当CPU饱和、机械缩宽后称完整MARS。原实现还需KV/内层后端，未安装运行。Synergy补读CPU/内存画像与租约接口，README留原文链接。
- 旧17128同两神经程序强参照12/12中位1.6617、17017大输入弱参照12/12中位1.6812；不同批次不拼成新确认。
- 旧17308并发宽度36计划/20完成、原门false；条件live2/4不启动。17322/17326握手诊断各47/48；observer被Jupyter CLI os.execvp替换丢失，根因未定位，不再投GPU诊断。
- 17328旧曝光单臂3/4正常，原资格false。17364只补其原seed局部重复性。旧12次空代码是不可解析响应，缺finish_reason不推断截断；不以修提取器另立方法。
- 学长10/9 SFT报告探索性：memory配置不同、缺失run/评分、同任务训练与多checkpoint选点；不是我方干净scaling或底座训练许可。

## 操作路径、证据保护
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；旧aira-dojo-codex-20260813有用户dirty，保留。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- 本窗stage=/research/d7/spc/yzyang4/scheduling-recheck-20261010.B5b9cz；五实验root均在/research/d7/spc/yzyang4，完整路径见各计划/源码，不从旧root盲重投。
- 兼容3090 gpu27/gpu28；gpu24 cuInit999未解决；不投projgpu39、不升级镜像/Torch、不静默退CPU。排除projgpu7/8/33、gpu36/38。
- first-960/Target-300/Target-522、D_val、官方test关闭；16560数值导出待独立授权。无付费API、无底座更新，不恢复HCE/多保真/Probe/TD/score-channel/K>=1。
- 安全：学长报告先用safe_senior_reader.py远端脱敏；曾漏camelCase URL令牌及Bearer替换顺序，已通知/修合成测试，绝不存值或用该令牌。凭据仅批准远端位置。
- 发布前扫描暂存及全部未发布历史、敏感文件名、证据Git/本地/远端字节；不force push，不改学长分支。Git hook曾有MSYS权限警告，不冒称hook验收通过，独立检查另做。
- SCP返回session时须等exit0。独立PowerShell核时间需显式double防Math.Max整数重载；属性集合Count先明确枚举，勿修改实验数据迎合校验器。
- 未跟踪phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md是用户13:01旧报告，保留、不stage，不主动另写长报告。
- 研究盘总4TB至2027-08-30，不是实时余量。长期技巧索引在旧checkout/phase1/memory/MEMORY.md，本次不覆盖其用户dirty。
