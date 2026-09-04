# DeepSpeed更新完成核验：生产接入修复的预检

范围：只修未来Global→Local适配器的完成状态；不改排队G0源5f3bc36、运行环境、冻结协议、训练数据或预算。
旧适配器在DeepSpeed分支恒报optimizer_step_skipped=false。已固定DeepSpeed0.19.3的_take_model_step
在overflow时仍增加global_steps，所以仅看步号不足以证明参数更新。此前CPU/DDP与loss bridge没有执行此分支，
既有CPU结果不受影响；这不是已观测到G0或任何真实训练发生了跳步。

## 本轮动作

1. 已读3份已固定SHA运行库中的相关方法，credential-first，未导入运行库或模型。
2. 新begin/finish接入检查绑定engine/optimizer实例、步前快照、三个跳步信号和engine applied标志。
   每次只接受一个attempt，skip则不可提交训练cursor；缺信号/漏步/双步/重复finish失败即停。
3. DeepSpeed负责clip和step，因此begin检查实际clip契约且禁止第二个LR scheduler；不能再默默忽略配置。
4. 用固定源码的实际Wrapper.backward、Engine.step和_take_model_step方法体驱动假后端。
   模拟正常与overflow两条路径；后端不计算梯度、不更新张量、不加载模型，不称ZeRO3/GPU实测。
5. 固定世界数2/4，微批次数从既有布局产生，全更新128、旧G余量48、新G-reuse余量114、L余量81。
   选择仅复现控制流，不读真实训练记录。每种形状/余量运行正常和skip，无网格调参。
6. 旧9e9ba2d源码作为负控，必须检出它把skip报成未skip；另注入漏执行、重复执行、信号不一致。

## 边界与通过条件

代码exact commit先于远端正式检查。标准库CPU、A/B两个进程，每进程最多120秒；零GPU/API/模型拟合。
单元检查覆盖新增失败路径，必要回归仅检查被修改adapter；不重跑旧四轨迹训练/48个loss bridge样例。
真实DS方法通过AST白名单提取；文件hash/凭据扫描先行，拒绝非白名单source/data open。
真实方法中的GPU/计时/监控/优化数值后端由明确stub替代，因此只能证明源代码控制流和完成账的互通。
比较前后输入/源码hash，双运行逐字节一致，旧冻结v2/历史开发v1未动；CSV记录完整命令、rc、seed和CPU范围。
测试所用合成seed=6，只为固定输入，不用来声称跨seed效果。

若有不匹配，修根因并保留失败收据；不得将stub成功写成真实训练准备完成。正式接入还需要
实际ZeRO3/bf16/模型保存恢复与有权威来源的数据，并另获GPU预算。不会自动重试或扩张G0。
