# CleanDirectDecision 静态信号来源 component-OOF v2 正式裁决

日期：2026-08-21。正式状态：`STATIC_SOURCE_OOF_INDEPENDENTLY_VERIFIED_NO_NARROW_POSITIVE`。

## 1. 裁决

预注册的窄正面门未通过。parent-closed OOF 下，code-only 的 task-macro 为 0.529716，task-clustered
95% CI=[0.497905, 0.566335]，不能排除 chance；parent-clustered point/CI 为
0.520420/[0.503049, 0.537910]。相对 lineage-only，code-only 的 task-macro 配对增量为
+0.008391，task CI=[-0.031204, +0.047777]；pair-micro/parent-clustered 增量为
+0.014790，parent CI=[-0.008262, +0.037835]。两类 CI 都跨 0，且 leave-one-task-out 最小点估计
为 −0.003203。

相对 all-static，code-only 的 task-macro 增量为 −0.004693，task CI=[-0.018386, +0.011119]；
pair-micro/parent-clustered 增量为 −0.008015，parent CI=[-0.020497, +0.004262]。两类冻结的
−0.01 非劣门也都失败。故不得写“code-derived signal cannot be reduced to lineage shortcuts”，不得把
同池 test 的旧静态结果解释成代码理解。

all-static 本身 task-macro=0.534409、task CI=[0.507148, 0.563707]，micro=0.528435、parent
CI=[0.511247, 0.545622]，两类 chance 门均过。它说明 152 个 parent-closed supercomponents 上仍有弱的
联合静态信号，但本实验无法把它唯一归因于 code、lineage 或交互。该描述不升级为方法正结果。

## 2. 输入、隔离与控制

- 只使用 outer-train train+dev 5,240 pairs、28 tasks、1,711 parents；没有读取 frozen test、TF-IDF、
  semantic identity 或 prospective outcome；
- 168 个原 components 经 16 个共享 `(task,parent)` 闭包为 152 个 supercomponents；5 folds 中 endpoint、
  run、parent、原 component 与 supercomponent overlap 全为 0；
- orientation oracle=1.0；random 的 task/parent CI 均含 0.5；三个 learned arms 反对称误差为 0、覆盖 1.0；
- code/all 无 ties；lineage-only 有 275 ties。这不改变窄正面门失败的裁决。

## 3. 独立复核与封存

commit=`208e38135c0dc10d8430095a41c8008c063ff8a0`。producer×2 与不 import producer 的
full-refit verifier×2 精确一致；逐 pair/fold/task/parent/summary 最大绝对差均为 0。focused tests
8 passed，phase tests 558 passed / 25 warnings。output manifest 40/40 通过，7 个 diff/stderr 文件为空，
可写文件 0，前后 credential-shape 扫描 0。manifest 文件 SHA256=
`27257d96bdcc32417333e8786237be38d6a84fa68e145db1ecc0f8a2067acff4`。

完整只读产物：`/research/d7/spc/yzyang4/critic-static-source-oof/208e381-v2`。Git 中的紧凑证据：
`phase1/results/critic_static_source_oof_20260821_208e381/`。

## 4. 对路线的影响

这项来源审计作为诚实 benchmark ablation 保留，不再在同一 5,240 pairs 上追调 code/lineage 模型。
它没有杀死数据论文：parent-closed split、来源消融、失败门与撤回边界本身都是 Benchmark 完整性资产；但它也
不是正面方法突破。

在读取本结果前已冻结的 `TreeTransitionStatic` 是不同问题：它比较 child-only 与 parent-relative edit-shape，
并有独立的 Draft/Improve 机制分层。按预注册可执行一次；若同样失败则关闭手工 transition 特征，不回头调门。
