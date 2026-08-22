# 0821 Plant archive 结构性拒收

- 精确归档：`0821/plant-pathology-2021-fgvc8-8seeds.tar.gz`；size=`119572767`，
  mtime_ns=`1787408006000000000`。
- archive SHA-256：`5213f40cb0246d927b5e825943232a8f6e2bf0eba7c7d7005a13740ba0a67b20`。
- diagnostic SHA-256：`8277d6dfe0651d88179735d8e2088d2de1cf329e9c2720272804833b65d226fc`。
- registry SHA-256：`7c16889eb5ec57b1ca391b4171a997ad0fcd35d076ad6b34fddb53b556e35e6e`。
- 固定 auditor commit `5ee342f549311ece7bc111ddd0cb7ff08b740210` 的聚焦测试 1/1；
  diagnostic 双跑逐字节一致。
- 当前 control commit 的 registry-builder 聚焦测试 5/5；registry 双构建逐字节一致。

4/4 checkpoint journals 的 competition identity cardinality 均为 0，所以只对这一个精确 archive bytes
按 `JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE` 整包拒收；不得从文件名补 task，也不得部分
salvage。raw checkpoint journal 在 JSON 解析前先经过 credential-shape scan；env/live-event journal、task
identity 值、代码、stdout、grade、metric、prediction 与 outcome 均未读或未输出。

连续 intake 在该门 fail closed，前两笔 0821 transaction 保持不变。首轮诊断包装还因旧 auditor commit 不含
后来新增的 registry-builder 测试而在归档访问前退出；失败目录保留，重跑只执行该 commit 实际拥有的 auditor
测试，builder 则在当前提交单独测试。只有把本 registry 与此前全部 registry 的精确 SHA 同时绑定到 clean control
commit，才允许恢复剩余 0821 archive 的 CPU-only intake；scientific commit、activation、estimand、frozen scorer
和稳定性门不得改变。
