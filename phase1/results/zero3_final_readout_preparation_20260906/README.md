# 真实 ZeRO 最终权重读出：衔接准备，尚未实际验收

源码 `ac445531b9e797a3c12eb94bb9a4c94d5248e028`。
脚本只面向作业12535、训练源码`09911b15ca065442386120707dccf036e262dadd`生成的自有微型工程检查点。
不是正式训练入口；ADMITTED_RELEASES保持空，没有提交或修改GPU作业。

现有final reader此前只在生成的DS格式fixture上测试。新增衔接检查要求先取得实际12535的
独立payload acceptance及其准确SHA，重验全部原检查点manifest，再加载full/resume2/resume3三个FINAL，
以固定BF16 CPU模型和固定合成token输入比较权重与输出。只在原GPU结果真正完成后运行；不能提前填入SHA。
另行trace/security验收仍不可缺，脚本明确不把caller提供的SHA当成已经完成这些审计。

本次只执行帮助函数测试：本地12通过/7因无Torch跳过；固定R5 CPU环境19通过，pytest4.81秒，
整个测试进程15.627409677021205秒。包括实际CPU BF16合成标量前向和负控，**没有打开12535检查点**，
也没有执行真实Qwen分片转换。因此不能据这些测试宣称12535、1.7B/16K或模型效果验收。
无新的GPU/API/模型fit，未使用真实语料。测试环境固定CPU/offline；不宣称完整OS级访问隔离。

源码包19文件/215040字节，逐Git blob导出，SHA
`999890686892f6d648c189d63359a5be5a5a6b071b493e90742fa63d2e88a097`。
原始测试日志SHA `5258542f36a68ac8eb9187ee3392eb0f36ccc1e7df3129d63d55c2a4e4328111`。
`receipt.json`及`tests.txt`是这次测试的原始字节；README不属于测试执行回执。
