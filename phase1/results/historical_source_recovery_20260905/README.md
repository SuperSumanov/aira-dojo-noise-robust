# 实际历史来源恢复：676个run完整定位，训练资格仍须分开判断

日期：2026-09-05香港23时。本轮针对“正式训练缺生产范围、experiment映射和构建记录”直接恢复真实资料，
不是模型效果实验，也不把合成测试通过数当成果。以下数字来自实际远端产物和独立复验。

## 已解除的具体阻塞

|项目|核验结果|
|---|---|
|固定历史范围|旧a466888-v3的全部676个run，launch日期2026-07-26至2026-08-15；未从失败S0挑子集|
|原始配置恢复|旧归档恢复668个run、675份出现记录；全部有recorded Git commit和meta_id|
|缺失leaf来源|共享盘0811 leaf已更正，另存隔离区后匹配补回8个run；不是我方补造或修改旧包|
|完整覆盖|676/676 run都有实际dojo_config与regular checkpoint/journal.jsonl定位；共683条来源出现记录|
|重复副本|7个run的重复记录全部为同archive SHA+同member+同config SHA；676个唯一来源键，跨run冲突0|
|完整来源账本|重新验证145个物理文件副本、143个不同archive哈希；原配置和hold全部保留|
|保守分组|139个archive/config关联组件；不是把meta_id直接当独立生产实例|
|旧hold闭包|101组件/538run与旧hold有关，不能拿进train；另38组件/138run没有这项关联|
|候选开发支持|上述138run覆盖21任务、14个recorded代码版本；尚非同版本合格训练包|

两份旧错误archive继续保留原错误状态，旧S0=`IDENTITY_UNAVAILABLE`不改判。新账本是覆盖全部固定run的
来源证据修复，不是“丢掉8个run和错误包后宣告S0通过”。原重复来源仍逐条保留，不增加独立样本量。
原目录中的420份配置与学长676-run集合没有目录名匹配，未混入本次来源。

## 学长现在不必再补什么、还需要什么

无需再上传那8个leaf run、手填676行Git/meta_id，或追造不存在的旧Cards/G/L构建命令。
我们已保存完整私有映射，可据明确的新输入范围重新构建，并记录**本次**真实命令、版本、输入SHA与输出SHA。

但是以下生产事实不能由配置哈希替代：

1. **实验实例语义及遗漏的跨目录联系**：目前采用“同archive SHA+顶层batch目录，或同recorded meta_id必须同组”
   的保守闭包；meta_id在AIRA中是配置hash，不是天然唯一的生产实例。需要生产方确认一次实际experiment的完整范围，
   或提供原runner/launch清单，以核对是否还存在这套记录没有覆盖的联系。没有旧hold关联不等于已通过所有保护集隔离。
2. **实际运行/评分环境出处**：676个配置记录24个Git版本；我方repo里22个commit存在、2个不存在。
   记录的9个不同base_path中5个不存在、4个Permission denied。没有访问或绕过无权目录。
   对22个可读commit中的pyproject/requirements进行固定源码查找，未找到MLE-bench版本引用；这不是遍历所有可能安装记录。
   需要可读的当次代码/环境快照、依赖锁或评分执行记录位置，不能把当前Git版本填成历史实际评分版本。

最小交接就是：**实际experiment/runner记录位置，以及当时执行环境/MLE-bench评分版本记录位置**。
给现成记录即可，不要手工声明“全部true”，也不要在Git或聊天里放env/API key。
正式未触碰cohort的资格继续走原协议；旧test不改名，first960/Target300/Target522未读取。

## 实际构建与核验记录（不是Cards/G/L构建回执）

- 初始恢复code=`14f8da6b1736f468ada9c220b21703a245c4bb3a`，两CPU，实际耗时259.4490107577294秒，rc0。
- 修复候选检查code=`3044f0ae3f45a2df8b4ee3563b7e7335f2a1e3bf`；A/B两个独立进程的summary和完整mapping逐字节相同。
  独立实现另重读8个配置，核id、实际launch、task、Git、meta与8个journal header；不读journal payload。
- 完整ledger实际code=`faf04cc5e3f8193652041674fff86e569062540f`，2026-09-05T15:21:32Z—15:24:56Z，
  rc0，两CPU；按秒分辨率时间边界计算204秒。Python3.11.15，无抽样，HASHSEED=0。
- 独立账本核验code=`4806e322d4513801400d07e0d539bbd2d8aa0345`，不用producer的union-find，
  另用图遍历重算组件/hold闭包并逐条核对所有来源，结果一致。
- 实际argv、cwd、源码/打包哈希、起止时间和一行运行CSV见`ledger/execution_context.json`及`ledger/runs.csv`。
  `ledger/public_manifest.json`绑定四个公开文件；只有聚合回执下传，私有身份/原配置/归档未进Git。

**没有执行Cards/G/L构建、真实训练或新的模型评估。**21个单测只是危险路径与实现的预检；
676-run实物恢复才是本轮进展。配置审查只删除明确的实例输出路径来定义recorded-stratum，所有task输入、
prompt/client、资源与interpreter image保留；139个recorded strata也不是已认证的pristine运行环境。
无需hash任何journal payload：7个重复已被整个压缩物件的字节一致性覆盖。journal成绩字段、env均未解析。

## 失败与局限全部保留

- 第一次3044f0a远端测试因PYTHONPATH不完整失败，未开始候选归档读取；修正启动环境后15测试通过。
- 第一版ledger64ba4b9在归档读取前以reused_config_origin停止。独立核实是精确同源副本后，
  只合并完全相同origin键、仍保留出现次数；冲突run/config依然拒绝。修正后21测试通过。
- 检查历史base_path时遇PermissionError；后续仅统计无权/不存在，不绕过。
- 两次执行依赖文件SHA不同，已查明只有CRLF/LF差别：AST相同、换行归一化后逐字节相同，Git blob相同。
  原执行SHA f75ad3539ea71c637a363505625169f434eef8abc47579b3230b8fd917bc0b6b；后续Git导出SHA
  3b5be4fbbc42f2d41665330631a4207848944eeb9256d672dc794c227c885d36。没有用一个SHA冒充另一个。
- 文件open trace支持核验访问范围，但不是完整OS隔离证书；独立ledger verifier重算存储证据，不声称第二次独立重扫全部原始归档。

## 不可变定位

完整账本：`/research/d7/spc/yzyang4/historical-source-ledger-faf04cc-20260905`，已设目录500/文件400。
ledger SHA=`8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1`。
前一步完整mapping SHA=`fd8e0769f4561937f2959c055da18120e3715aaf3b772364cca72e1a4268aec6`。

正确leaf archive另有研究盘只读持久副本：
`/research/d7/spc/yzyang4/historical-repair-candidate-0811-20260905/leaf-repair-8ade376f.tar.gz`，64815070字节，
SHA=`8ade376fb045aa47bffa63b493fa5e4b02d376815d7700c9c9f441c1848edfa4`。
旧source root、旧LFS物件、旧S0、原hold全部未覆盖。

最后只读查询12535仍PENDING/Resources/0秒；没有重投GPU、付费API或新增模型fit。
不能把本次资料修复写成正面accuracy/scaling结论，也不能说正式训练已全部解锁。
