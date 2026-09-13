# 独立进程与真实任务接口验证

`diagnostic.json` 是13286的固定合成计算/错误/超时/CUDA验证；`integration.json` 是13287的真实Leaf/Space共同RF预测对照、24个双worker调用和IPython magic验证。两者均零API，原MLE任务镜像、gpu28 RTX3090。

这是新执行后端的有限正确性证据，**不是e2e效果、普遍可靠性或critic进步**。新后端尚未接入任何正式搜索；现有13282/13283与失败seed未被修改/补跑。

逐字节SHA256：

- diagnostic：`f9c7728c563d6026567ea48d52580bc97b084eeb0e17fbc4cd32c45d81f71d9d`
- integration：`4b7e059c43cd266778e80ff22a776ba4de5cc2e74e8007ae94f68f28a7ff789b`
- independent-parity：`63cd8f3cae25a954107c8247c8a1ca4219483abe401749eee5ba7c016b8e2cd1`

独立实现重新读取八份实际预测文件，校验其哈希、列、行及数值。四对均通过事先固定的绝对容差`1e-12`：两次Leaf最大差分别为`5.551115123125783e-17`和`1.1102230246251565e-16`；Space两次差均为零。Leaf文件**并非逐字节相同**，不能把容差内相等写成文件相同。此核验没有访问外部成绩。

13286分配80秒；13287分配85秒。真实ML模型为冻结起点的重复执行，不是新的模型搜索或训练收益实验。完整计划/限制见上级目录的PROCESS_TRANSPORT_DIAGNOSTIC_PLAN和FRESH_CONTAINER_INTEGRATION_PLAN。
