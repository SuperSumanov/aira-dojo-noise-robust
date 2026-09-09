# ForeTS：首轮真实收益怎样读出、怎样决定下一步

2026-09-09；探索读出说明，不是新GPU/API批准，不是预注册确认或新方法首创声明。
方向为现成critic的真实e2e选择收益；沿用既有2任务×2seed×2臂，不新增训练、模型扫参或旧多保真路线。

## 1. 优先验证的正面假设

critic即使不能精细排出所有siblings，也可能通过避开较差候选，提高有效提交率或最终解质量。
这是假设，不是已有证据。先按学长ForeTS现有top-2中选1与全池随机选1比较，保持每批候选/执行规则相同；
不在看完结果后把top-2改成top-1来挽救同一轮。无需先重训critic，不要求把来源不完美的旧模型包装为最佳模型。

## 2. 最终成绩的唯一正确含义

当前solver配置use_test_score=false。最终解仍由原solver返回的best_node确定；本轮不改变选择规则。
要报告的是这个节点metric.info['score']中的外部评分，而不是metric.value的自报/分析分，
更不是从所有节点外部分数事后取最大值。后者相当于增添了一个知道评测结果的选择器。

已验证实际结果出口缺陷：main_run.py把标量传给字典日志接口，当前pandas/JsonLogger会将它规范化成空对象，
保存空EVAL事件而不报错。0015只改这一处，记录{'score':fitness,'selected_node_id':best_node.id}。
实际_main函数及真实JsonLogger的定向检查覆盖：选中解不同于最后执行解/自报分、合法0分、无有效解。
task/solver是人工替身，未运行真实模型或任务；修复不是收益证据。

不要用results_output_dir/grading_report.json代替最终结果：evaluate_submission每次覆盖此文件，
它可能对应最后一次执行而不是最后选中的节点。正式消费json/eval.jsonl的score及selected_node_id，并与运行身份关联。
无EVAL事件可能是无解、超时、导入/服务错误或结果丢失，不能单凭缺事件猜成某一种原因。

## 3. 成绩方向、配对与失败

已仅读取远端安装的MLE-bench公开config.yaml/grade.py，未加载答案或运行评分：

|任务|原始指标|正向差值定义|
|---|---|---|
|leaf-classification|多分类log loss，低好|random分数减critic分数|
|spaceship-titanic|accuracy，高好|critic分数减random分数|

两指标不可直接平均。保留8条run记录与4组任务/seed配对，逐任务展示两个seed差值、有效提交及成本；
不能把正负号统一后就把log loss和accuracy混成一个“平均提升”。

每个计划run均保留：实际代码/配置版本、任务/seed/臂、运行状态、最终有效性、选中节点/外部分数（缺失用null）、
墙钟、分配GPU时、初始化份额、API实际用量/是否未知、失败简述。API故障不当critic排序失败，但也不从总成本和运行完成率中删掉。
只在两臂均有有效最终评分时计算该组分差，并同时显示完整4组的覆盖；条件有效分差不能冒充全体收益。
超时保留下来的最后一次grading report不自动升级为最终选择。无提交不填0分，因为0对log loss恰好是最优值。

## 4. 哪种收益可以主张

首轮仍是两臂同2GPU分配（1执行卡、1critic卡），随机臂闲置的critic卡也计费。
因此即使胜出，也首先支持“在这套固定资源/候选生成机制下，使用critic的选择有价值”，
不支持“比把第二张卡投入更多随机搜索更省算力”。后一问题需要单独批准的资源重分配强基线，不能偷偷混进原两臂。
模型加载/暖机单列但不从整轮实际费用抹掉；已有critic训练成本未知，不能给出包含训练摊销的总成本优势。
同执行次数只是辅助，主要同时看最终解质量、有效率、实际时间/GPU分配/API用量。

## 5. 首轮之后怎么决策

- 两任务、两seed的有效配对都同向，且没有有效率/成本明显退化：作为扩大任务与seed的投资信号；仍不是论文确认。
- 有效配对不足、频繁端点故障、多数run未完成：先解决可执行性，不据此选择胜者，也不更换seed挑好结果。
- 几乎所有critic值相同：检查真实输出饱和/排序支持，再决定是否另立数值表示修订；当前验收只诊断，不自动换打分方式。
- 覆盖充分但两任务方向不一致或不改善：先看生成/执行/critic耗时和失败分解；不立即扩大模型或恢复旧多保真。

4组配对即使假设相互独立且全部同向，双侧符号检验最小p也只有0.125；实际任务只有2个，泛化证据更弱。
所以这8run的价值是快速决定下一步投哪里，而不是给一个看似精确的顶会成功率。

2026-09-10更新：12892已经完成，不再重复验收。OpenRouter安装及之后的公开人工输入端点检查仍未完成。
实际8run配置与协调入口见FORETS_E2E_CAMPAIGN_20260910.md；准备完成不代表已运行，实际资源与API矩阵仍须明确。

## 6. 只读汇总入口（等待真实e2e产物，不是启动器）

`forets_e2e_readout.py`接收显式development manifest和隔离开发根目录，不搜索历史目录、不运行grader/模型、
不读中间候选或grading_report。输出runs.csv、pairs.csv和summary.json；缺分在CSV留空、JSON保留null。
全部8个计划run必须在manifest里，不能先删除失败run再汇总；未开始的run仍保留缺项。

manifest顶层：schema=1、role=forets_e2e_development、source_tree=实际实验40位Git tree、runs=完整8项。
每项含run_id、task、seed、policy、run_dir、process_summary、config_sha256。
两个路径均相对同一隔离开发根目录；run_dir中的固定读取位置为json/eval.jsonl，process_summary指向该run的有界进程summary。
源码/配置SHA是**调用者声明**，读出工具不会凭它们宣布配置公平性获证；实际配置需在运行侧核对。禁止用占位SHA作为真实实验记录。
不能以此入口读取first-960/Target-300/Target-522；role标识不是数据来源或授权的独立证明。

调用方式：

```text
python -B phase1/forets_e2e_readout.py --development-root <隔离开发根目录> --manifest <明确列出的8run清单.json> --output-dir <尚不存在的汇总目录>
```

只有单一合法最终EVAL且有界进程started=true/status=completed/returncode=0，才进入有效配对。
进程失败但已写出的最终分仍保留在final_score_observed，不悄悄删除；不进入条件有效分差。
重复/残缺/非有限事件不自动选最后一个或最好一个；缺EVAL只记录缺失，不猜测是无解还是服务故障。
每任务保留两个seed、方向统一的原始分差、中位数和样本标准差；只有一个有效配对时标准差为null，而不是0。

这里只汇总进程秒数及未知项计数，**尚不计算分配GPU时、加载摊销或API费用**。进程完成不等于Slurm分配已结束。
真实完整报告仍须补调度器分配账及API实际用量，不能把本工具作为成本获胜或统计确认的自动裁判。
入口只补齐现有读出规则；未改变两臂搜索策略、生成器、预算或默认关闭的省critic调用开关。
