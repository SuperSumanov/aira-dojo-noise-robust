# 9月5日：修复未来训练适配器的DeepSpeed假完成风险

## 已做成的事

等待G0期间，发现并修复了一个与同预算实验直接相关的生产接入问题：旧适配器的DeepSpeed分支
无条件返回optimizer_step_skipped=false。固定运行库的_take_model_step即使遇到overflow，仍增加
global_steps；因此“步号前进”不等于“优化器实际接受了更新”。这是尚未接入的适配器缺口，
没有证据表明排队G0或此前真实训练发生过此错误，也不以它解释旧scaling结果。

新接口在每次计划更新之前捕获状态，之后交叉检查engine/optimizer身份、尝试步数、跳步计数、
三处skip信号和_step_applied。正常更新才允许提交数据消费cursor；跳步明确返回不可提交，
漏步/双步/重复完成、信号缺失或矛盾则立即失败。另核对实际clip参数，拒绝第二个LR scheduler。
不会自动补样、重试跳步或继续计入已完成训练预算。

三处skip接口最终来自同一个底层overflow状态，不是三份独立统计证据；交叉检查用于发现接口错绑或状态不一致。

## 证据与范围

- 本地及Linux相关单元/回归检查均18项通过。
- 固定库源码的Wrapper.backward、Engine.step、_take_model_step和两处skip getter真实方法体，
  用AST提取后接入**非数值假后端**；未导入Torch/Accelerate/DeepSpeed包，未初始化真实engine。
- 48个控制流用例：2/4-rank逻辑布局、128/48/114/81全局pair计数、所有rank、正常/overflow两种分支。
  24个模拟overflow用例全部复现旧适配器假成功，新接口全部正确区分；另3类故障注入均被拦截。
- 114是新G-reuse余量，81是L余量；不是只检查旧48余量。每rank末批配额经不导入生产器的独立算术复验。
- 原运行库global_samples在末批仍按名义128增长，所以实际pair预算继续使用冻结消费回执，不能改读引擎计数。
- A/B字节相同，rc0/无stderr；耗时0.7529901685193181、0.5782220726832747秒。
- exact code：d6b569e9ee5b77e40565f5c86db47650e6011ab4；archive SHA
  3240421e02eb1da5b0f996a94cc9bac7a81fca9b60576a8da2f7a801bc63f585。
- 主回执SHA：6a2e8c835b1dc65ee7a4c079218a03de11ea462d0e018ce9bb9eb663412f056b。
- r1/r2共9个manifest文件及14项版本化源码blob绑定核验；冻结v2/历史开发v1保持原SHA。

这证明指定源码路径的**更新状态控制流**互通，不证明真实ZeRO3通信、混合精度数值、模型训练或checkpoint恢复。
假后端的applied_calls是模拟计数，不是模型参数差异实测。48个用例不是48个独立科研run，也不是跨seed收益。
已有CPU训练/保存恢复证明仍绑定其旧源码；本次改动不能让旧checkpoint回执自动适用于新版本。

## 接入方式与剩余门

未来获准的正式consumer应当：runtime_binding → 来源/split/预算检查 → 设置本步LR →
begin_deepspeed_update → 原planned microbatch forward/backward → finish_non_deepspeed_update传入
deepspeed_before → 若跳步则终止、保留已花费预算与失败证据 → 仅成功才提交cursor/checkpoint。
新begin/finish没有模型加载、数据读取、优化器step或作业提交入口；不会替调用方批准训练。
GPU数值与实际保存恢复仍要另外验证，不复用合成通过数代替；不改排队G0源/参数或启动新作业。

## 失败记录

r1 exact 94976ec：18项单元检查过，但真实源码读取被guard以linked_source拒绝，producer_a rc1，未进入用例。
只读定位确认selective运行库链接到既有overlay。r2精确绑定这一个解析目标，读取前后校验别名和相同源码SHA，
没有放宽为允许任意链接，没有安装环境或改G0。原失败4文件及其manifest在r1目录保留，详见DS_COMPLETION_R2_20260905.md。
首次查找本地结果目录下非发布的recovery_binding/submit文件不存在，随后从版本化提交脚本定位实际运行库；
没有猜路径读取数据、调用默认uv或创建新环境。

## 与正方向的关系

本轮是可用训练接口的可靠性进展，不是新的critic accuracy、clean scaling或搜索收益。
实验设计技能促使核对“实际产物证明更新发生”，并使用旧代码负控；没有重复旧DDP轨迹或loss bridge检查。
主线仍为同预算G-reuse→L对照：来源/config/experiment-closed及正式fit预算门保留。
固定前向换边候选继续关闭，不为了寻找好结果重新选规则。下一实证关键依赖没有被这次修复替代。

香港9月5日01:42只读核查：G0 12377仍PENDING/Resources、Runtime0、原训练源干净；估计12:39:11开跑，非保证。
学长fetch成功、仍b8d0951，没有新commit/outcome；316归档、619/960eligible，closure=false/config-v2=0。
摄取3884166已正常完成退出，未重启旧链。新源码、条件与预算不写入正在排队的G0；详见live_status.json。
