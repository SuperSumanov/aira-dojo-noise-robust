# 定向排障：重建gateway时的kernel-info无回复

2026-09-12，用户要求一小时内推进实质工作。最多32次fresh gateway＋新内核，首次故障后停止并检查通道；
gpu28原MLE镜像、单3090/6CPU、一个allocation最多35分钟（35/60 GPU·h），无API/模型/任务数据/旧候选重跑。

已知：13156两次失败均120请求/0匹配reply，服务端记录已连接；未见故障之前的WebSocket错误。
Space25的ZMQ non-socket异常在超时并开始关机以后，不能倒置时间当作握手根因。
旧12内核测试复用一个gateway；真实任务每次重建整个gateway并复用该step端口，现验证这一未覆盖生命周期。

先做被动服务端记录：incoming消息类型/通道，outgoing是否匹配，连接future是否完成；不输出代码、消息内容、认证或会话身份。
原120秒握手不变；成功只执行固定print标记。失败时原ready仍为false，再独立检查control通道和新WebSocket连接，
不能把诊断后连接成功写成原失败修复，也不以发生故障后的尝试估计成功率。
若32次未复现，明确报告没有复现，不增加循环追出故障；若硬时间到则报告不完整矩阵。

这是定位基础设施，不是G0/critic验收或新模型收益。只改独立诊断进程bootstrap以加载被动hook，原镜像/冻结source不变。
先编译/单元测试hook不改消息和验证真实source导入；核节点、队列、代码SHA/提交及输出路径后只提交一次。
预检清单数据切分、训练存档、功效项不适用：没有训练/评测数据；完整停止记录和安全导出适用。
持久结果写独立root，旧13156产物只读。期间继续做已揭盲机制证据与后继方法准备，不读取保护cohort。

运行库只读镜像内省：jupyter_server2.20.0、jupyter_client8.9.1、ipykernel7.3.0、kernel_gateway3.0.1、pyzmq27.1.0、tornado6.5.7。
协议参考：[Jupyter kernel-info control通道说明](https://jupyter.org/enhancement-proposals/kernel-info/)，
[官方gateway协议](https://jupyter-kernel-gateway.readthedocs.io/en/latest/websocket-mode.html)。实际定位以镜像内代码和观测为准。
