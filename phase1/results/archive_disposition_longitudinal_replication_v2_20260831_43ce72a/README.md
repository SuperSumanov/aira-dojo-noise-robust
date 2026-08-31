# Archive disposition longitudinal audit v2：taxonomy-aware 强门通过

正式状态：`LONGITUDINAL_ARCHIVE_LEVEL_GATE_REPLICATED`。论文措辞应使用更保守的
**longitudinal persistence / taxonomy-aware archive validity audit**，不称独立新样本 replication。

## 结果

- exact commit：`43ce72a94dc70a4bdff07c9b5494176ff1926f15`；
- frozen observations：`dccd59d9e3fe964aabce2458647013d772070c40a120f79f9a6b02605356e855`；
- current observed/baseline/accepted/total rejected/pending=`275/128/126/21/0`；
- 21 个 rejected archives 被完整分为 structural=`13` 与 byte-alias quarantine=`8`；
- 目标结构拒绝涉及 6 个 competition，其中 6/6 同时存在 accepted archive，fraction=`1.0`，
  Wilson 95% CI=`[0.6096657121, 1.0]`；
- 相对历史 anchor 的 accepted/structural reject/alias/target-settled/overall-settled 增量=
  `48/1/8/49/57`；冻结强门要求结构 competition≥6、overall extension≥50、mixed fraction=1.0，三项均过；
- current structural rejection rate=`13/139=0.0935251799`，Wilson 95% CI=
  `[0.0554723929, 0.1534407550]`；overall rejection rate=`21/147=0.1428571429`，
  Wilson 95% CI=`[0.0953740448, 0.2085308576]`。

hash taxonomy 也精确通过：accepted unique=`126`；structural unique=`13` 且与 accepted overlap=`0`；
alias unique=`8` 且与 accepted overlap=`8`；alias registry hash 种类=`1`。aliases 没有进入结构 competition
estimand，只作为 quarantine 完整性正对照。

## 复验与安全

focused/full=`16/1848 passed`（48 warnings）；producer A/B、独立 verifier A/B 各自逐字节一致。
result/verification/manifest SHA-256：

- `58539382eb9cd82e52560b8073287e2a94043c5035e34ad2d955baa3329c104e`
- `854f81e58e9cf2aabce7a1a0edbda6f4f9696fdd6beeabd47524c1738321ab4f`
- `f5440d4dcccd6f1f6be7ec712766b18e1e842db5a48f6e8b0f91bf51b4765b7b`

独立 postflight 复验 manifest、所有 payload hashes、A/B、exact-clean worktree、只读与 symlink 门；
network/forbidden-path/credential/identity hits=`0/0/0/0`。archive payload、label、outcome、prediction value、
accuracy、utility 均未读取；GPU/API/model-fit/base-update=`0/0/0/0`。

## 失败链与解释边界

v1 在结果写出前因漏列已知 alias reason 而 fail-closed，永久记录为
`ARCHIVE_DISPOSITION_REPLICATION_INTEGRITY_FAIL`；v2 在任何结构 competition overlap readout 前冻结 taxonomy，
没有把 v1 补写成成功。

该强门是累计人口上的纵向 persistence：57 个新增 settled archives 中，只有 1 个新增目标结构拒绝；因此不能声称在一批
独立的新结构拒绝 competition 上复现。允许主张是：语料扩张后，结构拒绝仍不是 task blacklist，且 benchmark intake
能把结构无效 archive 与 byte alias 隔离成可复验的不同处置。禁止解释为 predictor accuracy、模型 scaling、search
utility、metadata 修复因果效果或拒绝率稳定。

机器主件为 `formal_summary.json`、`a/result.json` 与 `a/independent_verification.json`；B 份是逐字节复验副本。
