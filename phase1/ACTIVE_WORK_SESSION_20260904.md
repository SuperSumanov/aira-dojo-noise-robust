# 2026-09-04 会话内实验推进

用户要求连续做实验，不再以八小时定时巡检代替科研推进。原 `outcome-blind` heartbeat 已暂停；当前
会话主动推进下列工作。不会承诺不受连接或会话中断影响的连续八小时执行。
起始检查：2026-09-03 16:26 UTC（香港9月4日00:26），G0 12288 PENDING/Resources；
调度器预计香港12:14:15开始，晚于本次八小时窗口，不能把排队称为训练。
语料306 archives、615 physical / 589 eligible runs、16010 endpoints、3733 structural pairs、47 tasks；
closure=false、config-v2=0。学长 b8d095180415957aa1bab31fa53ead1bba261c03 未更新。

## 工作一：真实历史训练输入接口（事前范围）

问题：固定 G0 tokenizer/序列化的真实训练输入，是否与独立编码和 canonical A/B 打包逐元素相同？
真实训练池是否允许现有严格一次遍历计划？这是工程与预算可行性验证，不是效果测量。

- 仅 exact G0 历史 train 4689 rows，train SHA `0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e`。
- 只解析已发布的旧 grouped Cards；只保留 train endpoints 的 code/task/run。不打开 dev/test 或任何前瞻
  vault。历史 train orientation 只用于新旧 collator 重排等价，不计算分数、学习特征或拟合模型。
- 固定 source `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`、Qwen3-1.7B-Base tokenizer snapshot
  `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`、16384 tokens、head_frac .25、task_cond=true、budget_cond=false。
  配置从实际 resolved_cli 哈希绑定读取，没有凭默认值推测。
- 先 credential-shape scan 再解析，输入和代码前后验 SHA，离线 tokenizer、不加载权重；单CPU线程、
  最长1200秒，独占 /tmp 产物。每250端点写结构进度，不输出代码、身份、标签或 gap。
- 所有 train endpoints 对照独立 serialization/head-tail；source collator 对照 canonical A/B 重新打包。
  新旧差异仅是已知行置换；不改源 G0、不改 frozen v2。
- 元数据检查两种有效pair batch=128的候选形状：2×8×8与4×8×4。这不是GPU训练批准。
  不整齐则报告余数，不补样、不丢样，也不据此修改正式预算契约。
- 预检14项本地测试通过，包括训练划分拒绝、重复端点/重复pair拒绝、截断边界、hash与凭据形状门。
  无学习seed、warmup或checkpoint选择；不把一次编码墙钟称吞吐提升。GPU/API/model-fit均0。

## 工作二：多进程 CPU 消费/恢复（执行前冻结矩阵）

在独立、小型合成 harness 中验证2/4 rank的实际消费、累积归一化与各rank RNG恢复。
不删现有单CPU Trainer适配器的保护、不冒充ZeRO3/bf16或大模型checkpoint验证；先固定矩阵和对照。
已经完成的单CPU27条轨迹不重复。工程验证结束后，正式收益仍需真实训练，不将玩具测试当正效果。

固定矩阵：world=2/4 × G_to_L/Ghash_to_L × {确定性完整4步、随机完整4步、前2步、全新进程组恢复后2步}。
只有seed6（测试随机性，不是效果seed），G/L各16个合成pairs；有效pair batch=8，分别2×2×2、4×1×2。
CPU float64、两个参数、AdamW LR=.02、四步linear调度是合成fixture，不是研究v2修订。只允许本机loopback
Gloo通信（不能说网络调用为0），每进程PyTorch计算线程设为1，另有通信线程。先做一项确定性pilot，成功产物可计入完整矩阵，
不重复运行它。完整矩阵≤20分钟；独占/tmp并保留全部小checkpoint，不安装依赖，不读数据/权重。

验证：每rank模型forward内重算输入hash；聚合真实消费回执核阶段和完整覆盖；全量梯度参考容差1e-12；
恢复前所有rank文件先验hash，再读自身生成的安全状态；前后model/optimizer/scheduler/各rank三类RNG
逐位一致。G/Ghash全部rank输入相同、真实global-label访问被禁；各rank最终模型状态一致但RNG应不同。
不宣称这验证Transformers Trainer/ZeRO3/bf16，也不宣称文件fsync就是断电恢复证明。

## 工作三：正方向执行与文献边界（进行中）

输入编码完成后的下一项只读诊断：旧global train 14206 rows（SHA d9163bbc…）能否在当前L-train
physical-run边界内提供额外、非重复pairs。只投影unordered endpoints与train标记，Cards只取id/run/task，
不读分数作筛选、不读任何dev/test文件。按missing-card、cross-task、outside-L-train-run、same-local-pair、
within-boundary五类互斥穷尽计数；另外报告唯一pairs与共享/新增endpoints。先凭据扫描与SHA、3项局部
测试，再运行并独立复核。这不创建G训练集，也不解除exact-config/experiment-closed来源门；重复和交集
不擅自修复或删除。预计单CPU不超过2分钟，GPU/API/model-fit为0。

主优先级仍为一个pivot、三个固定seed、五臂的global-to-local机制验证。G0只计价，15 fits仍需精确预算
与来源门。历史探索可准备，但不得把旧受污染test或首次960未闭合cohort包装为新确认。

下一项预算诊断：复用已验证4095个L训练端点的长度，仅编码上述假设性G子池带来的3640个新端点。
不再重跑已完成的L编码；新端点仍对照exact source与独立reference。固定诊断seed6/7/8，顺序为
`sha256(compact_json([seed,source,sorted_endpoint_0,sorted_endpoint_1]))`，只计算一次遍历与循环的pair/token
总数、完整pair前缀是否能达到同一token预算。该顺序不是已采用的训练sampler，也不创建新训练集。
如不可达只报告，不调seed或改token截断。单CPU线程≤1200秒、GPU/API/model-fit仍0，输出匿名cost记录供复验。

[AceNAS（ICML 2022）](https://arxiv.org/html/2108.03001v2)已经将弱监督预训练接到少量精确标签的排序
适配，并强调整体排序指标不等于选中好候选。因此一般“两阶段迁移”或“accuracy不等于搜索质量”不新。
本项目要验证的是固定MLE generator下真实global质量信息能否改善local sibling决策，排除代码暴露、
额外训练与局部过拟合，而不是照搬其weight-sharing或切回多保真。其成功也不是本项目的成功证据。

已知相关的[Pairwise Validator（2026-07预印本）](https://arxiv.org/html/2607.14408v1)用冻结LLM进行
parent-child接受判断，已在此前裁决讨论；不把重新读到它当新发现，不自动恢复已关闭validator方向。

## 本轮完成与下一处裁决

前三项与追加的真实预算诊断均完成并独立复核；具体数字、r1失败和r2修复在
`GLOBAL_LOCAL_BUDGET_CLARIFICATION_20260904.md`，机器回执在`results/active_execution_20260904/`。
L编码4095例、G新增编码3640例、587个L批次、2/4进程16条轨迹均完成，不要循环重跑。
原冻结v2未改，G0仍排队。当时下一处真实训练预算/LR/末批修改需要用户明确同意，不能以“八小时自主工作”
代替预算授权或继续制造合成通过数。此刻无新效果结论，也没有完成八小时科研执行的声称。

## 用户批准合理修订后的进展

用户随后批准合理口径改动，采用独立历史开发v1；原冻结v2字节不变，模型fit/GPU/API预算不扩大。
30份真实token计划和30份独立重放、6组跨臂关系通过；可变末批Gloo的16条轨迹/48更新/612forward与
新进程恢复通过；实际Accelerate的4条轨迹/16更新/204forward另通过。学长loss/forward AST桥接48个
损失梯度案例、8行pooling通过，并用错误方向负控证实适配不可省略。完整数字、SHA和限制见最新预算报告。
本地相关组合回归为213 passed、2 skipped；跳过项是既有显式opt-in autograd及本地缺Torch的模块，远端实际CPU验证单列。

失败保留：真实token输入r0缺稀疏模块而在读数据前退出；Accelerate r1把全rank完整性要求用到本rank子集，
移到all-gather后r2通过。两个工作负载成功后的外层Bash/CRLF退出解析失败不被抹掉，均以直接独立verifier rc0
确认产物。一次误用worktree默认uv环境安装251包后发现不是实际G0 runtime；本次生成的1,235,908,246字节
`.venv`经exact-path验证后删除，保留实际selective runtime、模型和源码；不把此失败称作环境验证成功。

18:29 UTC重新fetch：公开HEAD仍58a1bb137a835f42a6c6181ad50ba8015504e6b6，学长仍b8d095180415957aa1bab31fa53ead1bba261c03。
G0 12288仍PENDING/Resources，306归档和LATEST55aae315未变。摄取原PID1692885已在17:36:47 UTC正常完成145轮；
没有异常。v5事前绑定log SHA ca372710…/575024 bytes/8612 lines/16个完成标记，沿用同exact脚本续接；
新PID3884166、首轮rc0、旧日志精确前缀由独立verifier确认。聊天heartbeat保持暂停，不以监控替代会话工作。

当前科学结论仍是：尚无新的clean scaling或跨seed同预算收益。下一个效果结果必须来自已准备的严控真实fit，
不能用本轮工程通过数代替。G0只计价，不选择模型、不作为scaling证据、不重复提交。

## 实际Accelerate保存/恢复（执行前冻结，进行中）

在上述更新接口上追加真正的`Accelerator.save_state/load_state`验证，不重复手动Gloo保存方案。
固定world2/4×G/Ghash，合成seed6、两参数CPU float64、AdamW、dropout及三类RNG；G/L为176/209对，
有效batch128，更新大小128/48/128/81，固定peak1e-5及token-progress规则。每个world/arm执行完整4步、
前2步→新进程恢复、前3步→新进程恢复；完整轨迹也在2/3处保存，避免保存调用差异成为混杂。
新进程故意从9600+rank而非600+rank初始化，只有成功恢复才能通过逐组件比较。

直接审查exact Accelerate源码发现RNG恢复异常可能被捕获为日志；因此不能只用`load_state`不报错判成功。
先验全部rank文件哈希、固定plan/source/runtime/cursor，再读本实验自产checkpoint，加载后立刻核对model、
optimizer、Python/NumPy/Torch RNG逐位摘要。另一个不导入harness/adapter的只读验证器将直接解码框架文件。
仅使用本实验产生的安全状态，模型safetensors、其它文件weights_only；hash不是第三方pickle信任证明。

预检26项通过；单rank计算线程1、Gloo仅loopback、最长1200秒，不新建GPU/API/真实model-fit；所有小checkpoint
保留。最终比较不含尚未实证的ZeRO3/bf16、真实大模型、数据加载器游标或断电恢复。运行根
`/tmp/gl-accelerate-20260904-XmQYTa/resume-r1`；用独立Python启动器记录rc，避免既有跨shell退出码问题。

18:54:07 UTC结构复查：语料589/960、306 archives、LATEST55aae315、config-v2=0、closure=false均未变；
摄取3884166 live且最近poll4 rc0。学长b8d0951无新提交/outcome。G0在18:53:31 UTC仍PENDING/Resources。
旧Target522-rank FAILED_RC=1的时间为9月1日21:52:12 UTC，并非本轮新失败；保持停止，不读私有结果、不擅自恢复。

完成：工作负载与外层启动器均rc0，347.506484746933秒（不是吞吐基准）。20条轨迹、48更新、612次各rank
forward；独立解码36份框架checkpoint，8组/24rank完整状态和消费事件逐位一致。171份只含合成回执的
导出文件、3,317,919字节由独立receipt-only路径再验，summary SHA为`99601e0c…bc7b`。
NumPy1.26兼容命名空间是独立decoder初次失败的原因；原工作负载不变，完成后仅改decoder两行，再读原
checkpoint通过。source as-run SHA与修正后SHA均保留，测试可逐字重建旧版本。所有实际二进制状态仍在远端。
新增故障测试与逐轨迹预算账通过；完整相关回归243 passed/2既有skips。未产生或声称新的accuracy/scaling/search utility。
