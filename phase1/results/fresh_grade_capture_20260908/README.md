# 新评分产物留存：真实评分器兼容性验证

2026-09-08。这是生产接入准备，不是新的 critic 效果、clean scaling、训练来源准入或生产部署。

## 实际完成

源码：`6b945b6e5af738d702f493f988d7e3f10b011bd1`；
真实 MLE-bench grader 源码：`507f92e1138bb6e40dac5c6ee7a6758e6424bf97`。

- Linux 单元测试 **29 passed**；本地 Windows **28 passed / 1 symlink skip**。
- 6 个真实 grader，固定 **31 个小型已知案例**：正确提交、乱序、错误 ID、重复 ID、缺目标列，另有常量 Spearman。
- A/B 两遍 capture，每遍由独立进程、不导入写入器地枚举归档、核对哈希、从留存 CSV 重新评分；逐例结果与已知答案一致。
- 每次 capture 内只调用评分 callback 一次，返回原对象；不改变分数精度、无效提交规则或原文件清理流程。
- 评分前保存提交和代码；评分后检查原文件及归档副本不变；任何额外文件、内容变化或失败事务拒收。
- 实际总墙钟 **42.724059098996804 秒**；生成测试产物 **6536622 字节**；0 GPU／API／模型 fit。
- 评分测试进程记录 network_attempts=0、real_data_attempts=0。只使用脚本生成的小表，不读取任何真实提交、答案或保护 cohort。
- 导出时重新核对 **193 个源码文件**；本地下载再核对 **13 个安全回执/日志** 的 SHA 和大小。

summary SHA：`dd0fcde699234fce9de30d200ebed33a1c97a784b66eef26e3b4ae02f6199eec`。
export manifest SHA：`b3c02859aa95155bbc940722a492e2b904247494bf5d506f97a6791c290ad98a`。
manifest 只绑定导出的 13 文件，不包含本 README。

原始 fixture CSV、归档中的代码/结果均留在远端测试目录，没有上传 Git。
远端运行位置：`/research/d7/spc/yzyang4/fresh-grade-capture-6b945b6e5af7-20260908`。
本目录 A/B 中的 fixture 名字只是生成的测试案例，不是任何保护人口中的候选身份。

## 失败如实保留

首轮 Linux 源码 `33ebc8dc6f95e711abda8f34b48f55f59061e71b` 在测试初始化发生 29 errors：
远端旧 pytest 把 `setup` 辅助函数当作 xunit 模块钩子。改名 `make_case`，以新 commit、新目录重跑同一矩阵。
不是改评分函数或放宽验收；首次没有进入真实 grader fixture 调用。
`first_attempt_FAILED.json` 和 `first_attempt_tests.log` 保留，原远端目录不覆盖。

本地更早一次故障为测试代码尝试删除 Windows 只读临时 fixture；仅在该测试中先解除只读位再删除。
没有删除用户数据、修改真实语料权限或反复重试未知状态的实际评分。

## 能解决什么，不能解决什么

能够避免将来正常清理 submission 后失去复核依据；同时明确失败不重试、原输入/归档副本不一致拒收。
这是可选 helper，默认 Dojo 不调用它，学长分支和运行中 producer 均未修改。

不能凭它认证历史 evaluator、候选执行环境或全部运行依赖；提供的 execution receipt SHA 仍只是未经认证的引用。
0400/0700 不是同 UID sandbox；归档必须在 agent 不可挂载的可信存储，真实部署须另外验证。
COMPLETE 的自哈希不是签名，需独立保留 receipt hash；FAILED 优先于 COMPLETE。

四-fit 仍缺独立开发范围及实际执行/评分来源。用户回复“可以”确认继续处理，并未给出原记录位置；
因此 `ADMITTED_RELEASES` 不变，也没有挪用 first-960／Target-300／Target-522。
不再为此重复 G0、分词诊断或通用测试；下一关键动作是接入实际来源，或明确没有可恢复记录后制定新开发生产范围。

实现与部署边界见 [设计说明](../../FRESH_GRADE_CAPTURE_DESIGN_20260908.md)。
