# 0820 LMSYS task-identity fail-closed 与恢复协议

日期：2026-08-22。

## 发生了什么

`0820` 的首个稳定归档 `cdiscount-image-classification-challenge-8seeds.tar.gz` 已在固定 scientific commit
`90842c49dbd73d41d405a5ecdad2224ee447b375` 下完成 append-only transaction；其实际 inventory 为 4 个
eligible physical runs、71 endpoints、19 structural sibling pairs。累计 outcome-blind inventory 变为 50 drops、
253 eligible runs、6,542 endpoints、1,684 structural pairs、26 tasks；dominant run-task share 为
`0.10276679841897234`，dominant pair-task share 为 `0.16508313539192399`。label vault、outcome 与 scorer prediction
均未被 accumulator 打开。

下一归档 `0820/lmsys-chatbot-arena-8seeds.tar.gz` 在 frozen intake 返回
`journal must identify exactly one competition`，连续 monitor 与 follow-up initialize 均按约定 fail closed。
两次失败 attempt 的日志分别通过凭据形状扫描，命中均为 0；失败与 GPU、API 或余额无关。

## 冻结诊断

归档路径、size=`29102615`、mtime_ns=`1787326291000000000` 与 SHA-256
`88cda8b980ee3b03fb2a19b6fdbddf35e4330e9e2adbc678c83cf20e3510f5b3` 被精确绑定。复用已冻结 audit commit
`5ee342f549311ece7bc111ddd0cb7ff08b740210` 双跑，结果逐字节一致；diagnostic SHA-256 为
`c71a3a7e952e693fb715d34dd82bc71c7a53ccb0285f2bfa06680d5dbbc09728`。

4/4 checkpoint journals 的 task identity cardinality 都为 0；无 cardinality=1 或 multiple 的 journal。审计先对
raw journal 做凭据扫描，再解析 JSON；未读 env/live-event members，未输出 task identity 值、代码、stdout、grade、
metric 或 outcome。该模式与 0817 LMSYS 的已冻结结构失败同类，但本次裁决只绑定 0820 的精确 archive bytes，
不按任务名泛化拒收。

## 裁决与恢复边界

整包以 `JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE` 拒收，不从文件名推断 task、不做部分 salvage。
由独立 builder 双跑生成 registry，逐字节一致，SHA-256 为
`766a4fa678a4cb9ae55fdb460ae94b5f1be93ce2040b64ed7e48c13260f9aebd`。恢复 monitor 时必须同时绑定全部旧 registry、
本 registry、原 scientific commit 与原 6 小时稳定性门；未知的新结构错误继续 fail closed。恢复只做 CPU intake 与
label-free transition escrow append，GPU=0、API=0、base-LLM update=0。

恢复后的剩余归档结果尚未写入本节；只有 transaction 真正 commit 后才计入新语料。
