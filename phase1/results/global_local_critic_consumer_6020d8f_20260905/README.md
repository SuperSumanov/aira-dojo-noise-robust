# 主线训练接入：token-plan 到实际 Qwen critic 梯度路径

日期：2026-09-05。结果前代码：`6020d8f5c252bb16fa3e587de54f60629676c88c`。
范围是补0L45指出的真实模型消费缺口，不改G0、研究臂、冻结门或数据来源资格。

## 本轮实现

`global_local_critic_consumer.py`把已有token计划、实际tensor观测、原scalar reward forward和既有Accelerate更新适配器接起来：

- canonical A/B输入，带符号BT损失；hash-global不读取真实global方向。
- 保持每个阶段/循环的optimizer边界；使用既有全局真实pair均值权重，不把末批当满批。
- 学习率遵循既定token-progress协议，不额外创建scheduler。
- 实际tensor的编码摘要、mask、padding和token数在模型前核验。
- 只有优化器更新未跳过才提交游标；出现异常后本对象拒绝继续，须由外部完整恢复流程接手。
- 不读文件、不加载权重、不选checkpoint、不启动作业。计划仅在构造时核验/哈希，避免每microbatch重算整个语料摘要。

没有删掉原CPU Trainer或checkpoint的限制；这里也没有新增恢复授权。真实输入资格与训练预算仍由外部caller建立。

## 固定配置与独立参照

单元检查18项；模型级检查使用与G0相同版本的软件、两CPU进程/Gloo、seed6、随机初始化小型Qwen3，
4433参数、float32、无dropout，11条合成G pair与13条合成L pair，五个既定臂全部覆盖。
输入每pair为8个valid tokens，端点长度在2/6、3/5、4/4之间变化；batch为world2×每rank2×accum2，
覆盖不等rank末批、source/cycle切换和实际token总量。

固定原reward实现source=`5f3bc362db922c8edee2ef134656dfdb9a2b74fb`，抽取经过哈希绑定的类/函数，
不执行原训练入口或真实数据读取。独立参照通过原`pair_collate`构造winner-first整批，计算负logsigmoid，
与新canonical输入的每rank累计梯度比较；控制臂hash方向独立计算。

此处特意用SGD作为透明的梯度→参数参照，并非把生产优化器改成SGD。原G0的Adam/ZeRO3没有改变。
代码中预先固定梯度容差atol=3e-6、rtol=5e-5，参数atol=1e-7，结果后未调整。

## 结果与复跑

- 单元检查：`18 passed in 8.15s`。
- Linux A/B各38条rank-update检查全部通过；两次summary/cases逐字节相同，不计作独立统计样本。
- 最大绝对梯度差：`9.5367431640625e-07`。
- 最大绝对参数差：`1.8189894035458565e-12`。
- summary SHA：`5acc15a4c5717e7f03d7c70e32d4694d2c1773144014c6840866ba2343e68222`。
- cases SHA：`090010a203a6b838cff3e1f905714b570aa0645d536c7c393de481bce2f67178`。
- 全部导出文件credential-shape命中0；下载后的7个原始产物SHA与远端postflight逐项一致。
- G0 control/source仍分别为`90cd91058fd03e86185d42c14704845827259655`与
  `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`，tracked clean。没有修改运行中的训练代码/环境。

A/B均在linux5、关闭CUDA可见性及网络模型下载、每进程1 CPU线程、每次600秒上限下执行，未申请新GPU。
精确复现入口（在上述commit的代码根、已有绑定软件中，输出须是新的/tmp子目录）：

```bash
CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
CONSUMER_CODE_COMMIT=6020d8f5c252bb16fa3e587de54f60629676c88c \
timeout 600 /research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python \
  -m phase1.scripts.validate_global_local_critic_consumer_20260905 \
  --source-root /research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b \
  --output /tmp/NEW_UNIQUE_OUTPUT
```

## 失败记录与限制

首轮`3d8344f`的测试helper命名为`setup`，被pytest旧式hook误调用，18项均在setup阶段错误；
`03683fa`修正命名后，发现测试fixture仍调用只支持整批的legacy planner来构造accum3，18项在fixture阶段失败。
`6020d8f`改为先获取原合成pool，再由successor planner构造末批布局。两次修正仅改测试fixture，
consumer与模型级验证脚本未改，失败不算梯度对照失败。首轮完整输出保留于会话工具记录，第二轮远端
`/tmp/critic-consumer-03683fa-GWlWp4/tests.stdout`保留；未将两次失败隐藏为首次通过。

A/B日志含CPU与NFS Triton cache警告，均正常退出；本轮没有运行Triton/GPU kernel或宣称验证其缓存行为。

**这不是模型正效果、干净scaling、生产入口或15-fit就绪证明。** 还缺实际同源开发包、生产AdamW/ZeRO3/bf16接入、
完整保存/恢复及正式预算；38条是代码等价性检查，不是38个研究run。数据包的producer/experiment事实不能猜填。

## 同时进行的G0

2026-09-05 14:16:12香港只读核验：12499 RUNNING、已运行17分42秒，两个日志均有4/10进度；
实际`optimizer_step_1`计时回执存在，双卡最高已采样到100%利用率，未见失败标志或日志错误marker。
尚无checkpoint-10/verification/COMPLETE，继续由`g0-r5`按完整条件验收，不提前称成功。
