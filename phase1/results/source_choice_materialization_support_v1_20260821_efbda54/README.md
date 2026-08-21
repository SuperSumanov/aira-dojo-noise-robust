# Source Choice Materialization Support v1

正式状态：`SOURCE_CHOICE_MATERIALIZATION_SUPPORT_FEASIBLE`。控制 commit：
`efbda542e69484bc93b0b36fcda10d37712cc674`。

## 问题与裁决

本轮回答的是发布材料问题：0DG 的 3,001 个 status-certified source winners 中，有多少同时具备可追溯的
全 source-set candidate-code 引用，足以进入下一步 answerability-conditioned source-choice benchmark 构造。
它不是 predictor 或搜索方法实验。

两个输入在看结果前以 SHA-256 固定：3,252-row answerability census，以及旧 hurdle 正式流程留下的
721-row 纯结构 construction census。完整 source parent 继承 v11 endpoint/card closure；identity-available 的
incomplete parent 只有在旧流程已核对 journal/code presence、retained-code hash、parent/status/journal provenance
且 construction row 为 eligible 时才算 code-reference complete。本轮不重新读取 raw archive、journal 或 code bytes。

正式精确 census 得到：

- 3,000/3,252 parents 可同时提供 certified winner 与完整 candidate-code 引用，rate=
  `0.922509225092251`；
- 3,000/3,001 certified winners 可物化，coverage=`0.9996667777407531`；
- train 为 2,109/2,109，frozen 为 778/778；extension 为 113/114。唯一缺口不插补；
- 共 8,027 个 candidate slots；3,000 组中 1,521 组 source size≥3，variable-arity share=`0.507`；
- 23 个任务均有可物化 winner，其中 20 个任务至少有 20 组；最大任务是
  `spooky-author-identification`，602/3,000=`0.20066666666666666`；
- train/frozen parent-hash overlap=0，physical-run-hash overlap=0。

13 个冻结材料门全部通过，`materialization_s1_authorized=true`。

## 解释边界

允许主张：当前 failure-aware Decision Corpus 已经不只是能回答 3,001 个 source-level choice sets；其中 3,000
个还能由既有审计链支持为全候选代码引用完整的 benchmark groups。该结果授权下一步构造
answerability-conditioned train inputs 与 sealed frozen evaluator。

禁止主张：本轮没有直接重读或重新发布 code bytes，因此这里只能称 `candidate_code_reference_complete`；S1 仍须
逐条物化并重新核验 code hash、parent/run/task 与 candidate 数。该结果不证明整个 v11 是 complete choice-set
dataset，不是 listwise 方法、predictor accuracy、search utility、prospective effect 或算法 novelty。传递关系也不是
logged comparisons。结果是冻结语料的精确 census，不使用 iid CI。

## 完整性

- producer×2 与不 import producer 的 verifier×2 均逐字节一致；
- independent verifier 状态为 `INDEPENDENT_SOURCE_CHOICE_MATERIALIZATION_SUPPORT_VERIFIED`；
- focused=`7 passed`；完整 phase tests=`686 passed, 25 warnings`；
- forbidden scientific path、secret filename/content、worktree drift 与正式可写文件均为 0；
- GPU=0、API=0、base LLM update=0；
- 正式只读远端产物：
  `/research/d7/spc/yzyang4/source-choice-materialization-support/efbda54-v1`。

关键 SHA-256：

- `summary.json`：`5ab474bd061f7f8845a19d1cefd5023fc9e2a0e5a1b45d4d93842fb62759c303`；
- `per_task.csv`：`85468fe45550a2542f6e848dcff1c7cccc3aa303e35c4ddcbb87dc69f62d5697`；
- `independent_verification.json`：
  `93e6faf066e61e4ff38cbe026447a0fbf13ef1d3eb17f681997ee57b70bdca63`；
- 回传的远端 `SHA256SUMS`：
  `26dae1d44cf5da7c6bd428bd0adef568bb740e72e51496b23c7ed250ed94f013`。
