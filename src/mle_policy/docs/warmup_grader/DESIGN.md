# Warmup grader 实现说明

## 1. 数据流与支持范围

Warmup 从现有 `prepared/public` 中保留一小部分训练样本，把去掉标签后的输入追加到测试输入。Agent 照常训练并生成一份完整的 `submission.csv`。可信 task 按 ID 拆分提交，对原测试与 warmup 分别调用同一个上游 grader；analysis 接收 warmup 汇总分，用来检查预处理、推理、指标和提交链路。方案排序继续使用脚本自己的 CV（cross validation，交叉验证或留出验证）得分。

第一批已接入四个任务：

|任务|原训练|原测试输入|warmup|转换实现|
|---|---:|---:|---:|---|
|chaii|1,002|112|23|`warmup/converters/chaii.py`|
|TGS salt|3,000|1,000|200|`warmup/converters/salt.py`|
|dog breed|9,199|1,023|205|`warmup/converters/dogs.py`|
|TensorFlow QA|276,635|30,738|500|`warmup/converters/tensorflow.py`|

代码路径相对于 `src/dojo/tasks/mlebench/`。逐任务的数据排列、评测细节、转换步骤、风险与验证记录放在 `datasets/`。其中 `AI4Code.md` 和 `denoising-dirty-documents.md` 保留了后续任务的参考分析，尚未接入转换器。实验命令见 `RUNNING.md`。

## 2. 准备独立数据版本

入口为 `warmup/prepare.py::prepare_warmup`，输入是已经准备好的 `data/mlebench/<competition>/prepared/public`。转换输出单独放在 `data/mlebench_warmup/<competition>/v1`，源目录保持原样。

```text
data/mlebench_warmup/<competition>/v1/
  public/                     新训练数据、合并测试输入、sample、description
  private/
    manifest.json             切分记录和版本摘要
    warmup_answers.csv        或 warmup_answers.jsonl
```

默认目标数量为 `min(500, ceil(0.2 * 原测试输入样本数))`，不设固定下限。TensorFlow QA 的 short/long 两行算一个输入样本；chaii 按完整 context 分组，实际数量可能小于目标。`--count` 可指定 1–500 的目标数量，转换后必须仍有训练数据。

准备流程分为四步：

1. 读取 sample 确定原测试 ID 和输入样本数，计算目标数量；记录源公开文件的 SHA256 和大小。
2. 在临时目录执行任务转换：复制公开文件，移除选中训练标签，把输入加入测试集，把答案写入私有文件。
3. 校验合并提交 ID、训练与测试 ID 互斥、剩余训练数量；在 description 追加提交与 warmup 反馈说明。
4. 记录输出文件摘要、seed、采样方式、目标和实际数量、原测试与 warmup ID，计算版本标识，然后将临时目录重命名为正式版本目录。

已有目标目录会报错；切分参数改变时使用新版本路径。manifest 记录了公开文件清单和摘要；运行时 grader 校验 manifest 身份、warmup 答案摘要和 sample 摘要，并核对原测试及 warmup 答案 ID。

`datasets.py` 保留通用 CSV 读取、ID/图片集合校验和整组分层抽样。各任务转换放在 `converters/` 独立文件，`converters/__init__.py` 的 `CONVERTERS` 明确列出支持项。TensorFlow QA 用两遍 JSONL 流式处理，避免加载约 15 GB 的完整训练文件。

### TensorFlow QA：输入样本数与提交行数的对应

`prepare.py` 中针对 `tensorflow2-question-answering` 的分支处理的是数据组织差异。这个任务一个输入 example 对应两条预测：`<example_id>_short` 和 `<example_id>_long`。其他三个已接入任务均为一个输入对应一行提交。因此，准备流程同时维护“输入样本 ID”和“提交行 ID”，具体对应如下：

|代码位置/变量|TensorFlow QA 的处理|其他三个任务|
|---|---|---|
|`submission_ids()`|从 sample 的 `example_id` 列读取带后缀的提交行 ID，校验非空且唯一|读取 `id` 列|
|`prepare_warmup()` / `original_samples`|用 `rsplit("_", 1)` 去掉最后一个后缀，得到完整输入 ID 集合；再从该集合生成 short/long 全集，与原提交 ID 集合比对，缺少一半或后缀错误会报错|sample 行数就是输入数|
|`test_count`、`target`|以完整输入数计算 20% 和 500 上限；本机 61,476 行 sample 对应 30,738 个输入，目标为 500 个输入|直接使用 sample 行数计算|
|`convert_tensorflow()` / `warmup_ids`|按完整 JSONL 记录抽样；选中记录的标签存入私有答案，四个输入字段追加到 test，每个输入新增 short/long 两条空 sample 行|转换器按各自文件格式移动输入及标签|
|`warmup_samples`、`warmup_rows`|先校验转换器返回的完整输入 ID，再展开成两倍的提交行 ID；校验合并 sample 恰好覆盖原提交行与新增提交行|两组 ID 一一对应|
|manifest 的数量和 ID|`original_test_count`、`actual_count` 按输入计数；`original_submission_ids`、`warmup_submission_ids` 按提交行记录；`warmup_ids` 保留完整输入 ID|输入数与提交行数相同|
|manifest 的 `answers_file`|使用 `warmup_answers.jsonl`，保留嵌套 annotations|使用 `warmup_answers.csv`|

本机版本因此切出 500 个 example、追加 1,000 行 sample，新测试共 31,238 个输入、62,476 行提交。description 中的训练/测试数量也按输入计数；公开反馈的 `num_samples=500`、`num_submission_rows=1000` 分别说明这两种规模。

评分侧 `grade.py::load_answers()` 读取 JSONL 后仅保留字符串形式的 `example_id` 和 annotations；`answer_ids()` 将每个答案 ID 展开为 short/long 两行 ID，供完整提交校验和分块使用。因此同一个 example 的两条预测始终属于同一个评分分块。CSV/JSONL 的答案读取及 ID 展开是当前已支持结构的明确约定，后续接入其他多行提交任务时需要一起核对。

`prepare_warmup()` 对转换器返回的 `remaining_train_ids` 做训练/测试 ID 互斥检查；当前 CSV 转换器返回该字段，TFQA 流式转换器未返回训练全集 ID，准备阶段只校验选中输入 ID 唯一、提交行不重叠以及剩余训练数量。TFQA 依靠按行移动完整记录实现切分，源训练 example ID 的全局唯一性仍是源数据前提。

## 3. Task 与独立评分

`MLEBenchTaskWarmup` 继承 `MLEBenchTask`，复用初始化、任务说明和 prepare，使用独立的候选执行与最终评分路径。配置为 `MLEBenchTaskWarmupConfig` / `task=mlebench_warmup`；`public_dir` 和 `data_dir` 均指向版本内的 `public`。原 task、`evaluate.py` 和克隆的 `mle-bench` 目录保持原实现。

原 `validate_submission()` 会直接对原测试答案评分，合并提交多出的 warmup 行会使其失败。新路径交给 `WarmupGrader` 完成校验和分块评分：

1. 执行候选代码并取回完整提交；执行失败或没有提交时记录固定状态。
2. 检查 ID 列、空 ID、重复 ID 及完整 ID 全集。
3. 按私有 ID 集合拆为原测试和 warmup；提交行顺序不影响拆分。
4. 分别调用原 `competition.grader(...)`；其 `Grader.__call__` 执行任务自己的 `grade_fn` 并保留五位小数。`InvalidSubmissionError` 和其他评分异常均由上游记录日志并返回 `None`，按评分失败处理。
5. 写入报告，并将安全 warmup JSON 追加到执行输出的最后一个独立条目；清理提交文件和 interpreter。

任务特有的预测格式与指标由各 competition 的原 grader 处理；warmup 外层负责完整 ID 校验、拆分和报告。`grade_part()` 给 grader 传入提交和答案的副本，避免上游原地修改影响下一次评分；同时将 `None` 和非有限得分统一视为失败，保证报告可写为有效 JSON。两部分单独计分，适用于非线性或分母随样本变化的指标。

上游会把预测错误和 grader 实现异常都转换为 `None`。公开反馈统一使用 `invalid_prediction_format` 错误码，具体原因从可信进程的上游日志排查；该错误码只表示该分块未取得有效得分，不能据此断定一定是预测格式错误。日志中的异常细节、私有标签和路径不加入公开反馈。

结果目录包含：

|文件/字段|含义|
|---|---|
|`grading_report.json` / `score`|原测试分数及其阈值、排名统计|
|`grading_report.json` / `warmup`|warmup 汇总反馈|
|`warmup_report.json`|独立的 warmup 汇总反馈|
|`valid_submission`|原测试与 warmup 两部分均有效|

执行失败、缺少提交、CSV/ID/预测格式错误同样更新报告，避免残留上轮成功结果。公开反馈只含状态、warmup 分数、指标名、方向、样本数、提交行数、版本和固定错误码。

## 4. Analysis 与搜索

新增 `WarmupAnalyzeOperatorConfig`、`analyze_warmup_op` 及独立 prompt。operator 从原始执行输出的最后一项读取 task 追加的反馈，并检查字段白名单；反馈另有专用 prompt 字段，完整保留，不受普通长日志截断影响。首轮分析即可看到评分。

Prompt 要求模型对照 CV 和 warmup 检查链路问题，`metric` 始终填写脚本 CV。analysis 的解释沿用现有 debug/improve memory 传给 agent。warmup task 与 analyze 必须成对启用，`use_test_score=false`；Greedy、MCTS、Evo 初始化处检查配置，继承其初始化的搜索器也复用该路径。Greedy/Evo 的 warmup 分支等待异步分析结果，原 analyze 分支保留原行为。

`warmup_mcts.yaml` 沿用原 MCTS 的搜索参数和 draft/debug/improve prompt，替换为 warmup analyze；`warmup_greedy.yaml` 提供 Greedy 配置。两者默认使用 Minimax client，可在命令行覆盖各 operator 的模型。`_convert_: object` 保留嵌套配置的具体 dataclass 类型，确保 solver 正确识别新 analyze。

CV 决定正常节点的排序；analysis 返回 `is_bug=true` 时，节点进入既有 debug 流程。因而 warmup 会通过 bug 判断影响搜索。固定 warmup 被反复反馈，相当于额外的可查询验证集；最终实验评价使用未向模型反馈分数的原测试集。

## 5. 批量实验入口与扩展

`main_runner_job_array` 通过 `benchmark.to_cfg_list()` 构造每个任务。新增 `WarmupBenchmarkConfig` / `benchmark=mlebench/warmup`，按 `warmup_root/<task>/warmup_version` 生成 `MLEBenchTaskWarmupConfig`，并合并通用 `overrides` 和任务级 `task_overrides`。随后沿用既有 seed 展开、RunConfig 插值、配置序列化和 launcher 流程。原 `BenchmarkConfig` 继续生成普通 task。

后续逐任务扩展：在 `converters/` 添加转换函数并注册；在 `datasets/` 添加独立解释文档；补转换与评分测试；准备真实版本并人工核对标签移除、输入排列、分组和指标。准备函数只接受已注册的 competition。

### 分批接入与人工审查

每次只接入一部分经过核对的任务。任务间的数据组织、标签位置、抽样单位和指标可能完全不同，新增转换器时同时检查通用准备与评分层是否仍适用。每个任务文档需要解释原 prepare 的产物排列、原 grader 的校验与指标、具体转换步骤、已知问题及验证记录，供人工逐项审查。

TFQA 是具体例子：如果直接按 sample 行数抽 20%，就把预测行误当成输入样本；如果直接把完整 example ID 用于提交分块，就匹配不到带 short/long 后缀的预测；如果把答案写成普通二维 CSV，就丢失 grader 需要的 annotations。当前 `prepare.py` 分支分别解决数量、行 ID 展开和答案格式问题。后续遇到多行输出任务，需要检查实际对应关系，而不是直接套用 TFQA 的后缀规则。

审查重点包括：

- **样本与分组**：问答可共享 context，notebook 可共享 ancestor，图片可包含大量相关像素。抽样、训练标签移除及实际数量按任务定义核对。
- **输入与提交关系**：一个输入可能产生一行、两行或数十万行提交。20% / 500 的规则按输入计数，CSV 行数、内存和推理负担另外评估。例如 denoising 的几张图也会新增百万级像素行。
- **标签位置**：标签可能位于训练 CSV、嵌套 JSON、mask/clean 图片或文件排序中。核对公开目录内所有相关文件，同时保证新增测试输入与 sample 能对应。
- **评测行为**：阅读当前上游实现，核对 ID、列、排序、空预测、类别编码及指标聚合方式。整体指标可能按 cell 对数或像素数加权，warmup 分数直接独立计算；任务自己的校验限制写入文档。
- **验证范围**：检查可复现切分、源文件保持、标签移除、乱序/缺失/重复提交、原测试分数保持、典型正确/错误预测，以及实际文件大小和运行负担。记录已完成的机制验证与仍待人工确认的问题。

私有答案、manifest、原始训练目录和结果报告留在可信进程侧；agent 仅取得新版本 `public`。实验环境的 interpreter 挂载范围负责文件访问隔离，普通本地 Python interpreter 不提供同用户文件系统隔离。

已完成的验证包括四类转换/原分数保持测试、异常提交、报告更新、配置和 solver 解析、真实 v1 sample 评分，以及 Minimax 生成 CNN 后的 RTX 3090 链路短测。逐任务证据见 `datasets/`；回归测试入口为 `tests/test_mlebench_warmup.py`。
