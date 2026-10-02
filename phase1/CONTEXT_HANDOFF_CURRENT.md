# 当前短交接

## 最后现场与结论

2026-10-02 19:17UTC（香港10月3日）：本轮两个GPU作业都已COMPLETED、服务关闭。主试验15282不是排队/运行中。用户三小时窗口17:34:10—20:34:10UTC；不为填时间补同配方seed或新框架。

当前方向入口0L412：固定底座、同预算下公开错误样例能否改善自动候选生成。已完成8条=Pizza/Spooky各2运行seed×均匀/误差对照样例；全部配对差0，两任务中位和样本方差均0，扩大门false。16有效评分=8初态+8新解，新解0改善/3持平/5退步。29请求27生成，6拒收、7执行失败、6生成后无结果、2请求无生成返回，8/8耗尽900秒。独立评分/初态/哈希/提示历史核验PASS。小样本开发结果不证明普遍无效或等价。

远端 /research/d7/spc/yzyang4/public-example-feedback-20261003-v1
- plan 40e6bc3301c1db52fa09a794577c0b5dc95533302b0e460a044942a6485c5376
- summary 480017dbcb8745f4e55c66d67bc55734ee3881b811d855f7ca12a29d74df6918
- 独立verifier源码 b153b767ef83f7f3d49f180fe329fd1402b2ef3c95051a794ae2b18fe5b7f5ba
- 4187秒×4GPU=4.652222222222222GPU小时。不要再运行analyze；readout-v1已排他写入。

## 机制与限制

27动作先遮蔽小数分数审理由/AST，代表完整代码另读；非完全盲审且未穷尽所有程序语义。主要是常规TFIDF视图/调参/融合，没有证实具体文本错误属性变成新有效修正。读分后发现一Spooky理由将更高log-loss误称更强；任务说明确有指标名/公式，缺单独优化方向文字，评分器正确。不能据此解释所有失败或把提示修复当创新。

Pizza6新有效解：3改变排序、1精确预测副本、2数值差小于1e-12但排序完全相同。不要与旧15272的5改变/1副本混淆。历史48轨迹回顾另存：自动Pizza3条、Spooky1条曾改善自己的较弱起点；这不是新的方法收益或匹配headroom因果试验。当前Spooky强起点本身来自旧普通agent改进。

两seed/任务、历史开发选优起点、公用OOF、Spooky仅TFIDF诊断、提示长度不同限制均保留。人工15283与主试验首波同节点但不同GPU并行，共享I/O等可能干扰成本；读分前已记录，不能删首波。两臂共享的新900秒/6调用/模式解析不用于跨旧版单因子归因。

## 人工机会对照已关闭

15283 /research/d7/spc/yzyang4/char-branch-control-20261003-v1
仅给Pizza原代码TFIDF分支加analyzer="char"；两执行seed各原版/修改版、反转次序。
plan e989f2f0d3d585812fda44bca0b2b6de5124b2222d9c1b2554800f0a4d997269。
两原版有效AUC0.6867376225783306，两char触及300秒代码超时无submission，0完整评分对；收益/方差null，不是0也不是正对照通过。不增时救回。655秒×2GPU=0.3638888888888889GPU小时。本轮合计5.016111111111111GPU小时，原毛上限7.666666666666667，付费API0。

## 发布与恢复

publication worktree：
C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001
主dirty checkout：
C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813
不bulk stage/reset主checkout。新源码/安全表在publication的phase1/scripts和results/public_examples_20261003、results/char_branch_control_20261003。
19:17UTC fetch未报更新；发布前公开head93c9246970865d0fe48a85e2b564ad62ca837947，学长dojo-reproduce最后确认1a4b06212727f45b6410a9d007803a0d0581219b。本批尚待最终白名单审查/commit/push，真实新SHA以Git核实，不拿此旧状态当永久事实。不要改学长分支。
远端导出18文件扫描/哈希PASS，receipt49b586955c398ca12d90d831c00174b4078d6a685a5b99ac9a7d5dd257c49144。首次凭据拦截是task-feedback路径中sk-子串；远端只输出命中位置/类别确认后加词边界，未输出疑似密钥。
本地附加rank、headroom、机制、census不伪称远端18文件export的一部分。原始样例/标签/预测/模型回复/候选代码不上传。

## 下一步与禁止重做

停止扩大本配方；不救回失败、不改门、不加prompt variants追正。保留证据到有效修改这个研究问题，但下一项投入必须有具体的预算内改进机会、区别于近邻的机制以及同工具强基线；当前无已批准的新矩阵/新方法收益。
旧15272、15227、15267已关闭；原16条状态因子矩阵未提交且不自动提交。旧routing反证、AST拆分、缓存、普通局部编辑不要再包装新发现。
不训/RL更新agent底座，不读first960/Target300/522、D_val或官方test。旧critic训练、HCE、多保真、Probe、score-channel、K>=1 lookahead不恢复。
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。MLE镜像用gpu28/gpu27，不能projgpu39或静默CPU。旧12535不释放。SCP退出0再使用产物；密钥只在远端.env。
用户确认研究盘总配额4TB、原路径、授权至2027-08-30；这不是实时空闲空间。
