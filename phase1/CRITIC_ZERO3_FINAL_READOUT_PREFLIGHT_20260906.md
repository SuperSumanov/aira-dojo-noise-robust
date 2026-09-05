# ZeRO-3 final 到独立推理模型：接口预检

2026-09-06。本项补齐普通DDP final与生产ZeRO-3 final之间的接口差异；没有新训练或揭盲。
独立critic训练仍须真实来源、预算、存储和GPU资格。ADMITTED_RELEASES保持空。

- caller提供经过独立认证的最终checkpoint/绑定/SHA/最终token数及新CPU eval模型；不猜latest或选择prefix。
- 验证两rank完整文件集与哈希，再调用已固定DeepSpeed运行库的lazy FP32合并；不执行checkpoint内脚本。
- 逐tensor恢复为声明的模型dtype；检查形状、finite、精确拷贝和加载前后输入哈希。
- 本功能只恢复推理权重，不恢复optimizer/RNG，不能替代训练resume。异常后必须丢弃caller模型。
- caller自有、可信checkpoint才允许调用；哈希不提供pickle沙箱，当前函数不是数据或模型准入器。
- CPU检查使用自己生成的两rank ZeRO-3格式，26参数BF16小网络和1个FP32 buffer，含奇数分片padding；
  用真实固定DeepSpeed转换器对比已知完整参数与模型前向结果。不是实际DS engine保存证据。
- 拒绝prefix/错误tokens、hash、shape、非finite、额外latest和转换期间输入变动；copy前错误不改变模型。
- seed6、CPU1线程、无GPU/API/真实输入；记录真实版本/commit、失败与原始输出，单次检查≤180秒。
- 不改变原四fit/五臂协议、12535或任何保护cohort；后续必须再用实际通过的GPU工程checkpoint验证此接口。

这里只固定输入格式和读出机制，不称生产收益、硬件通过或来源门已经补齐。未在1.7B规模测量合并峰值RAM。
