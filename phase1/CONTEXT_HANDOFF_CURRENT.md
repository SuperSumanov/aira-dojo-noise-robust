# 当前短交接
更新：2026-10-10香港08:00；旧全文保留于Git 8d1e8ca5。当前方向R14，历史动态不是现场。

## 当前六小时窗口与现场
- 07:59:34最后观察17368前两池2300s槽均闭合，第三池4worker仍运行、21执行返回/5评分回执；仅已知index6模型请求超时，未读新质量值。只读监控新增reverse-independent范围，source6dec662643ca016bdfa697a1b945ea37297662a7；neural_status.py SHA007c46328f3e82bd82319dd1c074a02883a0cbfca6809842d0cf420f37f9302f，测试SHA660f9695f226561c57a95fc42498a589dc0ab4594e62f4074e736fda0871ead1，本地/远端6项通过且字节一致；首个本地合成fixture因Windows默认Temp权限失败，改工作区临时目录后通过，未触实验代码。独立反序入口尚未prepare/submit；须等17368四槽结构闭合，prepare用255ed2eedd4718749e7198689a59bb570a953a73，不运行旧条件根。07:50 fetch核学长仍24efc2e0；07:25我方已安全快进push并核cfddbc857f81db4654960973777a57aa70fd177b（13文件，全未发布历史凭据形态/敏感名0，Git与本地字节一致），后续6dec尚未push。
- 07:08安全状态核第二池index6已failed/rc1、bounded TimeoutError发生在生成请求，cleanup_verified=true；其余同池仍运行，尚未读live分数。原controller在清理/FIFO安全下继续其余固定槽，不补样本，完整主门不能据未失败子集宣称通过。07:11另立独立神经反序入口（替代下方06:43未提交条件计划）：neural_reverse_independent_20261010.py@255ed2eedd4718749e7198689a59bb570a953a73、SHA6beb68e68f4a5f7f870e0f75252a800cdb59932070e004dc887e3939272ac756；本地/远端6合成测试通过、远近hash一致。新root scheduling-neural-reverse-independent-20261010-v1尚未prepare/提交；解除“无生成器的独立程序须live16全成功”这一无关关联，仍要求live四完整池槽的结构/身份/资源清理与primary闭合，不读取质量决定准入；原计划未执行记录保留，live失败不改。固定12/两程序/反序/150与588步/原seed/75min≤1.25GPUh及原效果门不变，全窗10.25GPUh/10:56:13时限不变。实际prepare用新入口与新source commit，PYTHONPATH仍stage:neural-extension根；不运行旧条件入口。
- 新窗口04:56:13–10:56:13香港，用户要求完整六小时会话内推进；不提前结束。17364/17366均COMPLETED，共2012GPU秒=0.5588888888888889GPUh。17368于06:19:57已RUNNING/gpu27/18CPU/3GPU；首块四worker和2300s全池槽已闭合、26返回/13评分回执。07:05最后观察第二块四worker已开始、5返回/4评分回执，未见基建错误，不提前读质量。曾考虑gpu35，但撤回前原作业已开跑，因此迁移/取消均未执行。旧Held12535不动。
- 闭合后阶段诊断live_twochild_stage_audit.py@b551a6cf186d5ca79414ad58bb59aa7649fa4ac3已在stage，SHA1cceab8ff22442ea904ddc8690ca3ab82713659a4a31fd10e78e69c5936dcfac；本地8/远端5合成测试通过、三依赖字节远近一致。远端首测缺live_root_exposure_audit依赖，补齐后通过，未跑真实writer；只在primary闭合后一次输出stage-coverage-v1.json，保留16/缺失，不输出代码或分数。Improve计数不是成绩提高，不改门。17366遥测全部max_resident_gpu_clients=1，仅候选执行重叠，不宣称训练kernel并行；原解释边界不变。
- 17364 opportunity_recheck：17328全部两组native接受Pizza父子（正/平），原seed各2次，共8执行；原源码/输入/评分器/240s单次不变，1GPU/6物理核/45min≤0.75GPUh。局部事后重复性，非新样本或调度效应；root scheduling-opportunity-recheck-20261010-v1，stage scheduling-recheck-20261010.B5b9cz。source4534112ad4de74f5d7d44da855366b38583d659f，plan e201f64f3ddbc8e753751b8e412ebb6df840f4ea5ebea6da1cc21016d4828feb；本地/远端各6测试通过且上传字节一致。
- 第二线17366：neural_extension_20261010，固定新CNN32增强版ea47bb6d与UNet3Residual c60e3f1c，沿用完整公开输入，pipeline/share2×3=12，1卡6CPU/90min≤1.5GPUh。两臂candidate450s不变，排队600s/worker1120s，整块预留1125s；首pipeline两程序不全完成则停，不换程序/改源码。依旧同两任务相关程序家族，不是新任务/训练seed或live质量证据。SETI公开输入缺失，未拿来充样本。
- 17364闭合readout b87dd1c85d15d9bba86ab5b47ecd60493dedfdabeda2798faa328caba5483fb8；8/8精确外部评分/预测hash/设备隔离通过。正组两次+0.0197321215020330、平组两次0，CSV独立Decimal复核一致；只支持同seed局部重复性，不排除dev样本选择、不等于池中全局更好（另一父程序分数更高）。opportunity_recheck_v1_closed，原writer不再运行。
- 17366于06:12:43闭合1796GPU秒，12/12；三比1.248439822872127/1.1602111699705704/1.4896379118094725，中位1.248439822872127/std0.17052995413242686；150/588步、每程序六输出字节一致，冻结门true。一次readout cfa91a7a48774fc10315423ab5547c6b3d65e60644fb4940647f387103094907/独立audit d40da2b8bf59f4d761faa046f15538a4743a50f0db5ce60dfa2f24291297fca4，勿重跑writer。neural_extension_v1_closed，远近7证据hash一致且PowerShell独立算数通过。CNN耗时沿轮次339.686→168.940s显著漂移；中间反序配对近同候选时间仍1.1602，但不能挑该组当独立确认。interpretation.json保留分解/混杂，不把全部25%称因果收益。
- 第三批新设计live_twochild_20261010：两臂同num_children2/1500s，FIFO许可1/2，ABBA四池×4run=16条，新seed175001起，四2300s等全池槽，3卡12+6物理核/160min≤8GPUh；保留全部16及缺失，不按分数续跑/换seed。仅借学长24efc2e0的分支宽度，不复现其SFT/9B/memory/24h，不能与旧root5/600s合并。旧冻结门不改、只检验本配置调度作用；源码/CPU预检前不提交。本窗三批上限0.75+1.5+8=10.25GPUh，API0/底座训练0。
- live twochild CPU/16配置/镜像权重预检全部完成，17366闭合后提交17368；source51b9daff161cb8e4b17ce729ca26cf1f7b5fdbe2，plan082645089d69e711f55057312d49e13d0fa99bf53942e91851791c12eb1525a6，root scheduling-live-twochild-20261010-v1。05:41提交前附prelaunch-prose-correction.json，纠正plan两处旧600s文字；实际numeric/config/运行deadline早已1500s，原plan/运行代码未改。四小预检回执已取回live_twochild_v1_preflight/且远近hash一致；仅预检，不当完成实验。
- 新监控stage/live_status.py --version twochild、neural_status.py --kind extension；helper40da62f449103047a5bc816cdc9ddb52125c0558，本地22/远端7纯CPU测试通过；不修改冻结root内代码。入口/CSV远近hash及Git blob字节核一致。
- 06:30只读旧17328提取形态诊断闭合：全部56节点顺序hash对应，12次空执行均在同一Spooky轨迹，最后保存响应各有一个语法不成立的代码块（unterminated），两种边界提取均0可解析块；不是纯thinking。未保存finish_reason，不据token数证明截断或其不存在；未修解析器、重执行或改变17368。source f22e14b1f21cf06debdd38860cf60cd7920cd51f，6本地/远端反例测试；response-shape-diagnosis-v1.json SHA7313d19a9cd347d6c9a2037aaf790a73f719f4a9dc46caeca247ac38ad154019，远近一致，只长度/类别/token统计，无原文。只能解释部分停滞，不称方法收益。
- 06:43新独立反序复验已冻结源码，未prepare/提交：neural_reverse_order_20261010.py@147cc4cbc98fda85db22b20d9fa782f410ed3c42，SHA8628c29c3fbf6a551db22f5abb2ed829a7b7b48ba6142680a9c46afc67229316。仍同两程序/输入/150与588步/源码seed，12执行三对，顺序从PS/SP/PS变SP/PS/SP；1GPU6物理核75min≤1.25GPUh，原判定门不变，不混称新任务确认。root将为scheduling-neural-reverse-order-20261010-v1。只在17368闭合readout显示16完整且structure通过后prepare（不依赖分数/go），提交与实际开跑须距10:56:13至少CAP+90s；核17364/17366/17368实际全成本+新4500s≤36900s。当前已闭合0.5588889+live上限8+新1.25=9.8088889≤10.25。本地8+相关26测试通过；远端首测漏PYTHONPATH依赖失败，补stage:neural-extension根路径后8通过，未动冻结批次。两新文件已在stage且hash一致，CPU准备须等当前live结束，禁止重I/O干扰。
- 05:46另在live提交前冻结pool-quality-secondary-plan.json：按任务比较每池两run的native最好成绩，四endpoint不全有效则配对差缺失；仅2独立池配对，4任务池差不作4独立重复。live_pool_quality.py@624573e688cb26386dd8d4bda1ec7b80b1d4a24a，SHA9f6945213779912299f18b1e13faa4ba11c16d6790bc7af92bd1a09b666fe944；本地/远端各5反例测试。原primary/资格/样本不变，分析等readout-v1闭合后执行一次；源文件在stage。
- Fetch我方8d1e8ca5f6345eaba12fa0771da2f815afe3dd2d；学长更新24efc2e0a84ead449fb6dff71414d73693f70893。10/9 policy SFT报告为探索性：memory配置不同、缺失run/评分、同任务训练及多checkpoint选点，不能作干净scaling确认；不实施我方底座训练。
- 安全事件：临时scan漏掉学长报告URL的camelCase访问令牌，工具曾显示该链接；不使用/再回显/入库，已提示建议撤销重发。旧safe_git_show合成测试另发现Authorization先替换Bearer会留下值；新safe_senior_reader.py已修顺序/URL编码/引号，2测试含9合成敏感形式通过。后续用新reader远端流式脱敏；不声称任意秘密都能检测。只记录类别，不存密钥。
- 本次14:11–20:11香港六小时窗口已完成；20:08:57只读复核17328四worker均闭合且清理通过，原56候选/23评分回执不变。20:05重新核本窗八作业最终账，无在跑批次；不新增跟进/作业或复用余额。
- 17328已COMPLETED，18:39:41–19:36:59，3×3438=10314GPU秒=2.865GPUh；4条开始、3正常预算结束、1模型请求TimeoutError失败。全部执行/服务GPU清理通过，无新GPU作业；旧Held12535不动。
- 本窗实际总计29281GPU秒=8.133611111111112GPUh，含v5/CPUprobe/v6/v7/17308/17322/17326/17328全部失败、启动和空闲；不含14:11前v4的3315GPU秒。
- 17328是单臂阶段资格，不是A/B：Pizza/Spooky各2seed174901–174904、原root5/share2/每run3000s；3张gpu27 RTX3090/18物理核/65min上限。提示预算也改50分钟，不能将前600s当v7反事实。
- root=/research/d7/spc/yzyang4/scheduling-live-exposure-20261009-v1；stage=/research/d7/spc/yzyang4/scheduling-exposure-20261009.RYQ2zq。
- runtime source=b3a5d0ee852f6013d3b1ca7f1ba1a44208f0163e；plan=b78c0101dec77c6c919a9f7669a07e4c6a5f377a20437e301c0fb8025ab047aa。不得重投/重开原root/重复writer。

## 本轮已核事实与边界
- 冻结primary一次写出：exposure-readout-v1 SHA632c411555e43b8459c7f91baa77621cad01210fe2da8fb0eba55af5fe90ade2，结构pass，但资格false：1/4失败、Spooky两条无Improve，另原raw-code匹配12未知。资格不改。
- 冻结辅助机会分析在写出前因native/external metric mismatch拒绝；不存在opportunity-readout-v1，原export_exposure_runs未运行。不是删掉失败换成功。
- 事后诊断修正分析假设：实际执行前native extract_code会格式化/滤除内容；用冻结原函数顺序匹配全部56/56。一条Spooky的12次实际为空代码。此前raw-code12未匹配不等于回执丢失。
- 23外部可评分中17被native接受，6个外部可评分且exit0但native标buggy；原源码保留LLM is_bug否决。不能直接说六个都应接受，也未改运行中逻辑。
- 6次Improve尝试，全在Pizza；3外部有效、仅2被native接受：seed174901一次相对父/所有此前外部最好均+0.0197321215020330；seed174903一次持平，随后该run模型请求超时。Spooky两条无Improve。
- native-opportunity-diagnosis-v1 SHA0733fb3b789e77f243a3bf64fe67ad5f43b8d3cf8b08de45ef2fe6d6a724844b；CSV b23366aa9b3e4770427746501f2a61772c06846707817f6e0427f7a06415d010。6本地/6远端反例测试、独立PowerShell计数/Decimal差值/远近SHA核验通过；不是独立重执行确认。
- selection-loss-diagnosis-v1 SHA9e7b1f6ca69f1568a3c775a1ce21797d1d5532aefeff201e8afb572271b777fb：四条所有外部最好−native最好均0。放行6个被拒结果不提供本批直接终分收益；减少debug耗时或改变后续搜索需新对照。
- 本地安全证据phase1/sandbox_scheduling/exposure_v1_closed；原候选/回复/预测/标签/权重均留远端。分析诊断与原冻结结果分文件，原失败不覆盖。
- 结论：存在一个真实开发局部改善，但没有跨任务、同预算调度终分新收益。暂不扩大复杂LLM调度器；先据这批事实判断负载/共同基线是否适合检验R14，不把增预算、改root或反馈放行命名为新方法。
- 19:51历史投入判断：保留固定程序阳性，但两文本任务原root5配方不足确认调度对Improve的收益；当时局部增益未重执行（已由上方17364补齐原seed重启，不是新seed确认）。相同起点续跑9/13及10/5已做过，只能算对照设计，不重命名创新。
- 19:29重读AIRA-dojo v2 §5/附录C/E：原主实验24h，策略弱收益限于AIDE算子，不能笼统说策略普遍无效；我方600s未完成root批不能解释原论文或学长生产。已写ROUTE_DECISIONS。

## 本窗口之前已闭合的批次，不重跑或救门
- v7/17279：15:30:54–16:59:15，15903GPU秒；16/16四块结构通过，FIFO1/2有效反馈两个池差0/+4，原feedback/quality门false；双方有效质量仅3/8（1赢2输）。全部16未完成首批5Draft，Improve0；Debug仍为反馈使用。live_v7_closed。
- 17308 width1/2/4：36计划24尝试20完成，另4候选前握手/屏障失败、12未开始，1325GPU秒；两观测2/4整批比1.5013821747034244/1.7927649723239687，完整门false。条件live2/4 f13dfb不启动，不用17328绕过。width_v1_closed。
- 17322/17326空kernel诊断：各48尝试47pass，串行各24/24、四并发各23/24，347/357GPU秒；不能判并发因果，握手根因未定。
- 17326全部gateway计数缺失；CLI os.execvp替换进程导致进程内observer丢失。CPU --help v2证实直接入口可保留observer，不是实际握手修复。gateway_v1_closed/interpretation-correction.json纠正旧摘要；17328未用此修改，不追加GPU诊断。
- v5/17262候选前因9物理核违背12核取消957GPU秒；CPU绑定17267通过36GPU秒；v6/17273入口ImportError失败42GPU秒。全部成本保留。
- 17128既有阳性：两固定神经程序强参照12/12；pipeline/share2三比1.2672909369785448/1.6617137953073626/1.6730949919847078，中位1.6617137953073626；150/640步、输出一致。独立审计已完成，不重复；不是跨seed/live质量确认。
- 17017大输入12/12中位serial/share2=1.6811874366439696但参照弱；16997四小程序36/36强参照中位1.3177936445362894。不能拼成新神经强参照。

## 同步与恢复
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本交接，旧aira-dojo-codex-20260813用户dirty保留。
- 10/10 06:23本窗首批40文件已快进push并ls-remote核80e86da805700a01ed2822a16de8d714e274ed3d；全未发布历史credential-shape/Bearer/URL命中0、敏感文件名0、最大67115字节，闭合证据Git/本地/远端一致。学长分支仍24efc2e0未改；后续形态诊断尚未push。
- 20:00–20:01已快进push并ls-remote核我方branch=e5d563bd7933481977a1b11d4d0d89d7e50176f9；26文件/22证据源码字节一致，完整未发布历史及文件credential-shape命中0、敏感文件名0、最大66417字节。学长分支未改；Git环境hook进程有系统警告，不声称hook验收通过，人工检查另行完成。
- 发布修复仅Git换行：三个CSV原始CRLF在窄路径-text后与远端SHA一致，数值无改动；详见exposure_v1_closed/publication-byte-audit.json。v7本地表对应远端readout-v1/runs.csv，非根目录控制器同名表；不是远端哈希漂移。所有原批次/失败/冻结门不变。
- 学长dojo-reproduce最后核a5519bc8e0c85d0a3bd78c478ac8332120d415d9，10/9 15:42 offline-GRPO/data docs；只读元数据、不并入。不得推断有新语料已入库。
- 未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md是13:01旧版本，保留，不误当本轮最新或擅自另写长报告。
- SSH偶发DNS/连接中断，不等于远端进程失败；先核PID/回执再行动，SCP session须等exit0再使用。当前监控入口stage/live_status.py --version exposure含安全退出状态。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。3090 gpu27/gpu28兼容，不投projgpu39，不改驱动/镜像或退CPU。
- first-960/Target-300/Target-522、D_val、官方test关闭；16560数值导出仍待独立授权。无付费API/底座更新/新critic训练。
- 原HCE/多保真/Probe/TD/score-channel/K≥1路线不恢复；SchedMate/MARS/DetShare等直接近邻边界见ROUTE，不能把普通并发、阶段调度、故障分类当新颖。
- 存储4TB至2027-08-30；凭据仅远端批准位置，不导出/打印。旧Held12535不动。
