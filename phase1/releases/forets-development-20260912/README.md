# 可直接复查的 ForeTS 开发诊断包（2026-09-12）

[下载ZIP](forets-development-20260912.zip)，38,466字节，SHA256
`dc99104b0faf0d175b9dac7be5fd54aaf02037f2b7268e974571a15afc8322b4`。
不依赖我方研究盘权限；27个条目包括24份原样生成程序、programs.json、blind-pools.json和manifest.json。

这不是一个新corpus论文主张，也不是新的冻结测试集，而是让方法开发可迅速复查的完整小包。
两个任务Leaf/Spaceship、程序种子要求16—21、两个生成模型；24程序全部在原镜像/gpu28分配上各执行一次。
13有效提交已独立数值复核；11无效保留缺失而非补0。没有挑成功样本，也没有修过失败代码。
4个池有执行前双序盲排名；生成器身份不提供给排名器，但会作为开发元数据保留在本包。

文件说明：

- `s*/code-*.py`：当时真正执行的程序，manifest记录SHA。
- `programs.json`：逐程序任务、生成模型、种子要求、有效性、外部成绩、费用、时间、最终异常摘要和代码路径。
- `blind-pools.json`：uniform4、固定Borda/top2、次要always-Flash对照；slots是同任务四程序的局部顺序，不是跨任务编号。
- `manifest.json`：实际job、源码tree、控制器commit、输入回执SHA和用途限制。

全部标签已经看过，若据此改模型/提示/选择规则，只能计作开发；之后必须另采未触碰的效果对照。
测试执行前critic时只能给程序及合法公开说明，不能把programs.json的分数、有效性、异常行或任何执行后信息混入输入。
不含Kaggle原数据/真实标签表、凭据、完整stdout或first-960/Target-300/Target-522任何内容。
不要将24个程序写成24个搜索run，或者将四个池写成四个任务；未确认等预算e2e收益。

最有用的检查不是在小包上调出高分，而是分别看：混合有效/无效池能否避开故障；全有效Leaf池能否保留更好解；
全无效Spaceship池为何无法靠排序解决。完整结果和解释边界见[给学长报告](../../FORETS_PROGRESS_FOR_ADVISOR_20260912.md)。
