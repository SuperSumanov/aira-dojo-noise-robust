# 当前短交接 — 2026-09-19 23:55 UTC

## 当前任务、边界

用户21:15:49 UTC要求会话内推进三小时，里程碑09-20 00:15 UTC/08:15香港。不要新任务/自动化/代理，不例行写报告；正常push及合理实验已有授权。先fetch、方向顶部、此文件、现场；旧动态仅称最后观察。
first960/Target300/522仍封；不恢复HCE/多保真/Probe/score-channel/K>=1/G0/旧失败cheap选择器，不微调agent底座。不改学长分支、共享source、冻结root。原始代码/回答/日志仅远端私有，密钥不回显/下载/Git。条件单batch不是完整E2E，初始候选生成不是免费。

## 活跃14167：原入选batch只改执行次序

ROOT=BASE/comparison-native-batch-order-20260919-hz3c589n；deployment dc4a7dbc6951f5bd8d24b49ca7eb2e2de3d5ccec；prepared25d55a42517e586b677dd72a7296a4453c0c68bfda03c551eeb30570e8274428。gpu28六卡24CPU100min≤10GPUh，0API/fit。23:34:38最后观察RUNNING、第二wave23:32:01开始，预计00:07 UTC闭合。新值未读。
Pizza原seed1/2、同失败prefix/原第二入选程序/first debug cycle，只换repair→second / second→repair。两阶段均做，不因首成功停止；共同35min、有限内部metric最大为实际最终提交、平分保首个。debug到首次原生有效/20步/时限/完整回答限制；无额外max_tokens、无重试/截断抢救。第二seed交换lane。
四episode及allocation闭合后仅用BASE/comparison-roundtrip-reader-20260919-Ral9kyiB/readout_comparison_native_batch_order_20260919.py --reader-commit 530d5739960b29fae03fccd5f1c4740ee6719c8c。shared SHA c9a83c66e02c104193a81570f4c38726c9db973a65a13529c3f129dbbba16c76；wrapper d083528f31078b41854aa90475b92edce225a56936120482392873a24a276a03。不用旧Pt3BsrGK/ee3c6da。CSV独立AUC必须round_trip；闭合后再独立verify_comparison_online_results_20260919.py。status_comparison_native_batch_20260919.py只查结构。

## 已闭合14170：冻结8B对完整30候选评分，禁止重读

ROOT=BASE/comparison-frozen-reward-20260919-ac_f34fz；deployment7d5c31c706c4bb18faeda18a27243ff7be539c93；prepareda16acaa7b96946f90d1a171a7accf16a3e0c170c08f1df7545f7d9f958ba2362。COMPLETED199秒/1GPU6CPUgpu28，含失败16秒总.059722222222222225GPUh，0API/fit。全30闭合，独立本地标签/组合/宏与任务平均核验PASS。
固定Leaf1/2/3及Spooky1/2五池全部30原候选；既有checkpoint-100、16384ctx/.25 head/task_cond/bf16/batch1，完整执行代码仅encoder截断，torchseed20260919。不训练/挑模型/候选；uniform2-of6、top2、top3-uniform2、slot平分均在新预测前固定。既有开发outcome已见，非新测试或历史rank复原；oracle-best不是部署最终选择。
14168（ROOT ...72slmwzt）FAILED12秒0模型0预测，14169（...zobjollo）FAILED4秒0模型0预测，原root/log保留。真实根因是我方新入口误用了aira环境Torch2.12.1+cpu；补exclusive srun并未解决。23:37已只读确认原GPU critic用exp环境Torch2.11.0+cu128/CUDA12.8，与旧campaign一致；最终修正使用该已有环境，无安装/镜像变动。不得称模型效果失败。
未提交 ..._yu28miq 误用占位SHA，仅CPU、禁投；新代码拒绝全零commit。readout已在新值前固定为14170，唯一reader02d0b5d4a4c75c700934f83c92ff4dd9585e2947已执行，不重跑；summarya1f7f22787e306512f715948d9abc25cbd499d8370880d4f0e286b35c63a68d9，runs407006f509471d0b91b0dc4214d2874f15c3fc3ee48ae8a5b15f06ade86601f8。本地results/comparison_frozen_reward_20260919含prepared/summary/runs/independent-check。
预定top2在Leaf三池均保留最好.06983/.12444/.11709，各对15均匀组合10胜5平0负；Spooky seed1两条均失败/0胜3平12负，seed2整池失败。五池等权有效概率top2 .6 vsuniform .6266666666666667；质量净偏好.24仍是oracle诊断、非跨任务E2E/scaling。不要藏负任务或按结果改筛选。具体预定敏感性见CURRENT_DIRECTION 0L226。

## 已验证窄正例14165（勿重跑）

ROOT BASE/comparison-pizza-full-deadline-20260919-yaywhbo1；deployment a37e3595a62989746c5ffb96943bbfea8ec65e96；prepareda153be4e55a98da9e07fb75f60cee4d320da5aa91b551ce7b65bbf7967ef4ee3。COMPLETED4813秒六卡=8.021666666666667GPUh。两pair1胜1平，seed2预先随机缓存49.211306715995306s原生接受/AUC .66883，baseline35min无有效；seed1两臂失败；sign p1/0unknown。来自缓存本身，不是后来debug，不代表总体/完整E2E/critic改善。
原e7d969 reader因独立默认CSV精度失败，原claim/grades保留。官方round_trip与默认概率差1.1102230246251565e-16，正确AUC .6688342527307931、默认 .6688362823057595。不改提交、官方分数或容差。独立ROOT/readout-roundtrip-v1、reader530d573在22:54唯一补充完成；summaryb9630d42453652391bc68544afad350ad40da636215a6ad7c7dea6651c080725，runs e7e94cd8a8be2e7ad0f197b19d0741aa531d5ca6b0f5beedd042f658eb9ec340。本地results/comparison_pizza_online_20260919含独立PASS/精度诊断，已push。禁止再跑主/补充reader。

## 已完成不要重做

14146 Spooky32k：ROOT comparison-online-continuation-20260919-qpw9ys94，COMPLETED3008秒六卡5.013333333333334GPUh；summarya958946c49bca5248c0ca7e647c71b22a493231657ee18f73ffd219ecb5c196e。1胜1平/sign p1；两个cache均失败，唯一成功来自后来随机debug，三轨迹32k截断，不能归因缓存。reader/mechanism全闭合。
14166原第二候选：ROOT comparison-pizza-selected-second-20260919-u2nkqs5y，88秒2GPU/.04888888888888889GPUh，summary19668b47b51cbcec7c99af1ea9d16e7d8559ad02274b28c5c65ef74bb9da0d0f；seed1 AUC .74184、seed2失败，未native分析，不是策略收益。
14149原Pizza前缀、14135/14115/14128银行、14127/14133debug、14134截断、14136分析、Leaf3/Spooky2完整池及reader均闭合，不重复GPU/读出/G0。旧Pizza32k root ...1qiyjkqy及CPU失败batch ...8pdj0u_r从未投GPU，禁投。
25池20调试阻塞、严格延迟有效兄弟机会0；次级7组便宜ready候选质量3胜4负。保留零结果，不用首成功替代最终质量。

## 并行CPU资产、学长更新

真实b7f8 source默认native的ready_first开关/SQLite ledger/两臂共同逐动作incumbent已准备：ROOT BASE/forets-ready-source-20260919-qkdl5y2i；builder26e121e31278fcb1d868e8394a60651c79e266f4；preparedd0f5d57f6785d35396942d38b577be751e78bb203de925f921ea72b90a3b03e5。249源文件仅改5，真实CPU导入PASS，0GPU/API/model；186相关CPU测试实际通过。不是可启动E2E。
**旧source的critic_topk_random实际走contextual_rank旧付费Qwen路由，不是8B！禁止直接把旧source当E2E提交。** 新隔离本地reward版已在23:53:44 CPU真实导入通过：BASE/forets-local-reward-source-20260919-81zz0r0j，builder5f9b05a98264a1c9c369cf5d397f6c79fefb2b75、prepared21b414b58cb781cf8d5ddbb80a29a7a6b74416eba0b8f082f6e701b834328773，250文件/6变动（含新增local_reward）。只本地127.0.0.1、无重试/代理/旧paid回退、完整代码、共同remaining-time门；原策略和slot选择不改。未GPU部署，完整E2E仍需共同worker/固定预算/模型服务绑定，不能把source builder当实验。be933旧patch只是原型。
205本轮明确模块CPU回归通过；宽泛discover额外导入旧critics/mock包因相对导入报错，未改旧包，后用明确模块列表重跑。新transport首测仅字符串引号假设失败，改AST检查默认native后通过；没有因此启动GPU。
23:00:27同gdown双列表正控制PASS：0912五可见/listing c02e5001cbfbddd4e096d1d6921a78132cc22b1b971222c6375912b51312cdec；0918零可见/d36f39e6e9476279df19da46f006f182236737f29e64e5808e93733d676ae239，不等于没上传。22:59学长head仍e4181fac5edb319e14d4d819088778d5d2708912。
AGR-V动态生成/验证、Recovering Wasted Compute回溯兄弟及固定draft消融、AI Research Preference Models critic/E2E均强相关；缓存/排序本身非新颖，尚未证明独特普适的方法主张。

## 环境、发布

本地C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；SSH linux5；BASE=/research/d7/spc/yzyang4。编排Python venvs/aira/bin/python（CPU），**critic GPU必须venvs/exp/bin/python**。SLURM_CONF=/opt1/slurm/gpu-slurm.conf；4jobs/8GPU；旧held12535不动。MLE原镜像gpu28 RTX3090，禁projgpu39/改Torch/CPUfallback。
ASSETS BASE/local-qwen27b-20260914-zcx1k1dy；revisiondc430725f831dd90d9271738b877879a46a82239，18文件36808331288bytes不重下载。DONOR BASE/forets-fresh-integration-20260914-ih6u0mpw。8B BASE/forets-critic-incoming-20260908-3lcjjcwq；loader BASE/forets-e2e-dev-20260908-IMuJx6/critic-offline-v1/src/mle_critic/src/evaluation。盘1TB至09-29、延期未知，无需清理。
0912五包BASE/comparison-quarantine-20260919-_tda9fh6，703326526bytes；仅新Qwen46config/43journal、保护集隔离已核。
只正常push myfork HEAD:phase1-value-critic；22:58已验证公开173c9fd8caa8e15c1c87b0b2cf2468ba379e42c5，后续待推。全部待推blob凭据/敏感文件名扫描只报数量，JSON/CSV -text，无关untracked保留。数字标题只复制打印结果。
