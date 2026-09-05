# 双3090私有CUDA12.8：单次恢复工程验证

2026-09-06，用户会话内总授权。新job，不改12535，不覆盖12570失败或12571诊断。
问题：私有工具链补齐后，真实双卡ZeRO3/CPUAdam的两个中断点能否恢复为逐位相同最终状态？
使用相同4433参数微型Qwen结构、seed6、BF16/eager、五轨迹full4/prefix2/resume2/prefix3/resume3。
仅环境依赖改为已独立验证的12.8私有prefix、显式CXX/NVCC_CCBIN；学习逻辑/容差/数据fixture不改。
不是生产1.7B、16K、FA2，也不是critic/scaling效果。不把不同GPU耗时当公平性能结果。

GPU矩阵=1job×2RTX3090×18min；driver900秒+终止60秒。最多2880 GPU秒（含300秒退出及60秒余量）。
12570实耗2、12571实耗5GPU秒；更保守用诊断预算180，组合2+180+2880=3062≤原独立3120。
仍有原12535独立预算，不取消、修改、复制它。新job先held，核CPU12/mem0/gres/节点/gittree/时间再放行；不自动重试。

## 13项预检

1. 真实节点build_tools写入nvcc/host compiler/ninja SHA、version、已验证prefix全部文件；不只相信环境变量。
2. Linux CPU原恢复/分片/分配/独立payload verifier测试与新工具链绑定测试均通过才提交。
3. 五轨迹全是自生成工程fixture，零真实train/dev/test样本；不声称真实数据资格。
4. 分别报告两个断点×两rank逐位状态、实际payload和consumption，不只driver汇总。
5. 科学旋钮不变；没有方法性能对照，PRO6000/3090时间不互比。
6. 保存完整实际ZeRO分片、优化器/RNG/manifest/trace；输出新job专属目录。
7. 不读取真实语料/旧模型/封存标签，strace独立审核；来源是固定readonly5f3bc3工程定义。
8. python/numpy/torch/cuda seed与扰动恢复流程不变，不重抽fixture。
9. 提交前源码扫描，任务不导入代理/密钥，离线hub；公开仅经过扫描的工程产物。
10. 18min硬墙钟，driver900s，300s退出预算+60smargin；失败存exit_status，不自动扩大。
11. 不用于统计效果/显著性或训练功效，仅消除恢复入口工程风险。
12. controller、worker、独立verifier分别保存真实rc；缺任一终点不得称通过。
13. 原确认/训练开发协议、intake、旧抽签字节保持；生产准入仍空。

私有安装：原7c0c06e安装的默认gcc9缺C++前端；2aaa9bd显式g++13修复成功，原FAILURE保留。
独立对照4官方归档→1728文件/7链接，manifest ce7f9f18218799db0776d08a2c3e2342e51273bcaccae61c1ebab8e340e959f1。
工具链不是完整CUDA SDK，不改system/venv，GPU上重核全部prefix和实际C++前端。
显式host compiler选项由[NVIDIA CUDA12.8文档](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-features-archive/index.html)支持。
完整训练存储与真实source/experiment/dev资格仍未解决，不能由这个检查越过。
