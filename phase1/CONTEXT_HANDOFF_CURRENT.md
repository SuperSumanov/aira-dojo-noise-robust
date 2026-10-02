# 当前短交接

## 当前裁决与真实现场

2026-10-02 20:43UTC（香港10月3日）；方向入口0L413。用户本窗口19:25:50—22:25:50UTC。15285/15286/15287均COMPLETED，9次真实任务程序执行，合计0.5427777777777778 GPU小时，API/生成器调用/底座更新0。没有新的GPU矩阵；不再加模型、prompt或seed填时间。

校准15285改善0.0006881858856195855，但3外层seed仅1份预测、条件CI跨0；NB15286三seed均负、中位-0.0016718851203692542；风格HGB15287三seed均负、中位-0.00034312114084361633。各独立评分/优化/哈希/隔离核验PASS。三个readout-v1已封口，勿重跑analyze。不是同预算agent收益或跨任务复现。

Spooky既有10轨迹凸组合事后机会界：只有3条多份独特预测，最大改善上界0.0004507913195095025、总体中位0，独立数值证书PASS。Pizza25轨迹两成员oracle有2条旧自动轨迹超过0.005，最近4条最大0.0001793829227457744；2条较小收益记录因5/1个比较舍入成平局导致实数oracle与浮点提交不同，numerics.json已解释并保留，不是全相等PASS。两成员结果不约束3+混合、条件路由或新候选。

全部16自动轨迹五折敏感性：中位0.0001495215311004851、8胜5负3平，最近4条中位0。候选生成已受同一开发标签影响，不能声称这是独立交叉验证。当前没有支持扩大组合路线或新agent方法收益的证据；也不能说任务整体饱和。

## 证据与发布

publication：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001
主dirty checkout：C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813
只更新主checkout方向/短交接，不bulk stage/reset，保留其他用户改动。

安全数据：publication/phase1/results/opportunity_checks_20261003/，六目录、31聚合文件及export-receipt；receipt SHA256 ab6b2a8d9afd056bae25179ee510f3a4f4dfdcac056cd168dfccc1a76338025f。13个本轮源码在publication/phase1/scripts。计划/源码/摘要/表哈希均在产物内；原始标签、预测、代码、模型回复不发布。
远端/research/d7/spc/yzyang4/下calibration-opportunity-20261003-v1、nb-ratio-opportunity-20261003-v1、style-opportunity-20261003-v1、convex-opportunity-20261003-v1、pairmix-opportunity-20261003-v1、pairmix-sensitivity-20261003-v1；opportunity-export-20261003-v1为安全导出。

20:40UTC fetch确认公开研究分支8ec74c5a4e7eaaa334a7f0f34dbfd220120e6a02，学长dojo-reproduce 1a4b06212727f45b6410a9d007803a0d0581219b，均无更新；本轮尚待白名单复核/commit/push，不修改学长分支。发布后的确切SHA以Git及本地补记为准。精确字节属性必须在stage前设置，不能放宽哈希来容忍CSV换行变化。

## 不重做与研究边界

0L412的15282（8运行、四配对差全0、新解0改善/3平/5退）和15283（2原版有效、2char超时、0完整对，收益null）已关闭；不重复。更早15272/15227/15267也已关闭。状态因子16条矩阵从未提交。rank_locality_guard、task_span_reference、uniform trajectory ensemble都已做过，不改名重提。

旧v6弱起点不是现成破局：仅两个初态可比的B-A、C-A主增量均负，其他初态缺失不能补0。普通agent曾改善只证明历史上存在机会，不能证明更丰富反馈有效。当前强父程序本身历史选优、所有新数字是复用开发集探索。

下一投入须同时有具体预算内改进机会、区别于近邻的机制、同工具强基线和新未触碰确认集；现在不启动新的GPU/API/model-fit。不要把ensemble（MLE-STAR）、结构化假说反馈/记忆（GOME）、压缩/一比特经验、能力×harness比较换名当创新。保留证据到有效修改这个问题，但无实证不宣布突破。
不训/RL更新agent底座；不读first960/Target300/522、D_val或官方test；旧critic/HCE/多保真/Probe/score-channel/K>=1路线不恢复。

## 操作

SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。MLE镜像用gpu28/gpu27，不用projgpu39或静默CPU。旧12535不释放。SSH内层引号会被剥离，用本地脚本+SCP且退出0再使用。凭据只在远端.env，日志/本地/Git不存值。
用户确认研究盘4TB、路径不变、授权至2027-08-30；不等于实时空闲。记录保持短，细节在Git和结果文件，不用日志工程取代研究。
