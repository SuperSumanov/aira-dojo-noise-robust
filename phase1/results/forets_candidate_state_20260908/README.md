# ForeTS 候选隔离与有界开发成本（2026-09-08）

这是我方对学长 `8b621851a87d20382feefe8c8458a7db2a1fabea` 的未部署接入补丁。
不修改学长分支/生产 checkout，不是 critic 收益、clean scaling 或端到端验收。

## 已实现范围

先应用 `0002-ForeTS-startup-and-step-boundary-20260908.patch`，再应用
`0003-ForeTS-private-candidate-state-20260908.patch`。0002 保持原样。

- 未执行候选用私有 SQLite 台账留存代码、plan、生成操作的返回成本元数据及 critic 状态。
  不挂 parent.children、不进入普通 journal、不填假失败分数。
- 完整候选批次评分完毕后锁定选择顺序，执行意图先持久化，再调用真实执行/分析；
  仅已执行且完成解析的节点进入 journal/UCT。debug 用完预算的剩余选中项明确标为 skipped_budget。
- 已完成的生成/评分可在完全相同的已确认执行前边界复用；任一未知生成、评分或执行状态阻止整批自动重试。
  writer 锁不自动强删，hash 检测偶然漂移，不宣称同 UID 对手防篡改。
- 独立批次 selector RNG 由显式 selector_seed、任务和起始步数确定，不随生成随机流、输出目录或 critic 配置变化。
  这不是跨臂共同候选/prompt 已经冻结；正式对照仍需同候选批次协议。
- 父类 MCTS 的 while <= 在边界造成无效空转，改成 <。此公共修复须在所有对照臂一致应用。

完整 solver/interpreter checkpoint reconciliation 尚未实现，继承恢复会丢 MCTS 统计/树状态，
故 ForeTS 明确拒绝已有完整 checkpoint 的自动加载，而非错误地宣称可以无损续跑。
当前仅执行前已知批次的恢复通过测试，不允许借此开启长实验。

## 验证与剩余边界

Windows Python 3.13.4：24 个新增定向测试，28 个既有 0002 回归，共 52 passed；
独立 Git index 实际应用后的 tree 为 `af2489d55e174a73f9f92dbb416062f43dd55994`，同 24 项通过。
相对学长 upstream 合计 7 文件，321 新增/95 删除。重复执行相同测试不是独立科学实验。
首次候选测试为21项通过，之后新增3项覆盖并复测；旧回执保留。

测试运行真实补丁的函数体与真实 Node/Journal 的数据结构函数体，模型、HTTP、执行器、分析和部分框架依赖为 stub。
不是实测 prompt 等价、实际总成本、模型收益、Hydra/Dojo 全栈或完整重启验收。
还需：完整恢复原子边界；实际渲染 prompt/available_packages 隔离；operator 内部重试的全部成本；
critic 同步 HTTP/40,000 字符截断及真机批次验收。Linux 复测待本目录后续 receipt，不能预先称通过。

## 开发成本

`development_cost.json` 为远端只读复算原始 JSON（包含命令、源码 commit/hash、时间和三个固定输入 hash）。
84历史runs、24保守组件、15任务中，有6任务至少含两个组件。
假设每任务取两个完整组件、每组件所有非空程序按原完整超时 cap 重执行，六任务最小 cap 合计
2091.6666666666665 GPU小时；不是实际耗时，也不是实验独立性/来源准入证明。

**组件必须全体从训练隔离，不等于组件全部程序都必须重执行。** 原输出 limitations 的第一句
仅适用于本次“全组件重执行”假设，不能作为准入规则。后续应先冻结小规模 sibling 开发组，
仍将对应整个组件从训练排除，再核真实资源上限。未选择任务/组件/程序，未执行程序或模型训练，
严格四fit source gate 不变；原记录位置仍待外部事实确认。

## Linux 预检范围

只运行相同定向测试，最长300秒单次CPU子进程；0 GPU/付费API/fit，不安装依赖、不改活动环境。
远端 exp Python3.11.15 已有 pytest/OmegaConf/dataclasses_json；活动 repo 不含本次 upstream 对象。
因此仅传递已 credential-scan、逐字节 hash 的7个 Git source blobs，与测试模块放在新隔离目录。
不伪造 Git history；缓存只替代源文件读取，不替代模型/执行器验收。
一次只读解释器版本检查因 SSH -c 引号丢失返回shell语法错误；没有执行实验。
随后通过 stdin 脚本读取版本/依赖成功，后续不用该易错 -c 形式。
