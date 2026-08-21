# Decision Observability Funnel v1：结果前冻结

日期：2026-08-21。状态：`PREREGISTERED_BEFORE_NEW_FUNNEL_TOTALS_READ`。

## 问题与输入

当前 release 已确认 3,252 个 source parents 中存在 task-conditioned child retention，但尚未把 child-level
censoring 对 pairwise decision opportunity 的组合放大单独量化。本审计只读已经双重验证的 `per_parent.csv`，
SHA-256=`75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`；不得读取 code、numeric
outcome、pair orientation、prediction、prospective vault 或 raw archive。

每个 `(role,task,run,parent)` 固定四层漏斗：

1. source child slots：`source_declared_size`；
2. raw cards：`raw_card_child_count`；
3. finite candidates：`finite_card_child_count`；
4. published decision graph：`unique_edges`。

相应 pair capacities 固定为 `C(n,2)`。三段 pair loss 必须严格可加：

- source→raw：`C(source,2)-C(raw,2)`；
- raw→finite：`C(raw,2)-C(finite,2)`；
- finite→published：`C(finite,2)-unique_edges`。

最后一段是 release projection，不得写成 execution failure；前两段也只按字段名描述，不能把未逐身份归因的缺失
全部称为 execution error。已知 893/902 recovered statuses 为 execution error 只能作为独立证据引用。

## 冻结 headline 与门

headline 是完整 release census 的 source→finite pair-capacity loss share，与 source→finite child loss share 的差。
同时逐 role、逐 task 报告所有整数分母、retention、decision-parent survival 和 published-edge coverage；不做抽样
置信区间，也不把 parents 当 IID。

`VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION` 只在以下全部成立时允许：

1. 全部行满足 `finite≤raw≤source`、published endpoints≤finite、`unique_edges≤C(published endpoints,2)`，
   三段 loss 非负且精确相加；
2. source→finite pair loss share≥0.15；
3. pair loss share − child loss share≥0.03；
4. 至少 10 个 tasks 各有 source pair capacity≥100；
5. 其中至少 8 个 tasks 的 pair loss share严格大于 child loss share；
6. train 与 frozen 两个 roles 各自都满足 pair loss share严格大于 child loss share。

支持任务不足则 `INSUFFICIENT_TASK_SUPPORT_FOR_FUNNEL`；支持足但任一 material 门失败则
`VERIFIED_FUNNEL_NO_MATERIAL_COMBINATORIAL_ATTRITION`。不得结果后改阈值、按任务删行、用 parent-equal 替换
完整 release totals，或把 published projection 与 execution censoring 合并追求大数字。

## 13 项预检

1. 方向：Decision Corpus / D&B 数据测量；不是旧 HCE、TD、probe 或多保真。
2. 问题：child availability 的损失是否在 sibling pair capacity 上产生预定幅度的组合放大。
3. 唯一输入：固定 SHA 的 source-aware per-parent 表；3,252 行与 role counts 必须一致。
4. 单位：parent 为计数单位，task/role 只作完整 census 分层；不作伪 IID 推断。
5. 分母：所有 child、pair capacity 与 published edge 的整数分母必须输出。
6. 泄漏：禁止 code、outcome、orientation、prediction、prospective/raw archive 路径。
7. 完整性：逐行单调关系、容量上界、三段可加恒等式先于任何结论。
8. 主张：只允许 material combinatorial attrition；不允许完整 choice set、MAR 或缺失候选质量。
9. 负控：无 child attrition 的合成数据必须拒绝 material 状态；edge 超容量必须 fail closed。
10. 复现：producer×2、独立 verifier×2、精确 commit/input/protocol SHA、byte-identical。
11. 测试：focused + 全套 phase tests，tamper/rehashed-summary 反例必须失败。
12. 安全：syscall forbidden-path=0，两类秘密扫描=0，正式产物只读。
13. 资源：单线程 CPU，预计正式计算含全回归少于 20 分钟；GPU/API/base-LLM update=0。
