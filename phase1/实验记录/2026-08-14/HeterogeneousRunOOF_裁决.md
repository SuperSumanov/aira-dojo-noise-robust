# Exact-same-pool heterogeneous OOF 裁决

日期：2026-08-14。对应 outcome 前协议：`HeterogeneousRunOOF_预注册.md`；科学运行 commit：
`385a5e59e40125e75fab01176f23387c0b5ec53f`；协议：`heterogeneous_oof_v11_discovery_v1`。

## 冻结裁决

正式状态为 **`VERIFIED_DISCOVERY_NO_UNLOCK_NO_ENSEMBLE`**。producer 与不导入 producer 的 verifier
分别从锁定输入拟合 5 个 physical-run outer folds，结论一致。`frozen_read=false`：三份论文冻结 pair
文件始终没有被打开。

| arm | pair accuracy | complete-parent top-1 | parent-equal gap utility |
|---|---:|---:|---:|
| fixed frozen global | 0.5038705137227305 | 0.44710048694112436 | 0.5105066477670084 |
| operator-only LR | 0.5000000000000000 | 0.44122030396930795 | 0.5000000000000000 |
| static LR | 0.5186488388458832 | 0.46038069942452414 | 0.5186718032549540 |
| static GBM | 0.5008210180623974 | 0.4501992031872510 | 0.5060517769583547 |
| char-TFIDF LR | **0.5219329110954727** | **0.4674634794156706** | **0.5310468507329235** |
| label-free equal-rank frozen+TFIDF | 0.5110250996950504 | 0.45685406522059907 | 0.5188913180809154 |

char-TFIDF 是本轮最强 arm。其 run-macro pair accuracy 为 0.5866967034927386，95% CI
[0.5531680059666031, 0.6197497050943016]；task-macro 为 0.5517077051681596，95% CI
[0.5100268056827233, 0.6007455714540130]。这允许写成“执行前代码文本含有弱但跨聚类可见的排序信号”，
但不等于真实 sibling 选择已经可用：20 个有支持任务中只有 11 个不低于随机，比例 0.55。

相对 fixed frozen anchor，char-TFIDF 的 top-1 微平均增量为 +0.02036299247454626；run/task 95% CI
分别为 [0.014048909411889906, 0.10627524841199303] 与
[-0.017883322107708047, 0.10187640003771506]。utility 增量为 +0.020540202965915178；run/task CI
分别为 [0.01118441179364102, 0.09809233556028082] 与
[-0.021890025583021465, 0.09611480070870171]。两项 task-clustered 区间均跨零，且 absolute top-1
未达到 0.50、utility 未达到 0.55，因此 primary unlock 明确失败。

## 互补性解释边界

char-TFIDF 与 anchor 的 pair disagreement 为 0.4468684025334272；weighted parent rescue/harm 分别为
0.2244355909694555 / 0.20407259849490925。不可实现的 oracle-union top-1 为
0.6715360779105799，oracle headroom 为 0.20407259849490927。它说明错误确实不同，但不能当成可部署
ensemble：char-TFIDF 的任务一致性门失败，且 utility task-CI 下界 -0.021890025583021465 低于冻结门
-0.02；其余 base 也没有通过全部门。因此不得在同一 OOF 行上事后训练 stacking，也不另开权重网格。

label-free equal-rank arm 的 top-1/utility 增量只有 +0.009753578279474692 /
+0.008384670313907017，未达到其独立证据门；不能替代 primary。

## 完整性、资源与归档

- 精确样本为 4,263 pairs / 333 physical runs / 23 tasks / 2,293 parents / 2,259 complete parents /
  5,499 endpoints；五折 physical-run overlap 为 0；
- 所有输入 SHA、coverage、orientation oracle=1.0、随机对照 0.5036359371334741、训练收敛、禁止字段、
  post-execution feature=0 和 train/held 三层隔离门均通过；
- outcome-free smoke 后，producer 用时 754.2702545728534 秒；verifier 重新拟合全部 20 个模型，二者
  rc=0；0 GPU、0 API、底座权重更新=0；
- producer summary SHA-256：`2b804642e420b1313e10bc10f653db7b32bce25bbd8419e9918f78527e740859`；
- OOF predictions SHA-256：`fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45`；
- 30 个 manifest payload 全部通过 SHA 校验；高置信密钥文件与可疑文件名均为 0；
- 完整包 SHA-256：`a96e41b9f72c56c49b9af60ed1eead0d1b6daf21efe365a0f1a732590fc5eae4`，
  1,119,807 bytes。

## 下一步

当前 sparse patch、global frozen linear、task-conditioned/top-centered linear 以及 static/char-TFIDF
nested ensemble 四条低容量方法线到此关闭。下一步不再替换一个静态特征刷分，而转为 benchmark 主线的
**pair-graph intervention**：固定同一 OOF endpoint 分数与 endpoint universe，仅改变全局随机、
gap-matched 和真实 sibling 三种配对图，分解表观准确率中由 gap 分布和真实决策拓扑造成的膨胀。
该审计先只用 train OOF，不读取论文 frozen；任何确认性外推另等机制冻结后的新 physical runs。
