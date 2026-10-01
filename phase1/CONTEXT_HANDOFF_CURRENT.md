# 当前短交接

最后观察2026-10-01 19:01 UTC（香港10月2日03:01）。用户本轮要求六小时持续实验，目标至00:40 UTC/08:40香港；不以automation替代会话。研究盘续期已确认。15204于19:00:24提交、19:00:27 controller claim，19:01队列RUNNING/gpu28；服务在初始化，尚无实际续改。

## 当前新实验（勿重复提交）

方向顶部0L396/FEEDBACK_UPPER_BOUND_20261002.md。验证人工辅助可执行证据是否改善冻结27B续改，不是自动analyzer/E2E/终评，不扩旧长度分组C。Pizza/Tweet各1个旧A有效incumbent×3续改seed×A/B/C=18条；每条1200秒、最多4修改，5张gpu28 RTX3090（2服务+3执行），最多3h10，毛15.833333333333334GPUh。无paid API/critic fit/底座更新。仅D_search开发，保护cohort/D_val/test不读。

新root /research/d7/spc/yzyang4/task-feedback-upper-20261002-v1；plan SHA9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0。18 typed config、12实际SDK编码mock HTTP、三臂15动作CPU主循环PASS，无真实模型调用。prepare/cpu/transport/engine测试均已完成不可重做同输出；submit已完成，大文件hash通过，**job15204 SUBMITTED**。exec session96256已结束，不能再次提交。旧12535 JobHeldUser勿触碰。公开证据第二实现PASS：evidence-independent.json，证据SHA9f238ebcb5cb7ce7ec4384ec10f6c7d892d3338f3e198357b26328b22d9a0814。

只读状态：ssh linux5 /research/d7/spc/yzyang4/venvs/aira/bin/python -B /tmp/feedback_upper_status_20261002.py。已上传的新读出/独立核验在/tmp/task-feedback-stage-20261001/task_feedback_upper_{readout,verify}_20261002.py；读出输出须新路径，不覆盖。CPU检查/tmp/feedback_upper_cpu_20261002.py。新wrapper复用原v6 immutable runtime SHA4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad，只改新root/port19442/1200秒/新schedule/新facts模块。旧15140不可重投。

## 证据/公平与后续

A普通反思；B加定向事实；C逐字B事实加人工具体建议，额外人工建议本身是处理，不冒称同信息自主算法。事实绑定旧初始code，不能宣称每个新子程序仍有该缺陷。Pizza同record日期特征845→0，Tweet未使用sentiment/训练neutral全文Jaccard0.9757；只有公开train/无标签输入用于核验，不喂旧D_search复制分。Spooky备用词向量未触发，剔除假线索。证据/tmp/task-feedback-upper-evidence-20261002-v2/checks.json；v1凭据regex误中task-路径后停止，v2加边界，失败目录保留。

读出保留18分母、按task/seed配对自身初分增益+最终分；每任务仅一个代码origin，三seed不等于三新任务。全分配成本含idle/startup/failure，人工成本另列。固定不追有利seed、不增加建议、不按采用建议筛样本。先做源码/公开反例第二实现验证，再完整比较与决定是否止损；C若好B不好仅说明人工指导有用。

## 已完成旧实验

15140/18条/89返回动作/31有效提交全部独立复验，0L395完整表；旧批16最终有效，预定主收益仅两有效初态，B-A两负、C-B平负。Tweet局部C增益仍低于全文复制0.593357488208652。不能作为新正主张。总连旧失败14.308333333333334GPUh，全部关闭。

## 本地/Git

主checkout aira-dojo-codex-20260813 HEAD14188f8956d5becfc1f192455647d7c4aedd1f82有大量旧脏改，禁止整体stage/push/reset/rebase。新源码/协议优先在干净发布worktree C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，HEAD4af5723c7a98b25a75c7771695a19ac96f90935d；正常推HEAD:phase1-value-critic，不新branch，不改学长branch。新代码未push。主/公开方向历史不同，0L396分别插入，禁止整文件互盖。

本轮fetch学长到4ee7afd9970974f4bfae4b7a9d51591aca5c0b48（10月1日23:01香港）；三个改动文档先credential-shape零命中后读diff，只是policy数据/训练路径更新，不是已核新效果。不恢复底座训练。

相关研究上轮已查Gome2603.01692、MLE-STAR2506.15692、Malena最简harness2609.40303（9/30）；targeted reflection/genericanalyzer不新颖，只有可重复实际收益或不同机制才值得扩大。experiment-prompting技能已读；13项preflight已对照。长期经验在phase1/memory/MEMORY.md，动态以本文件和现场为准。
