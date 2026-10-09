# 当前短交接
更新：2026-10-09香港19:51；旧全文保留于Git e5e8bef4。当前方向R14，历史动态不是现场。

## 当前六小时窗口与现场
- 用户14:11授权在会话内推进至约20:11香港；此刻尚未完成整窗，不提前宣称六小时结束。
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
- 最新核远端自己branch为06aa7c328c0fa8b25988a42d09cbe602b88c1b71（18:46安全快进push）；本地e5e8bef4及后续本轮闭合待最终扫描/commit/push。未修改学长分支。
- 学长dojo-reproduce最后核a5519bc8e0c85d0a3bd78c478ac8332120d415d9，10/9 15:42 offline-GRPO/data docs；只读元数据、不并入。不得推断有新语料已入库。
- 未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md是13:01旧版本，保留，不误当本轮最新或擅自另写长报告。
- SSH偶发DNS/连接中断，不等于远端进程失败；先核PID/回执再行动，SCP session须等exit0再使用。当前监控入口stage/live_status.py --version exposure含安全退出状态。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。3090 gpu27/gpu28兼容，不投projgpu39，不改驱动/镜像或退CPU。
- first-960/Target-300/Target-522、D_val、官方test关闭；16560数值导出仍待独立授权。无付费API/底座更新/新critic训练。
- 原HCE/多保真/Probe/TD/score-channel/K≥1路线不恢复；SchedMate/MARS/DetShare等直接近邻边界见ROUTE，不能把普通并发、阶段调度、故障分类当新颖。
- 存储4TB至2027-08-30；凭据仅远端批准位置，不导出/打印。旧Held12535不动。
