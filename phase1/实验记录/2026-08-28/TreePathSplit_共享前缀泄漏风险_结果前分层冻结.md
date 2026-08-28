# Tree path split 共享前缀泄漏风险：结果前分层冻结

日期：2026-08-28

固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`

## 为什么这是当前主线，而不是恢复旧方向

当前论文容器是 Decision Corpus + Predictor Benchmark + Audit Protocol。我们已经正式证明，同一 observed forest 若按
root-to-leaf paths 线性化，会把 10,895 条 canonical observed edges 展开成 26,107 个 path-edge occurrences。
这一步继续回答 benchmark release 最直接的问题：如果下游用户把这些 path records 当独立样本随机切分，训练集和测试集
会共享多少完全相同的 canonical edge；按 fragment 或 physical run 分组能否把这种 exact crossing 降为零。它不训练模型、
不读 outcome，也不恢复 HCE、多保真、Probe、score-channel effect 或 lookahead。

## 时间顺序与已见信息

这不是从零开始的预注册。上游 multiplicity histogram 已经公开，我在冻结本文前探索性代入了固定 80/10/10 path split：

- 3,599 条 paths 固定分成 train/validation/test=`2,879/360/360`；
- train-test 共享 canonical edge 的期望数约为 `1291.4019805907681`，占全部 canonical edges
  `0.11853161822769785`；
- 在 test 中出现的 unique canonical edges 里，与 train 共享的“期望之比”为
  `0.63841797380705656`；
- test path-edge occurrence rows 中，同一 canonical edge 预计也在 train 出现的“期望之比”为
  `0.71072159960645032`。

这些数是已发布 histogram 的确定性后验推论，不能称新发现、独立确认或结果前通过。真正尚未计算、从本 commit 起冻结的是：
匿名 task/run/fragment profile 的 breadth 与 anti-dominance，以及独立实现能否逐项复算 exact combinatorics。

## 固定概率模型与 estimand

在所有把 3,599 条 path records 分配给固定大小 train/validation/test 的方案上均匀取样，但不实际抽 seed。对 multiplicity
为 `m_e` 的 canonical edge，若集合 `S` 有 `s` 条 paths，则：

`P(edge 的全部 m_e 条 paths 都落入 S)=C(s,m_e)/C(3599,m_e)`。

因此 train-test 同时出现概率为：

`1 - C(N-n_train,m_e)/C(N,m_e) - C(N-n_test,m_e)/C(N,m_e) + C(n_val,m_e)/C(N,m_e)`。

主指标是 test occurrence contamination ratio of expectations：预计落入 test 且同 edge 至少有一个 train occurrence 的
path-edge rows，除以预计 test path-edge rows。另报 expected shared unique edges、canonical overlap fraction、unique-test-edge
ratio of expectations。所有算术用 exact rational；“ratio of expectations”不得误写为随机 ratio 的 expectation。

## 尚未见数值的强正门

全局 test-occurrence ratio≥1/2 只是已见数值的 integrity floor，不算新证据。真正的新门是：

1. task 中至少 1/2 的 conditionable groups 达到 ratio≥1/4；
2. physical runs 中至少 1/4 达到 ratio≥1/4；
3. 最大匿名 expected-contaminated-occurrence contribution share：task≤2/5、run≤1/5。

task/run 两轴全过才允许分类 `BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK`；单轴只写对应 one-axis；其余只写 global expectation
without broad support。fragment profile 只作描述，不能 rescue。按 fragment 或 physical run 分组时，每条 canonical edge
只属于一个组，因此 exact cross-split edge overlap 必须为 `0/1`，作为正控式 remedy certificate。

## 13 项 preflight

1. question：随机 path-record split 的 exact shared-prefix crossing 与跨组广度；PASS。
2. estimand：固定大小均匀分配下的 exact expectation 与 ratio of expectations；PASS。
3. inputs：固定 887 snapshot、tree linearization 与 tree-native 两份 hash-bound receipts；PASS。
4. split/leakage：只读 blind structure；禁止 label/outcome/prediction；PASS。
5. controls：all-multiplicity-one、手算两分支、小 N 穷举、invalid sizes、cross-fragment/run、hash drift；待实现后必须全过。
6. support：固定 3,599 paths / 10,895 canonical edges；conditionable task/run 至少 15/150；PASS。
7. randomness：不抽样；exact combinatorics，`PYTHONHASHSEED=0`；PASS。
8. inference：无 p-value/CI/accuracy/effect；按固定阈值描述性分类；PASS。
9. cost：CPU-only，预计低于 0.5 CPU·h；GPU/API/model-fit/base-update=`0/0/0/0`；PASS。
10. resume：唯一 formal root，失败不写 COMPLETE，不覆盖既有输出；PASS。
11. environment：公开精确 commit 的 fresh detached no-smudge Linux worktree；PASS。
12. security：basename 白名单、file trace、credential scan、identity-free aggregate only；PASS。
13. promotion：只有 producer A/B、non-importing verifier A/B、focused/full、trace、安全与 manifest 全过才发布；PASS。

## 防 scoop 与主张边界

[Tree Training](https://arxiv.org/abs/2511.00413) 已明确指出把一棵 agent tree 拆成独立线性 branches 会重复 shared-prefix
计算；一般 grouped split 与 parent-inherits-split 也不是新思想，例如 InstructGPT 按 user ID 切分，[RAG-Safe](https://proceedings.mlr.press/v318/salinas-medina26a.html)
让所有 paraphrases 继承 original sample 的 split。故不得声称首次发现 shared prefixes、首次提出 grouped split，或仅凭 exact
overlap 推断模型指标被抬高。

可守贡献限于：在真实 Python MLE-agent observed forest 上，以 physical-run provenance、exact fixed-size combinatorics、
匿名 breadth/anti-dominance 和 executable release contract 量化这一风险，并证明 tree-native grouped release 可兼容阻断 exact
canonical-edge crossing。它不覆盖 semantic clones，不证明完整 source tree，不产生 predictor effect/search utility，且当前
仍是 435/960、closure=false；最终 closure 后必须按原协议重签。

## 结果前实现回执

在真实 task/run/fragment profile 运行前，exact producer、未 import producer 的独立 falling-product verifier 与测试已完成：

- producer SHA-256：`c91bcb07cb1f4690b32425096bf029019033d72959b69f36aad3a5ba7c22ac0c`；
- verifier SHA-256：`974adb65b9a3da9ee9afc5650053995dd2565745158a14ec2730729a4298e414`；
- tests SHA-256：`51465ea7d97e18df3fea5f1d15faba7790cfcadd2b89b76557d5f0b26eea6b03`；
- 新 synthetic/exhaustive=`22 passed`；连同相邻 tree 回归=`92 passed, 2 skipped`，两个 skip 均为 Windows
  symlink 权限边界。

覆盖包括小 N 全分配穷举、all-multiplicity-one 零控、两分支手算、producer/verifier byte-equivalent aggregate、breadth/
anti-dominance 不可 rescue、hard-gate precedence、cycle/cross-run/tamper/hash-timing negatives。此时没有调用真实 887
population，故尚无新的匿名 breadth、贡献集中度或最终分类。
