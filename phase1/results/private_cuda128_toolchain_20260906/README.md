# 私有CUDA12.8修复与节点诊断：原始证据

2026-09-06。解决的是gpu28缺固定12.8编译工具链，**不是模型/scaling收益，也不是生产GPU验收**。
源安装7c0c06e1a1bdb355d35ab052da16e3454fde9198；修复/独立核验2aaa9bdaac55878170c4f9660e3592540ffcc32f。

- 0GPU节点任务请求被QOSMinGRES拒绝，没有分配job，错误原文保留在cpu0_rejected。
- 合法最小1GPU诊断12571实跑5秒，未创建GPU context/导入训练框架；全量源hash与独立postcheck通过。
  加上旧12570的2GPU秒，短工程组截至诊断终点实际7GPU秒。此数字不包含后来新提交12572。
- 官方4组件下载169877512字节，精确SHA通过。初次编译失败：默认gcc9缺C++前端；原FAILURE与log不变。
- 单次显式修复复用下载，指定/usr/bin/g++13，不修改系统或R5venv；CUDA对象编译成功但未运行。
  独立重新对照4归档→1728文件/7链接及readonly；Linux CPU测试20项通过。
- export时工具链目录实际分配1413439488字节≤1610612736；不是完整训练checkpoint空间已解决。

原安装wrapper实耗87.73902740608901秒（失败，含前置测试），修复wrapper66.38150821160525秒（三阶段全通过）。
两次安装前launcher问题也记录：站点env不兼容nounset、Git归档顶层目录误拒绝，均在安装器启动前纠正。
这些失败不能删除，也不能将最终修复成功倒填成原安装成功。

关键绑定：

- installed manifest `ce7f9f18218799db0776d08a2c3e2342e51273bcaccae61c1ebab8e340e959f1`
- recovery receipt `8701d0fc275c5c0f7a124d05e622bbe0a1e7f5313b7260911000326808b5730a`
- independent receipt `6732f4045503fb658cce9a0fbf7c449985ecee41f01886d3e4f2a704463dd2fe`
- safe export archive `b97adb799836b7634b65fa1089e5de87479d0ea4e8c8d74e8f9bbe96603bfa20`
- safe export manifest `85c30da6e693d43140a9666224a152381d490f3b004a3797a0059d9394f23129`

37个原始文件（含MANIFEST）逐字节导入；未导出编译器二进制、第三方归档、API凭据或研究保护数据。
随附07:04学长0903/0904目录名复核：9/6档名与本地一致，0904既知Drive ID未变化。
这只是名称/部分ID层面的观察，不排除同ID改内容，不是全部历史目录或payload复验。

修复后独立短GPU测试另按source11ff14a7f6fe9a4a2ab9b830a9829f07b0249b2c提交12572，
本目录不预先包含其结果；原12535不动。四fit真实训练仍缺合格来源，准入为空。
