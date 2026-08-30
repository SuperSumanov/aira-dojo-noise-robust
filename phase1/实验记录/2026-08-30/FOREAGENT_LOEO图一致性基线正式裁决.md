# FOREAGENT target-edge-excluded 图一致性基线：正式裁决

## 结论

正式 v5 的预注册分类是：

`NO_DENOISING_GAIN_MODEL_COMPARISON_REMAINS_STABLE`

因此不能声称图一致性提高了固定 LLM 裁判的任务级准确率。它给出了一个较窄但可用的正结果：在相同历史公开
18,381-pair grid 上，图修正后的 DeepSeek−GPT task-macro 差异具有正的 task-clustered 95% CI，且 26/26
leave-one-task-out 保持正号；raw majority 的同一比较 CI 则略跨 0。这个结果应定位为 Predictor Benchmark 的
graph-aware robustness baseline，而不是新算法、通用 judge denoising 或 prospective critic 提升。

## 冻结问题与方法

- 输入：156 个固定 source files、110,620 行 primitive；26 tasks、18,381 common finite pairs、894 vertices。
- 每个 model×task×edge 的三次判断先编码为 mean signed flow。
- 对目标边 `e`，使用闭式 Hodge least-squares LOEO：`(fitted_e - h_e*y_e)/(1-h_e)`；目标边本身不进入预测。
- bridge 或数值零预测回退 raw triplicate majority，得到 full-coverage hybrid。
- truth 只在 label-free projection 后用于评分。
- primary：equal-task task-macro `hybrid−raw`；20,000 次 task bootstrap；禁止 pair-IID inference。
- 正门在结果前固定：pair coverage≥0.90；至少一个模型 task-macro gain CI 下界>0；两个模型 point gain 均非负。

## 正式数字

| 项目 | DeepSeek | GPT |
|---|---:|---:|
| LOEO pair coverage | 0.9914585714 | 0.9927098634 |
| raw majority task-macro | 0.6094236880 | 0.5834301655 |
| hybrid task-macro | 0.6128439428 | 0.5819708565 |
| hybrid−raw task-macro | +0.0034202548 | −0.0014593090 |
| task-clustered 95% CI | [−0.0043703960, +0.0099193214] | [−0.0103567258, +0.0067942615] |
| LOTO positive | 26/26 | 1/26 |

两模型比较：

- raw DeepSeek−GPT task-macro=`0.0259935224`，95% CI=`[-0.0002093901, 0.0570976139]`；
- hybrid DeepSeek−GPT task-macro=`0.0308730863`，95% CI=`[0.0067339847, 0.0593877218]`；
- hybrid LOTO=`26/26` 正号。

注意：DeepSeek 的 pair-micro gain CI 为正，但 primary task-macro CI 跨 0；不能用 pair-micro 替换预注册 primary。
GPT 的 task-macro point gain 为负，因此“两个模型均不退化”门也失败。

## 可写与不可写

允许：

- 在固定 public grid 上，target-edge-excluded graph projection 具有约 99% pair coverage；
- 它没有建立单模型 task-macro accuracy gain；
- graph-corrected DeepSeek−GPT comparison 在 task bootstrap 与 26/26 LOTO 下更稳健；
- 这是 benchmark/audit 中值得保留的强比较基线。

禁止：

- “图一致性普遍提升 LLM judge 准确率”；
- “我们首创 topological/transitivity denoising”；该方向已有 Hodge ranking、non-transitivity 与 2026 TCR 等直接先例；
- “前瞻验证 critic/search utility”；本实验未读 prospective sources；
- pair-IID 显著性、candidate-level 泛化或把该结果当主线效果确认。

## 完整性与复验

- exact commit：`942957757fd0c8464b1670ab3e35da64f4cccebf`；
- formal root：`/research/d7/spc/yzyang4/foreagent-loeo-graph-denoising/formal-9429577-v5`；
- preflight=`13/13`，focused=`16 passed`，full phase1=`1789 passed, 48 warnings`；
- producer A/B 与 verifier A/B 分别逐字节一致；
- 独立 verifier 使用 opposite orientation + grounded reduced-Laplacian inverse，检查 45 个数值字段，最大差=`0.0`；
- result/verification/SHA-manifest SHA-256：
  `b00ab6b7...1e96b` / `a6912890...c524` / `a3453efa...3eee0`；
- forbidden trace、network、credential filename/content、symlink、sealed writable path 均为 0；
- prospective/confidence read=`false/false`，GPU/API/model fit/base update=`0/0/0/0`。

## 失败链（全部保留）

1. v1：无关历史 LFS object 缺失，tests 前退出，0 result；
2. v2：bare repository pytest 误收集旧 CLI/integration，focused 9 后退出，0 result；
3. v3：已公开 raw reproduction 的 18ε/13ε 合法 roundoff 被旧 `2e-15` 门误杀，图投影前退出，0 result；
4. v4：A/B+verifier 已完成，但 zero-network grep 在 `pipefail` 下误杀，未写 `COMPLETE`；仅做结构/哈希复查，不读 outcome；
5. v5：以 fresh commit/root 重算，全部门通过后才揭读并裁决。

## 对论文主线的作用

这不是新的主方法突破，但补强了“Predictor Benchmark + Audit Protocol”的正面贡献：pairwise judge 输出具有关系结构，
headline predictor/model comparison 应报告 raw 与 graph-aware robustness view；图修正可能不提升每个 judge 的绝对准确率，
却会改变比较不确定性。主线仍是 outcome-blind Decision Corpus、冻结 predictor escrow 与未来 cohort，不因本历史支线改线。
