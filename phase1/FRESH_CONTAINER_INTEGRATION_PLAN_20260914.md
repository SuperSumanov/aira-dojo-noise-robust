# 新执行后端的真实任务与并发接线验证

2026-09-14 HK，尚未改变EScope任何运行。13286已通过四组固定合成计算和错误/超时/CUDA检查，但不能推出生产可靠。

新的 opt-in `FreshContainerInterpreter` 每次启动原镜像里的IPython cell，避免HTTP/WebSocket握手；保留可用的IPython magic、原数据只读挂载、driver namespace和新进程隔离。它不支持跨调用共享变量、不承诺任意富媒体输出等价。模型文本作为文件数据交给IPython，不拼接为控制代码；持久化/文件取回遵循已绑定workspace。现有主实验和原失败记录绝不修改。

验证矩阵：Leaf/Space共同RF原代码×两次重复×Jupyter/fresh两后端，共8个真实公共任务执行，训练内参数/划分不变，单程序90秒（不是20分钟新搜索）。比较完整提交结构/列序/预测值atol1e-12，不调用外部成绩。再两个独立worker各12个新容器调用，共24，及一次IPython magic。Jupyter首次未知后不补跑、不再重试它；缺配对则不能宣布验证全部通过。

一份gpu28/3090/6CPU/45分钟分配，上限0.75GPUh，模型/API调用0。2500秒全局限制与Slurm限制双重兜底。两并发worker共享这一张卡只跑合成算例，不假称两张独立GPU；实际MLE八次顺序执行。保持原镜像/Torch，不调用critic/G0。

全部四次fresh真实执行有效、全部四对预测相同、24并发调用完成、magic成功，才通过有限集成验证；不等于论文正效果，不恢复失败seed，不据此绕过EScope原扩大门。以后效果实验如用该后端，两臂必须同环境、完整计入真实开销，重新固定协议。

预检：诊断实际输出已过；本地5项新helper单测通过（Windows缺SIGKILL的测试mock已修正，不改Linux生产行为），源代码入口/签名逐项对照原Interpreter/JupyterFactory；prepare后校验完整当前source与所有adapter哈希。无训练集新增、无保护cohort读取、无抽样/标签选择、无API；固定原RF种子，分任务逐次报未知；不改活跃源码。其余检查单中训练功效/保存模型等不适用。
