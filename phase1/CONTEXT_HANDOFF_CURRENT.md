# 当前短交接
更新：2026-10-10香港10:56窗口闭合。旧全文完整保留于Git 3c04f3049fc2004b1ff3ecbd1728ec49ce6b9916；方向/路线旧全文另存于Git96e129c8，本次只压缩状态索引，不改实验原件。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件；旧8月心跳与旧排队状态不作当前方向/许可。

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
