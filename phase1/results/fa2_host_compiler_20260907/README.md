# FA2实际节点编译器与来源核验进展

## 2026-09-07恢复后的原始回执补齐

以下覆盖下文“尚未导出”的动态状态，不改动停机历史：已将远端安全回执逐字节复制至
`remote-node/`与`remote-historical/`并独立复算5个SHA，全部匹配原值。
inventory/compile及3份历史来源核验均为原文件；其余原有内容仍是终端观测整理。
真实FA2全量构建12641已经释放并于UTC22:09:01观测RUNNING/gpu37；不是完成或GPU验收。

|原文件|SHA256|
|---|---|
|remote-node/inventory.json|ff9aeca3e3040388cffd4b12a2b2a19fd05a0c12bba8d67eeb2250b143b9a9de|
|remote-node/compile.json|100131462fbcc9b55ed1eff2d6fac03e254080cbbf44977b0c4d7cd80993c0a0|
|remote-historical/historical-stratum-independent-20260907.json|0371cd61a8d5cd08748c5b96eb33b092d1e6005f5c5a50fac5306018340486b0|
|remote-historical/historical-code-scope-20260907.json|af04ac8f26d7937186c88167e2022782c5c8a899141bcf18fdb3558eb2222ed6|
|remote-historical/summary.json|749111383fa1e8e5acf6d614aa1badbc02cf3424ae51496a8238910a82990baa|

固定84run/24archive的header-only A/B完成，5项实际Linux CPU测试通过，未打开member payload。
仅发现84个可能grading记录，未发现扫描格式内的预测表/依赖清单；该结论只限固定归档范围，
不是证明生产机其它位置没有文件。不能从grading文件名推出可重评分、版本完整或训练资格。
独立aggregate复验与安全原回执导出尚待完成，未重建Cards/G/L。

2026-09-07。本目录只保存本会话终端观测的整理，不冒充远端原文件的逐字节导出。
远端停机前已完成核验；原文件仍在各自专属目录，恢复后需复制安全回执并独立重hash。

## 已完成

- 12635真实编译错误是默认gcc9找不到cc1plus，不是模型OOM或研究盘空间问题。
- 12638保留1卡运行1秒，节点哈希门发现登录机与gpu37编译器补丁包不同，未开始全量FA2编译。
- 12639完成独立目标节点诊断：gpu37/g++13.3.0，显式绑定后能编译sm120对象，Slurm总时长5秒。
  没有调用CUDA kernel、模型或数据；占卡时间照常计费。
- 新FA2 artifact绑定、CPU数学参考、错误数值负控、编译器漂移门等15项Linux测试通过。
  新header-only扫描本地5项通过；第一次测试发现grading文件名分类漏项，已在真实读取前修复并重测，未掩盖失败。
- 固定84run的代码/stratum独立验证完成：12记录commit、9种Dojo清单、24个exact strata，
  同task跨stratum的12种组合均不只是commit不同。每个stratum只有1个保守组件。
  这不自动禁止跨配置开发，但不足以称同配置独立重复；没有扩选数据或新增训练准入。

## 原始回执位置（均远端）

- `/research/d7/spc/yzyang4/flash-attn-build-20260907/compile-status.json`及`compile.log`：12635。
- `/research/d7/spc/yzyang4/flash-attn-build-20260907-r2/submission/`：固定代码、15项测试、held/release记录。
- `/research/d7/spc/yzyang4/flash-attn-build-20260907-r2/slurm-12638.out`：哈希差异早停。
- `/research/d7/spc/yzyang4/fa2-node-compiler-20260907/job-12639/`：`inventory.json`、`compile.json`及CUDA对象。
- `/research/d7/spc/yzyang4/historical-stratum-independent-20260907.json`：独立数据结构核验。
  绑定原代码范围SHA `af04ac8f26d7937186c88167e2022782c5c8a899141bcf18fdb3558eb2222ed6`，
  配置差异SHA `749111383fa1e8e5acf6d614aa1badbc02cf3424ae51496a8238910a82990baa`。

## 当前阻塞与恢复顺序

R3代码34343b8ff7dbe4107ccced6781df627afce7c988已发布，但SSH返回pam_nologin/系统正在关闭；
首次R3准备/提交命令在登录阶段被拒，因此没有新的R3目录准备或job。不是VPN超时，不尝试绕过登录限制。
旧12535保持held；12635/12638/12639已终态，不重复release或重跑exclusive检查。

恢复后先只读核对队列、旧作业终态、目录是否存在及原始回执，再准备新的R3来源与一次受限构建。
现实际累计7297GPU秒，后续构建2760及双卡尺寸3840的保守合计13897≤14400。
完整FA2构建成功后还必须逐文件绑定附加目录，在PRO6000上验证FA2数值，才能再做原1.7B/16K保存恢复。
GPU数学验收阈值已冻结，不能看到失败后调阈值或改attention backend救回。

并行待做的具体来源补齐尝试：只查固定84run归档header，判断是否保留预测表可供新pristine evaluator重新评分。
固定源码34343b8中的`historical_saved_output_headers.py`；尚未执行真实扫描，上传orchestrator也被停机拒绝。
即使存在文件，仍须独立的可读性、完整性、标签隔离与评分协议；本检查不会读submission或成绩。

本轮没有新的critic收益、干净scaling或正式效果四fit结果，没有修改学长分支。
