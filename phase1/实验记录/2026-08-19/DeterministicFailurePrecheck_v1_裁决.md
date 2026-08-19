# Deterministic Failure Precheck v1：裁决

## 复现

- 结果前 commit：`863a3b0c33784a00da7e6cc3614e5b8d65df5a1e`；
- 完整测试：`389 passed in 36.84s`；
- producer 双跑逐字节一致；summary SHA256=
  `3b738ea56f11b80cc40375bd669cd4fd78310f1baade3679ec75bb1c73547b54`；
- 独立 verifier 两次均通过；verification SHA256=
  `2a02170db3f37e2cf53b609307ff3fb3989a54e550021f03de96080f8f450f33`；
- numeric grade/raw-code output/frozen code/GPU/API/底座更新：0/0/0/0/0/0。

## 结果

在 494 pairs / 13 tasks / 126 runs 上：

- failure caught=`1/494=0.0020242914979757085`（冻结门≥0.05，失败）；
- success false rejected=`1/494=0.0020242914979757085`（冻结门≤0.01，通过）；
- balanced-pair rejection precision=0.5；paired net=0.0；
- task/run-clustered paired-net CI 均为 `[0.0,0.0]`（冻结门 lower>0，失败）；
- caught failure tasks=1（冻结门≥6，失败）；
- 唯一 catch 与唯一 false reject 都来自 12-pair 的 `denoising-dirty-documents`，原因均为
  `REJECT_NO_ARTIFACT_WRITER`；没有 `REJECT_SYNTAX`。

## 裁决

固定为 **`INSUFFICIENT_DETERMINISTIC_PRECHECK_FEASIBILITY`**。旧 494 对上不再增加 writer sink、改 AST
规则、查看错误代码后做 v2、筛任务或降低门。

机制含义是：这些 evaluator-verified execution failures 几乎都不是静态语法/表面 submission contract 缺失；它们
主要发生在代码已经“看起来完整”之后。这个结果支持把 benchmark 的难点描述为 execution-semantic，而不是声称
静态预检有方法收益。该实验是 retrospective，不能产生 search utility 或跨 agent 泛化主张。
