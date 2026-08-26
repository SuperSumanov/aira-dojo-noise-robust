# Task-balance structural-only v2：正式结果

状态：`INDEPENDENT_STRUCTURAL_ONLY_TASK_BALANCE_FORWARD_PASS`。本结果包是对旧 v1 provenance 的替代，不覆盖或删除旧
artifact，也不追溯恢复旧 matrix/guard/forward 的严格零 prediction-value 合规性。

## 结果

- baseline `7cda`：339 runs、2,635 canonical sibling pairs、30 tasks；OSIC 823 pairs，占
  `0.31233396584440226`；25% cap 失败，整数债务为 657；
- current `8579`：366 runs、2,755 pairs；相对 baseline 新增 27 个 OSIC pairs 与 93 个非 OSIC pairs；
- 冻结恒等式：`657 + 3*27 - 93 = 645`，按当前逐任务结构计数独立复算也是 645，债务变化为 −12；
- 当前 OSIC 850 pairs，占 `0.308529945553539`，25% cap 仍失败；债务清零前继续新增 27 个 OSIC pairs，因此即时
  “暂避 OSIC”动作明确未遵守；
- 允许结论仅为 structural-only v2 精确恢复了 guard 与 forward accounting。自然摄取不是随机干预，禁止声称 guard
  导致改善、producer compliance、predictor accuracy/effect 或 search utility。

## 输入与独立性

guard v2 只读取 independent structural gate、snapshot-bound accumulator summary 和 summary 内 SHA-256 绑定的
first-960 ledger。forward v2 对基线与当前 summary/ledger 各自重算，并以 receipt-only independent common-support
verification 交叉确认当前 2,755 对总量。没有 prediction matrix 输入，也没有打开 prediction pair、label、grade、outcome、
winner-orientation 或 raw archive payload。

producer A/B、non-importing verifier A/B 均逐字节一致；postformal verifier A/B 又与 formal verifier 逐字节一致。focused/
full=`4 passed` / `1113 passed, 47 warnings`。file trace 的 forbidden opens、credential filename/content hits 均为 0；
GPU/API/model-fit/base-LLM update=`0/0/0/0`。

## 固定版本与哈希

- source commit：`1b9b8365f1b2067c9ebb27c20d29b6844bc79f3a`；
- guard / independent：`2ffa91a5e10f17f31c1a79f51a69d2f4e2331353e9ac9cfab14c6c40352cd177` /
  `62f5fa00ad4535c0e6e8706daf62f5408ac4fa407506f761b42840d1c115310c`；
- forward / independent：`fca979bb912c61bb14385638069a64aefcb8a7b9bc41cb77c260d07075ea0fb1` /
  `00f8fec272705d0d5dfe072f2e0e59efa170913900249a506c829b693f102146`；
- remote formal manifest：`b1405cd4a7ae844a1150119137349672d41963296f0899778a476d923b005135`；
- postformal replay manifest：`8b90eab94987a01f981463ea3f821d5afa4e8b11271c4913c1b673f80ecb0166`。

`remote_formal_SHA256SUMS` 对应远端完整 formal 目录（含 strace，未全部收入 Git）；本目录另有独立 `SHA256SUMS` 约束
所有公开文件。四个 JSON receipt 与远端正式文件逐字节相同。

## 失败记录

前三次 setup 分别因 remote alias、未加载 proxy、nounset 下加载环境而在 fetch 前停止；随后一次普通 worktree checkout
因无关旧 LFS 对象 404，在 formal 前停止。首次真正 formal (`formal-8192016-8579-v1`) 已通过 4/1113 tests 与全部 A/B，
但无左边界的 credential regex 把目录名 `task-balance-structural-only-v2` 误报为 key，故 fail-closed、不提升。修复仅把
scanner 改成 boundary-aware 并增加正/负自检；新 commit/new output 从头全跑，得到本结果。
