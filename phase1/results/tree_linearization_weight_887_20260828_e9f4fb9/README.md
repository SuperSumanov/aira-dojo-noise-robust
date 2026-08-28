# Tree-native representation：887 provisional 正式结构证据

状态：`MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING`。

本包回答一个结果前固定的问题：在同一 outcome-blind MLE-agent snapshot 上，把 observed search fragments 保留为
unique child-parent edges，与把它们展开成全部 root-to-leaf trajectories，是否会改变 benchmark 的经验权重？答案在
预注册门下为“会，而且同时改变 task 与 physical-run 两个轴”。

## 主要结果

- 固定人口：11,906 eligible endpoints、435 physical runs、34 tasks；恢复 10,895 条 observed edges，parent-present
  fraction=`0.9150848311775576`；12 个完整性/支持门全过。
- path 展开把 10,895 条 edge 变成 26,107 次 edge occurrence；其中 15,212 次是共享前缀重复，重复质量占比
  `0.5826789749875513`。
- `0.3877007801743919` 的 unique edges 被重复；mean multiplicity=`2.396236805874254`，p90/p95/max=`4/7/144`。
- task-weight TV=`0.1603376038171571`，超过预注册 0.05；task maximum share 从
  `0.25672326755392383` 增至 `0.3858352166085724`。
- run-weight TV=`0.18894421733497543`，超过预注册 0.10；run maximum share 从
  `0.06351537402478201` 增至 `0.1158693070823917`。

因此 tree-native provenance 不是仅供可视化的附属字段：若把 root-to-leaf paths 当独立数据行，共享前缀会按其后代
leaf 数隐式重加权，并显著改变 task/run mixture。发布与 benchmark 应保留 stable node/parent/run identity，并明确区分
edge、choice-parent、run 与 task estimand。

## 复验

协议 SHA-256=`95b49fd50b75dd16fd9eefbb34557da35daa52fcecc35fce45ac89948a697feb`，source commit=
`e9f4fb9cf495d6751fb77d061095f6dca312728c`。formal focused/full=`19/1299 passed`，full 有 47 warnings；producer
A/B、非导入式 verifier A/B 与另一 fresh worktree 的 postflight A/B 均逐字节一致。

- formal receipt SHA-256：`642e9fd793950d4dfd082669df164be0781bd13847f35d6483ebd8611a136ea8`；
- independent verifier SHA-256：`11b255093055941c5747d238cc1bc00b4a3d81a7216dd6efb701da85c9a9045d`；
- formal/postflight manifest SHA-256：`d8972749b7ee7e98abcbcc85dcefc7080ad674f2bdc260d01c27c6bf8628d46a` /
  `725566a5a928764a5700d08b086c2f815f55d4240c30403bdcd3ccb3e0392961`。

`formal/` 与 `postflight/` 均是远端不可变目录的逐字节副本；各自运行 `sha256sum -c SHA256SUMS` 可验证。两轮
forbidden-open bytes=0、credential filename/content hits=`0/0`；prospective label/grade/outcome/prediction、raw senior
archive、GPU/API/model-fit/base-update 均未访问或使用。

失败史未删除：v1 在数据读取前因无关历史 LFS 对象缺失而停止，失败清单 SHA-256=
`4bad99dfb77d44e0ae8a8fe7add82851e747a901076abab24cb78eeca302fe96`；v2 的科学计算与复验完成，但封装把临时
manifest 自身纳入校验，按 `FAILED_RC=1` 拒收，失败清单 SHA-256=
`c3bfcf145bc3f452e8ea2101caa700d26713aaa718b40cf9e19a666be6f7e2a8`。v3 从测试起完整重跑，并非只修补结果文件。

## 主张边界

允许：在该固定、尚未 closure 的真实 MLE-agent snapshot 上，root-to-leaf linearization 按预声明阈值显著复制
shared-prefix edges，并同时改变 task 与 run empirical weights。

不允许：完整 source tree 已恢复；所有 trajectory dataset 都有同样幅度；我方首创 shared-prefix/tree processing；
predictor accuracy 或 search utility 已提高；语义或因果机制已证明；first-960 已闭合。

相关工作边界见 `phase1/实验记录/2026-08-28/TreeLinearizationWeight_887正式结果与防撞边界.md`。
