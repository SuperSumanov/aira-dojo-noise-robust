# 短交接：双分支全八已独立闭合；参考条件后继准备中
2026-09-13 04:10 UTC更新：以下更早动态状态均仅历史。目标本会话05:58 UTC前实质推进，不建automation。
13201/13202全8终态，04:01:43 readout-finished status=verified；只执行了一次原冻结读出。
ROOT仍y_p2tlmi/source35321718...；本地results/forets_branching_s30_s31_20260913五主产物逐hash一致。
技术合格7/8、3质量配对：Leaf30平；Leaf31 critic .37782 vs random1.51485；Space31 critic.79655 vs random.80690。
Space30 critic.81839但random首内核故障，整对不合格；不可补0/补跑。新正信号不代表稳健收益。
实际1.3375GPUh；累计1140调用/结算3.558619389USD/责任4.958619389USD/两旧未知不变。
固定120/240/360/480/600曲线40行/9个不同原提交独立重评分完成，600严格与主结果相同。
Leaf31正结果360秒已交付；Space31 random由360秒.81839回落到终点.80690，不按外部最优重选。
机制/lineage为闭合后诊断；不得把部分批次里的程序加回原终点。
内核失败120 ingress/0 matched egress/3 foreign；32次login原镜像CPU纯连接均通过，未复现不等于治好。
04:08左右单次提交13204 gpu28单卡6CPU15分钟纯连接诊断，最多64内核，0API/0MLE；日志logs/forets_transport_13204.out。
新bounded同内核首次连接替换helper已7测试过，尚未投入生产：只在候选从未dispatch时、原120秒内最多一次重连，无重启/重试候选。
reference新32/33全8仍未build/activate/submit；先实际镜像故障注入、明确基础设施风险与共同修复后才决定。
本地HEAD96791864；公共最后核118c21e5339d8ffb9136d9a9e8d9c18b3f47adbb。下面旧排队/未揭盲叙述不得当现状。

## 历史运行配置（保留至本轮收尾再压缩）
2026-09-13 03:45:53 UTC最后核现场；用户要求会话内工作三小时，开始02:58 UTC，目标05:58 UTC，不建automation。
恢复先fetch→CURRENT_DIRECTION 0L189→核现场；不能按本文件旧动态状态重投。

## 当前唯一活动实验
13201 / 13202，分别seed30/31，每seed Leaf/Space×random/critic四条，共8条，两份gpu28单3090/6CPU/90分钟≤3GPUh。
ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi
STAGE /research/d7/spc/yzyang4/forets-branching-stage-20260913-mdP18vGW
source 35321718fef54f1907b469ab44334a30fe66b6cd；controller be59c7363d79710ae166a2530c03ef10854bf0ff。
prepared 56efc43be970f45b328e3ce29daceca31350d2966ce8929aa7f34f400a2e15e8；
AUTH ee05b65d5870a607144bed13bdcd474337cd5b46228552fdf36d0ca6df74c9a5。
readout-plan SHA1d0402365a080a3e4f7fec75d75cb62c6a1d5fa4bdd0cd85ef51b5dc0850fc67，7文件冻结。
本地release仅forets-branching-source-20260913-v3是投入版，tarSHAfa65c3abf9e9644274ec25b513c7931c9b1960822f605d95007e98909716bf47。
每run600秒、程序300秒；首步同RF真实执行计费；后续4生成/2执行、原UCT、Flash/Plus单票、原镜像，臂间仅选择规则不同。
独立多slot回放核候选顺序、debug归属、原代码哈希。保持仅完整迭代的incumbent契约，不把部分批次补成完整。
费用完整继承：985调用/责任4.562294681/结算3.162294681USD/两旧未知，然后又做4次新route；实际最新总账需只读核。
原用户100RMB下10USD责任帽不变。旧2o9mw39n和nehs1mj2账已封，禁止重新激活。
公共预留等待最多90秒，生成器和裁判均await，释放事件循环以让在途结算；仍守135秒准入，旧未知不释放，HTTP不重试。
11预留测试、4新真实transport测试（另4旧回归）、6多slot测试、实际batch/截止接线通过；这些不是效果。
kernel故障根因仍未明；新source只有被动网关消息种类/匹配计数，原就绪判据不放宽、不重试，不升级Torch。
实际gateway直接调用已安装kernel_gateway使hook生效；不得用无故障冒烟宣称治好。

## 未激活/废弃准备必须区分
thn8jswc/source8704...：未激活、0GPU/0API。
nehs1mj2/source061...：只4次route、0GPU/0搜索，因同步等待阻塞异步结算风险而废弃。
v3已修复并承接所有费用。原未调用的同名scope只在新账重建，旧封账及所有调用保留。
预检夹具曾没做生产格式化导致严格hash拒绝，已改用extract_code；旧真实30候选hash全部一致，verifier未放宽。
不修改在跑source/config，不重复route/submit/readout。

## 正在做与收尾
- 查两job及block-*.runtime/started.json→pool manifest状态，运行中不看成绩/候选选择。
- 全8终态后一次执行STAGE/readout_forets_branching_20260913.py ROOT；原初始/最终submission独立重评分。
- 完整逐run报告（含失败）、合格配对差/跨seed离散度与实际费用；不因单个好数换任务seed、缺失不填0。
- 并行推进成本强基线/机制分析，可用于后继但不混改本轮。
- 本地新结果目录phase1/results/forets_branching_s30_s31_20260913；发布前scan staged与tar，正常push myfork HEAD:phase1-value-critic。
03:45最后观察：两job都进行到第三run；首四终态，首00/04已确认是600秒截止而非内核启动失败。整组未揭盲。
当前账1063调用/结算3314546989/责任5414546989nanoUSD/3未决，其中可能包含实时在途，不能当作新未知已丢失。
最新公共36144e465ec2fc2de5db97c431ed1cb80ec805b8已ls-remote验证；学长分支仍113e25e7...。

## 未部署后继准备

已准备reference-context候选：新32/33×Leaf/Space×random/参考critic全8，仍600秒、原模型/镜像/execute2。
只给critic已执行parent/incumbent/最近两节点，代码+运行反馈+搜索可见validation；不带metric.info/隐藏grade/原始日志。
12本地测试通过，包含实际源码补丁及独立prior-reference回放；合成根可能有exec_time=0，必须明确排除，已加回归。
新STAGE /research/d7/spc/yzyang4/forets-reference-stage-20260913-m3U9toWD，只有准备脚本，未build/activate/API/GPU。
计划FORETS_REFERENCE_CONTEXT_PLAN_20260913.md；新builder需前组readout-finished与精确账快照facts，不得提前封旧账。
新reader在phase1/releases/forets-reference-tools-20260913，不能改变旧STAGE的冻结reader。
尚需生产CPU实际请求接线→冻结新reader/源→按前组全量结果决定是否投入；有故障则先解决，不能盲跑。
CEB强相关已核，参考提示是机制基线、不是算法novelty。新同预算收益尚未知。

## 已闭合旧结果（不可覆盖）
13190/13191 ROOT2o9mw39n：8初始+8最终原提交数值复核；6技术合格/3对。
Leaf28/29 random .36598/.39201 vscritic均1.51485，均不利；Space29 random.79310 vscritic.81034（+.01724），起点.79655，只有一个seed。
Space28 kernel/BudgetStopped两臂不合格，不纳入质量均值、不补跑。报告FORETS_COMMON_START_RESULTS_20260913.md。
旧cold-start random2/4 vscritic0/4保持；真实图单链已证，debug自动接树。
execute2是新机制条件，不是旧execute1因果消融、干净scaling或新方法胜利。

## 边界
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；原MLE镜像仅gpu27/gpu28兼容3090，不投projgpu39/升级/CPU回退。
Key只远端aira-dojo/.env OPENROUTER_API_KEY→PRIMARY_KEY，不复述/重索要。
本轮fetch学长myfork/dojo-reproduce仍113e25e7fa2570cb5f60401d051a1de3cce307c2；未改学长分支，本地模型权限仍待回复。
first960/Target300/Target522封闭；无agent底座FT/RL；不恢复HCE、多保真、Probe、score-channel、lookahead。旧held12535不动。
研究盘2026-09-29到期、续期未知。保留其他未跟踪目录/旧实验。长记录留报告，本短交接轻量覆盖。
