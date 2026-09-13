# 短交接：真实双分支八次搜索已提交
2026-09-13 03:17:40 UTC最后核提交；用户要求会话内工作三小时，开始02:58 UTC，目标05:58 UTC，不建automation。
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
本轮提交尚未push，最新公共仍6a0c2b3429e5533fc8ec4f9a21c511ec57522f83，需核后更新。

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
