# Target-522 Selective Parent max-prior-step 前瞻附录：冻结复验回执

冻结 commit `0719d075d584481e72a3d67dd591a156bbaaa62b` 已在远端 fresh detached worktree 完成 outcome-blind
复验。

- protocol / producer / verifier / test / runner SHA-256：
  `81df44e9194fb194611d6ffb7f3fba6c0a3fd1d7d2c0aa1ba6be19d33f84ce87` /
  `b84894a75a4c2493aa8d79a7ca0a2afbb025bc4865408ca67c224430deea2cbf` /
  `b2368ea4cb956f9514aaa09e70e07e37b9847a840ab232782403e7b415007ee3` /
  `e81433e0d188c200097b2a4fb73158d58cb46f4020f6615a3ccaedf9678b217e` /
  `32cd4923775c03671026012ab976f0711f0d963dd675833f380e40b23e083674`；
- focused=`30 passed`；full phase1 tests=`1537 passed, 47 warnings`；
- commit changed files=`7`，filename/blob secret hits=`0/0`；
- 16-member freeze manifest 全部本地重验通过，SHA-256=
  `f6a7f53a3f3f31a96089b98c66c247340bef6e5a37bba14d96e87fc1d6ca0f6b`。

## 结果前拒绝证明

复验时 Target-522 selection `COMPLETE=false`，upstream selective formal `COMPLETE=false`。在系统调用级 open trace 下调用固定
formal runner，runner 按协议返回 `rc=1`；未来 formal output/worktree 均未创建，candidate.tsv、observed.tsv、snapshot、
producer result 或 formal summary 的 open hits=`0`。因此 frozen source 在 closure 前不能提前读取 candidate/profile 或运行
科学 readout。

既有 selection/lineage/selective watchers 没有被修改、重启或复制；本轮没有启动 addendum watcher。prospective
first-960/Target-300 values、Target-522 candidate/profile、raw senior archives 未读，无 row-level release；
GPU/API/model-fit/base-update=`0/0/0/0`。

远端只读回执：
`/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522-order-addendum/freeze-0719d07-r1`。
