# Python代码提取误拒的根因与最小修复

2026年10月1日。对comparison/0930两个固定归档的检查发现：**204条被框架拒绝的响应实际包含完整、可编译的Python，原生提取器却把字符串里的三反引号当成代码块边界。** 本包提供原始记录的脱敏证据、最小复现和三个源码文件的补丁。它修复程序准入，不是新critic或analyzer的收益证明。

## 已证明的根因

原生生成算子和MLE任务入口都使用未限定整行边界的正则提取代码。例如，下列合法Python包含一个用于处理Markdown文本的字符串：

```python
import re
pattern = r"```.*?```"
def clean(x):
    return re.sub(pattern, " ", x, flags=re.S)
```

把这段程序包在正常的Markdown Python代码块内，旧算子提取结果为空；即使直接把合法的原Python交给旧任务提取器，也会被拒绝。失败发生在调用解释器之前。任务用`ExecutionResult.get_empty()`生成记录，其默认`exit_code=0`和`exec_time=0`，**不能解释为程序正常运行退出**。

补丁先原样接受可编译的完整Python；对带说明文字的响应，只识别独占一行、闭合且语言标记合格的代码块。代码块内部的字符串不被改写。两个提取入口共用规则，保留原来的语法校验和Black格式化；无闭合块、空块和无效Python不自动补全。原有多个合法代码块的拼接策略保持，不借本修复扩大语义重写。

## 真实归档的范围

| 已核事实 | 数量 |
|---|---:|
| 全部非root日志动作 | 983 |
| 原代码可解析且按新规则逐字节保留 | 779 |
| 原生generic rejection且新规则提取唯一合法完整代码块 | 204 |
| 受到影响的配置目录 | 8 |
| 拒绝记录组成的父子连通段 | 10 |
| 连通段内后继父边 | 194 |
| 日志中从这些段直接转为非拒绝的子节点 | 0 |

204条全部来自QUEST；Petfinder的402条没有该类误拒。词法检查确认204条的问题标记均位于Python的STRING token内；恢复后的程序按AST去重为56种，而不是204个独立程序，见`lexical_context.json`。QUEST按臂分别是`forets-selected`20/88、MCTS42/150、random63/170、short79/173条动作，其中分母为对应臂所有日志动作。它们不是独立样本，也不能据此比较策略的真实质量。分母、目录数和全部10段都保留在`rejection_chains.json`，不删除受影响运行来制造“干净胜利”。

10段首次至末次拒绝记录的跨度为1.4981072952777776至3.5611238025小时，中位数2.4906103305555556小时。这只是已观察的日志跨度，不是生成延迟、GPU活动时间或修复后可节省的时间。204条中的196条是Debug、8条是Improve；10个入口包含8次Improve和2次Debug。

### 独立复验状态

全量原生函数复验**983条全部通过**：204条旧函数拒绝、新函数准入，779条原已准入程序的AST保持不变；新生成端与任务端两次提取的AST逐条相同。独立算法暂时屏蔽行内反引号，调用原生旧正则后还原，再比对AST，与204条修复结果全部一致。`native_independent.json`的SHA256为`c132c23b23ba848339508fbc187945cc899c7dfa13bf5ec628b5042aa9848a4d`。

现有17项原生函数和任务入口回归已全部通过，另有18项诊断脚本测试通过。真实`step_task`的解释器调用被截获：证明原入口未到执行阶段、新入口接收到相同程序的语法树，**没有实际运行候选程序**。测试覆盖普通Python、原有代码块、行内反引号、较长外层fence、CRLF、多块旧行为、空块、未知语言、缺失闭合和无效代码等边界；不是完整Python或Markdown解析器的形式化证明。

发布后另从`d11beb748f1f1fa654a88debd03b64f6457fbdfa`精确导出公开包，在远端全新临时目录复现：清单与60例格式结果完全一致，13项原反馈分析测试、23项当前诊断测试及17项原生回归均通过。未重复读取原始归档或运行候选；回执`published_d11beb74_readback.json`明确绑定该提交，不能当作后续任何源码版本都已复现。

## 如何使用补丁

补丁位于`phase1/patches/python_fence_parser_20261001/fix_python_fences.patch`，参考学长分支commit `e385f863cb531904e611e987f7f71606796db656`，仅修改两个提取入口并新增一个共用helper。已在隔离临时仓库真正应用，并逐字节核对应用后的三个文件；不是只检查退出码。**本轮未修改学长分支或生产运行目录。**

归档记录的四个生产commit中，这两个提取器、MLE任务入口和空执行结果定义的Git blob都与参考commit一致，见`source_provenance.json`。这不证明当时没有未提交改动，也不证明历史Python和依赖完全相同。本轮原生复验使用现有环境Python3.12.13、Black26.5.1；原始回放用Python3.12.3。重新fetch的upstream `origin/main@c795d8649d30b77fa9b8c011b978bba7127507ad`也保留同类未锚定提取正则；这不是对所有issue、fork或既有修复的穷尽检查，代码提取修复本身不声称方法新颖性。

在参考版本的干净checkout内先检查再应用：

```bash
git apply --check /path/to/fix_python_fences.patch
git apply /path/to/fix_python_fences.patch
```

其他版本若有上下文变化，先看diff，不用强制应用。Windows下哈希复核应关闭临时检查仓库的自动换行转换，否则Git可能把正确补丁转成不同文件字节。本轮第一次校验因此失败，设置`core.autocrlf=false`后才通过，原生产源未受影响。

**兼容性不是无条件的。** 冻结补丁另经5种人工程序×12种包装格式，共60种组合检查；60/60符合事先声明的规则，没有新准入程序的AST偏离预期。但12例原两级提取会接受、新规则会拒绝，涉及四空格缩进围栏、行内闭合、非Python语言标记及完整块后跟未闭合块。更严格的格式要求是可观察的兼容性变化，不是性能优势，真实983条上未见回退不能推广到所有生产输出。上线前应确认生产响应遵循约定；不能静默把此补丁当完全向后兼容替换。合成检查见`contract_matrix.json`，人工例子的拒绝率没有总体统计意义，也没有触发程序执行。

## 复现与安全边界

公开包只含框架源码、人工最小复现、计数、坐标和哈希，不含候选程序、模型prompt或原始终端输出。原归档可能带凭据，不得直接上传；原始读取脚本只访问指定配置和JOURNAL成员，并先做凭据形状检查。

在仓库根目录执行，输出必须用新的路径。原始源码核验需要本地Git对象包含参考commit。原始归档复验仅限持有合法副本者。

```bash
S=phase1/scripts/comparison_0930_parser
B=phase1/patches/python_fence_parser_20261001
R=phase1/results/comparison_0930_parser_20261001
python -m unittest discover -s "$S" -p 'test_*.py'
python "$S/run_parser_regression_0930.py" --bundle "$B" --output /tmp/parser-regression-new.json
python "$S/build_parser_fix_patch_0930.py" --repo . --bundle "$B" --output /tmp/parser-apply-new
python "$S/parser_rejection_chains_0930.py" --census "$R/compiler_census.json" --numeric-trace phase1/results/comparison_0930_feedback_diagnostic_20261001/numeric_trace.json --output /tmp/parser-chains-new.json
python "$S/compiler_feedback_census_0930.py" --source /path/to/authorized/0930 --output /tmp/parser-census-new
python "$S/fence_replay_0930.py" --source /path/to/authorized/0930 --output /tmp/parser-fence-new
python "$S/verify_native_parser_replay_resumable_0930.py" --root /tmp/parser-native-new --bundle "$B" --source /path/to/authorized/0930
```

最后一项会在`--source`下建立独立的`fence-native-resumable-v2`结果目录；不修改归档，若目录已有结果则先核身份。逐记录安全回执可续验，最终983条全部核完才产生完成回执。首次非续验版因Black格式化超过600秒而超时，没有完整PASS；之后改为单CPU低优先级、1800秒分段及身份锁定续验，不更换候选或指标。计时是验证脚本耗时，不是解析性能benchmark。

## 对研究主张的实际影响

这是必须各臂共有的框架修复，不作为C臂新增analyzer的独有优势。后续A/B/C仍要检验同信息、同生成器、同完整预算下的真实质量；不能把修复旧解析bug的收益冒充反馈机制创新。

此前“204份代码AST失败”的事实应解释为**保存了说明文字与代码的响应外壳无法按Python直接解析**，而不是204份模型程序都有语法错误。继续为这些案例做LLM语法修复或训练退出成功标签都会混淆错误层次。也不能仅因共享同一bug就认为策略比较不受影响，因为各臂访问的代码模式不同。

**退出成功标签不等于quality critic标签。** 公共trace精确联结的204条误拒全部缺外部分数、valid为假、buggy为真，虽默认exit_code仍是0。学长e385f863的`cards.py`在外部分数缺失时设`label=None`，其`build_children_index`会跳过无label项；该源码路径与204条缺失状态已分别核验，见`label_route.json`。因此不能说这204条作为“高质量正例”污染了学长的critic，也不能据此解释模型容量结果。这里是丢失可执行候选及其质量反馈的风险；没有证明新补丁会产出有效提交或高分。该检查不等于复核所有历史builder模式或任何具体checkpoint的训练成员。

当前没有新候选执行、最终分数增益或已测计算节省。语法合法不保证库兼容、运行完成、提交有效或质量提高；需要在统一修复后的入口做新运行验证。研究盘续期未确认，本轮0 GPU、0 API、0模型fit，不触碰保护cohort，也不恢复已关闭的旧训练或过滤器路线。

## 旧执行状态实验的标签补充审计

对我方9月28日风险迁移实验使用的已解封9月12日四任务25个ForeTS run，按原journal哈希白名单只读检查547条记录。发现**1条Pizza Debug记录尚未进入执行器，却因默认退出码0被旧`exit_code == 0`规则赋了正标签**。这是对旧结果解释的必要限定，不是新模型实验；与学长最新十任务critic训练不是同一批数据。

240条原提案评测记录中没有该拒绝签名；其25个逐run行数与退出码0计数和原实验记录一致。受影响的Debug行出现在原36-fit研究的9折中7折训练集，进入对应repair与mixed臂，共14个拟合模型可能受此错误标签影响。这里只核训练成员，不知道预测会改变多少或向哪个方向改变；后续配平和对比研究尚未逐一追溯。不能据此解释全部负结果、宣称修正后获胜，或解释学长的容量结果。原指标没有偷偷重算，旧配方不恢复。

冻结的解析补丁对这条旧记录**仍拒绝**，因此不能把它和0930的204条行内fence误拒合并，也不能声称205条都被修复。原生参考函数来自e385f863，不表示已经证明旧归档生产环境完全一致。证据见`legacy_label_audit.json`、`legacy_one_parser_replay.json`及`legacy_training_membership.json`；三份记录各自绑定脚本，保存哈希、成员关系和布尔事实，不含原程序或提示。标签判定的5项边界测试通过。

如果预测目标是“程序真正执行后的退出结果”，未执行样本应标为未知并另记失败阶段，**不能简单把正标签翻成负标签**。若目标事先定义成整条流水线是否交付成功，才可依定义计入流水线失败；两个目标不能混用。TF-IDF词表原本由各折全部训练文本拟合，删除整行也可能改变proposal臂的表示，不能声称只有14个模型在任何处理方式下会改变。

## 后续方法检验的最小边界

本发现先解决反馈的事实来源，而不是替新方法制造分数。下一轮所有臂共用修复后的解析入口，并把“未执行”“执行非零退出”“正常退出但无有效提交”“有可用评估”分开；不得把不同阶段混成一个成功或失败标签。

在此共同基础上，B/C获得相同的执行事实、修改目标及反馈字数预算。待检验的唯一差异是：C是否把当前修改目标绑定到可核验的执行证据，再提出修改；B使用同信息普通反思。目标相关证据不足时允许返回未知，不让模型编造验证成功。框架修复、额外评估调用和额外日志不得只给C。这样的设计仍需真实任务、跨seed和全成本终评才能建立主张；本包不声称它已成立。

新颖性门同样保留：[Gome的分层验证](https://arxiv.org/html/2603.01692v3#S3.SS2)已经检查假说是否达成；[PROBE的Guidance Gate](https://arxiv.org/html/2605.08717v2#S3.SS4)已经按证据、可操作性和干预范围限制反馈。因此“对应目标”“给证据编号”或“缺证据时保守”本身不构成独特方法。下一小实验应先回答这些近邻已有机制在同信息、同总成本下是否留下真实缺口；不能先把新名字写成创新，再让少量单步收益为其背书。框架bug修复也不能承担这条论文主张。

复现旧标签审计仅限拥有原授权归档者；路径固定在脚本中，不会回退扫描其他语料。可依次运行`audit_legacy_exit_labels_20261001.py --output <new.json>`、`check_one_legacy_rejection_20261001.py --bundle <bundle> --output <new-case.json>`、`legacy_bad_label_membership_20261001.py --case <new-case.json> --output <new-membership.json>`。仅原生解析回放需要Black；三者均不加载旧模型、不读取预测或grade值、不运行候选。JSON整体字节因脚本路径外环境变化不承诺相同，固定源与逐条事实应相同。
