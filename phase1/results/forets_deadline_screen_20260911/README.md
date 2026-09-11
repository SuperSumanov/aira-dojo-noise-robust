# 限时完成预测：开发筛查结果

2026-09-11，代码`643938e7910653b3fca9693243bd0168e5f0234e`。
完整方案/失败/结论边界：[FORETS_DEADLINE_SCREEN](../../FORETS_DEADLINE_SCREEN_20260911.md)。

- 固定84旧开发run，3447非空程序；25条耗时缺失或无效，3422条可构造目标。
- 6个至少有2来源组件的任务，15个整组件留出，1554条预测；25次实际LogisticRegression拟合，5次单类回退。
- 只有38/1554（2.4453024453024454%）记录在300秒内正常退出；这不等于38份有效submission。
- 投资筛查未通过；没有新critic收益或e2e结果。原始行预测/身份仍只存远端，未导出任务数据、代码、数字成绩或密钥。

公开文件为安全聚合`public-summary.json`、逐任务`per-task.csv`、独立枚举46656个任务bootstrap样本的`independent-exact.json`。
独立核算验证了逐行预测的聚合与门，不是独立认证历史实际运行或重新生成源标签。
public-summary SHA256：`5c6cb1610cc8caed42ce2dffc7aeddc72e722bec9bc15076869a24cb18003544`。
远端原summary SHA256：`93ff3521f32ad984fcf4c85e9ee60d4fabe9ef8d86019881dd0f5b28a46fc509`。
远端预测CSV SHA256：`25c8704d9e0883068be941eb37dfd97726813235f17c22ac899a471a15d93adb`。

执行根：`/research/d7/spc/yzyang4/forets-deadline-screen-20260911-TeDok5zC/actual-r2`。
首次读取大小失败保留在相邻`actual`与`execution.log`，尚未拟合；未覆盖、没追加调参。
0 GPU/API/critic或agent底座更新；不是“零训练”，实际有25次轻量模型拟合。
