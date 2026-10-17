# 当前短交接：现场、边界和恢复动作

最后核验2026-10-18香港02:04（UTC10/17 18:04）；本窗口原至HK03:30。
quota与R15均停止；19249完整闭合并独立复核，当前无本批GPU。不得把已停方案换名字继续补跑。
上一长交接/事前边界见Git b5126e6abbe9d992c14781f19aa4dac007334cd4；原实验件不重读覆盖。

## 位置与授权

- checkout C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，故意detached HEAD。
- 最近fetch：myfork/phase1-value-critic=b5126e6abbe9d992c14781f19aa4dac007334cd4；dojo-reproduce=e4d478350e704e8c5927eba566b2847aaa6dcbab，无新学长提交。当前闭合变更待安全扫描后push。
- 用户批准有限自主验证；没有无界重试、改门、旧余款复用的授权。不再为本窗口增加GPU修复批，不开新自动化/长报告。
- SSH yzyang4@linux5.cse.cuhk.edu.hk；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/quota-queue-source-20261017-ymOz45；远端批root=/research/d7/spc/yzyang4/rng-selection-20261018-v2。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；Node v22.14。本机无torch。

## R15：已跑完并停止

- 固定32次＝2既有DEV任务×2时间顺序选出的不同CUDA程序×2选解seed×global/sampler/addressed三臂=24，加4程序×2共同global部署seed=8。
- 同源码/镜像/300s/两物理CPU/独占GPU；v2同程序所有臂始终同物理卡和CPU。没有模型服务、API或agent底座训练。
- 19249 source7632bba196426ae1689e89a1d62671609d1d5296；planSHA9e1bf0caa8964e6baaf9ccd8be247f9ddc802bfd6be137f88fc535a494082756。
- gpu3四3090，HK01:06:28–01:58:34，COMPLETED0:0；allocation3126s×4=12504GPU秒=3.473333333333333GPUh，32完整/合格，清理true。
- 唯一冻结readout-20261018-v1已运行完成，不得重开覆盖；先封24行selection-sealed再读8部署。sealSHAcb3dfeca1180fbe90696813013b334bb116caf6d80e0ac2a76e75a0b146ecd16。
- 32 pristine DEV重评分一致。readerSHA968ad8d1aa2b87979c141e7fcfec66fb3562a8305259b6bfaa635727882229a4。
- 全三臂Aerial选program0、去噪选program3；新seed4103/4104对两参照增益全部0，原quality_gate=false。两参照也均选中本次两程序库观测最优；不是整个候选空间的上界。
- 去噪program3对program2的部署有向差分别+.0067386413852812445/+.006230520362543179；没有“排序已经错、等该方法挽救”的当前库证据。
- 事前次要诊断：每臂4次selection执行最佳去噪RMSE global .017415579264335714、sampler .01743975156706539、addressed .017758409998876772。Aerial对sampler逐seed一正一负。局部正号不救原门，不称独立holdout/完整搜索。
- 两seed Aerial相同完整epoch顺序global0/76、sampler36/77、addressed72/72，非独立样本；Denoise exact-input-multiset匹配0，不证明无部分重叠或已实现其跨程序对齐。
- input+epoch不隔离增强操作语义/fold/ensemble成员；顺序一致不等于增强一致，边际模型/墙钟工作量也可能变。不能把质量差解释为纯降噪。
- 直接近邻arXiv2603.11084已覆盖event-keyed RNG；MetaFlow也有workflow CRN，MaxUCB已区分mean与max。R15不是原创随机数方法；本试验既无选解收益，也不值得继续扩批。出处见ROUTE。
- 独立Node重算10传输SHA、完整32矩阵、封存选择、差值、阈值、实际成本；PowerShell独立复算12顺序结构行一致。不是第二次独立标签重评分或新任务复制。
- 本地证据phase1/sandbox_scheduling/rng_selection_19249_closed，含runs.csv/summary.json/independent.json；远端safe-export-20261018-v1仅白名单，不含原始源码、预测或标签。
- 当前没有已证实的新正结果，也未确认下一方法切口。不换样本/补seed/加新随机流再追正号；新方法先说明能改变哪个真实决策、可用提升空间及直接近邻，不恢复旧机制。

## 必须保留的失败与成本

- 19245 v1在首global块盲态取消：slot轮转使arm×GPU混杂；4started、0finished/训练回执，没有任何分数检查。allocation848GPU秒，含batch清理尾部保守856GPU秒；不伪报独立物理清理观察，不读取其分数或复用结果。
- 本窗口19245+19249保守总13360GPU秒=3.7111111111111112GPUh≤5GPUh。两批不重开，余款不用于救配方。
- quota19136：32启动/31完整，index26 readiness失败；实际借用0/11/9/0，33重评分+独立核验，原门false/incomplete；29676GPU秒、清理true，已停止。
- 18770 FIFO/18807 cap2/18997静态准入无稳定终分；19004未实际干预；所有旧批不补跑/改门，细节ROUTE。
- 旧calibration/ensemble仅已用DEV离线标签诊断，不是合法在线同信息收益；不拿旧局部正号给新失败解围。

## 安全与执行边界

- 已告知用户：读取学长1016报告时旧凭据扫描漏URL accessToken，链接曾进入工具输出；未访问/使用/转存令牌，建议学长撤销。不得复制链接值；今后扫描含URL query凭据，本轮导出器已补门。
- 不读first960/Target300/522、D_val/officialtest、16560；不使用付费API、不训练agent底座、不改学长分支或用户dirty。
- 兼容gpu1/3/27/28/29优先；不投projgpu39，不改镜像/Torch/退CPU，不绕他组/QOS，Held12535不碰。研究盘4TB至2027-08-30是授权非实时剩余。
- 原始源码/预测/标签仅远端；SCP退出0后才验证，发布显式清单+凭据/URL参数扫描+文件名守卫。
- 保留未跟踪用户报告、_codex_tmp、pooling_host_compat_20261016.sh；inspect_rng_candidates_20261018.py未发布且不必重跑。短入口≤100/140/80行。
