# Global→Local：历史开发口径采用与真实输入验证

状态：**历史开发口径和实现已批准；不修改冻结v2、不批准模型训练。**
用户“如果你认为合理的改动就批准吧”覆盖下列结果前口径裁决，不是新增GPU·h授权。
机器协议为`global_local_historical_development_protocol_v1.json`，SHA
`1964e8e48e998660584c045a7e8fe2a03d61a946ba266d29d74555f934482902`。
本轮没有新accuracy、scaling或search utility结果。

## 已从真实历史训练输入验证的事实

L-train为4689 pairs、4095个程序、430个已发布grouped Cards中的run身份、28 tasks。固定G0的Qwen tokenizer、16384 context、
task前缀与25% head/75% tail，在全部4095个程序上与独立编码参考一致；587个source collator批次与
canonical A/B的已知行置换一致。仅1个程序被截断。这只说明当前L训练池不存在普遍截断，不能外推到
所有语料或测试集，更不能证明长上下文已经提高准确率。

旧G-train共有14206 pairs。只做身份诊断后，2260对缺当前Cards身份映射、2032对不在L-train run边界、
522对与L为同一unordered pair；其余9392对覆盖428 runs、28 tasks、6698个程序，其中3640个不在L中。
互斥计数和共享/新增身份由独立set-based verifier重算。**没有创建G训练集，也没有把缺失身份自动补入。**
这是一批可能支持历史开发验证的数据基础，不是exact-config/experiment-closed确认资格。

另外3640个新程序的编码已完成，全部与source参考一致、无16384截断；复用之前的L长度，未重跑它。
假设使用上述G子池，G一次遍历为72676205有效tokens，L为32187742，总共104863947 tokens/14081 pairs。

## 旧预算表达在这批真实输入上不能直接执行

有效pair batch128下，L为36个完整step加81对；G为73个完整step加48对。切换2×8×8到4×8×4仍是128，
不能消除末批。保留所有pair、严格一次遍历与每步始终满128之间存在直接冲突。

事前固定的诊断SHA顺序（**不是正式sampler**）给出：

| seed | 同14081次pair消费的G-only tokens | L-only tokens | G→L tokens |
| --- | ---: | ---: | ---: |
| 6 | 108860000 | 96654679 | 104863947 |
| 7 | 108866083 | 96653504 | 104863947 |
| 8 | 109085847 | 96666318 | 104863947 |

G-only多3.8107%—4.0261%，L-only少7.8174%—7.8296%。因此相同pair次数/更新次数不是相同有效tokens。
六条诊断顺序的完整pair循环前缀均无法恰好达到104863947 tokens；这是这六条顺序的事实，不是所有
排列都不可能的定理，更没有证明某一种方法效果差。匿名成本文件由不导入producer的循环求和程序独立复验。

## 已采用的结果前修订（仅历史开发）

优先保持“同资源上限”这一研究问题，并把两个问题分开：

1. **质量信息对照**：G→L与Ghash→L必须全部输入、顺序、tokens、batch形状、更新、LR、保存点逐项相同。
   仅G阶段标签改变；这仍能严格识别真实global监督相对于端点一致hash负控的差异。
2. **预算下的部署对照**：Lbudget/Gbudget使用同一有效token上限，完整pair不得拆程序或改截断；在再读一对
   将越过上限时停止，实际差额显式报告。它们的更新次数允许不同，必须单列pair次数、有效tokens、padding、
   optimizer updates和实测GPU·h；不能再称“token、step和GPU计算量全部完全一致”。
3. **保留全部阶段数据**：G→L和L1末批按真实pair数归一化，不丢样、不复制真实程序补齐。采用最少可容纳
   microsteps后，将真实pair均衡分到所有rank×microstep槽；每槽至少1对、至多8对。v1不使用合成占位，
   余数小于world size则fail-closed。每个完整source cycle也结束一次更新，保证L1是Lbudget真实前缀。
4. **LR与局部过拟合对照**：建议所有臂采用同一token-progress调度规则，warmup占完整预算3%，之后保持
   G0已固定的peak LR=1e-5，不因臂或阶段重启。L1严格复用Lbudget第一遍的顺序、LR与优化器初始状态。
   这是相对于旧cosine的明确事前修订，不冒充配置未变；不得根据dev结果改回、调峰值或挑checkpoint。
5. **范围不扩张**：先作为单独登记的历史开发方案，保留原五臂、seed6/7/8及原成功/稳健性门。其已触碰的
   历史数据不能确认前瞻泛化；不使用first-960/Target300/522。原冻结v2不覆盖或改写。真实训练仍须G0
   实测计价、完整停止/存储方案和明确GPU·h授权；本请求不增发GPU/API预算。

若坚持同时严格匹配有效token和optimizer steps，则应保持现有拒绝门，另行设计预算分配协议；不能只改
报告措辞后把现有五臂直接开跑。也不能在看过效果后选择两种预算口径中更好看的一种。

## 较早完成的等长多进程工程验证

独立CPU/Gloo两参数模型实跑world2/4×两臂，16条执行轨迹、48次全局更新、288次各rank forward；
4组跨全新进程组恢复（共12个rank状态比较）逐位相同。确定性DDP与独立整批参考容差1e-12通过，G/Ghash
输入逐rank相同。独立saved-state verifier复核完成，缺rank文件/缺manifest rank/损坏字节均拒绝。
这不是HF Trainer/ZeRO3/bf16验证，也不是模型效果。旧单CPU保护没有移除；全部checkpoint留在远端/tmp。

本地组合156 passed、1个原有显式opt-in skip；额外远端11项访问/故障case通过。输入首轮曾误把运行库
`vaultgemma`源码判作数据vault，停止于import；只给固定包内只读Python源文件增加双路径包含检查的例外，
再运行r2通过。真实数据vault、dev/test、权重、写训练文件及网络拦截通过合成audit事件测试；没有打开那些
保护文件。保护是Python audit hook，不冒充操作系统级sandbox。

机器回执见 `results/active_execution_20260904/`。G0 12288在2026-09-03 16:55 UTC仍排队，589/960与学长
branch均未更新。当前8小时窗口内没有可靠的GPU开跑保证；不得用这些CPU通过替代效果收益。

## 批准后完成：真实token计划与可变末批

按既有`global-local-metadata-plan-v1` SHA顺序实现，未采用上表较早的简化诊断顺序。全量7735个端点逐项
双编码（1个截断），30份计划=world2/4×seed6/7/8×5臂，30份独立重放及6组跨臂关系通过。
G→L/Ghash→L均为14081 pair visits、104863947 tokens、111 updates；L1为4689 pairs、32187742 tokens、37 updates。

| seed | Lbudget pair visits | Lbudget token短缺 | Lbudget updates | Gbudget pair visits | Gbudget token短缺 | Gbudget updates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 15276 | 2720 | 121 | 13519 | 5367 | 107 |
| 7 | 15275 | 1937 | 121 | 13557 | 711 | 107 |
| 8 | 15273 | 2066 | 121 | 13517 | 593 | 107 |

两种world布局的上表pair/token/update值相同，padding成本另报；不能称GPU计算量完全相等。
原始摘要SHA=`c40f9b696530c2303c5129fa5571a2ffc484986472d1962871170d30a509043b`，见
`results/global_local_token_plan_20260904/`。工作负载rc0与外层CRLF退出失败分开记录，独立直接verifier rc0。

新增可变末批Gloo案例使用合成G=128+48、L=128+81。world2/4×两臂下16条轨迹、48次更新、612次forward；
4组新进程恢复共12个rank的model/optimizer/Python+NumPy+Torch RNG及消费事件逐位相同。
独立saved-state verifier和三项缺rank/缺manifest/损坏字节故障均通过，见`results/global_local_partial_ddp_20260904/`。

## 批准后完成：实际Accelerate与学长loss接口

固定Transformers5.12.1/Accelerate1.14.0/DeepSpeed0.19.3/Torch2.11.0源码SHA。标准Trainer的可变累积仅在
epoch尾生效；DeepSpeed有显式边界接口且Accelerate将sync_gradients传入。新增独立更新适配层，不修改默认Trainer。
非DeepSpeed路径抵消Accelerator.backward内置固定GAS除数，再按world×local_pairs/global_pairs归一化；
DeepSpeed路径显式传`scale_wrt_gas=false`，其真实GPU执行仍未验证。

实际Accelerate+CPU DDP另4条轨迹、16次更新、204次forward通过；各rank末批与独立全量更新参考在1e-12内一致，
G/Ghash输入/同步边界相同。JSON-only verifier验证原始manifest哈希、128/48/128/81更新数、真标签访问次数和权重。
结果SHA=`a16b7d3a7935d65a6fdb1de1a56c725f68941f6cbe0d15ec8b8a7c8e20fb7d4a`。
学长exact AST loss/forward在合成tensor上完成48个损失/梯度案例和8行pooling，未调用真实模型构造器；
未适配canonical方向的负控确实失败。详见`results/global_local_accelerate_20260904/`。

仍待：真实reward-model执行、ZeRO3/bf16完整状态恢复、global candidate exact-config/experiment-closed资格、
最终train/dev/frozen物化与零交集、G0实测成本及五臂精确GPU·h授权。工程通过不解除这些门。
