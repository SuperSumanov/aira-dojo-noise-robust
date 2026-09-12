# 当前交接：13124已闭合且数值通过，准备同版本seed15

## 最新现场（覆盖下文早先运行观察）

- 2026-09-12 02:48:17 UTC：13124 COMPLETED，四槽正常结束、12池完整，3个final独立原submission数值一致。
  Leaf random0.50877 / critic1.42793（critic差）；Space random缺失 / critic0.81839。不得补零或称稳定整体收益。
  两critic的step1确实改选不同代码；两个末端宽1池正确旁路。0.8955555555555555 GPUh。
- session closeout已成功；independent-context-verification.json已成功，SHA93313ffb7777a549397c08d98716b2373a38224b2d28c7b473e0510fb61571b2。
  不再对13124运行closeout/verifier/submit。只读PTY23406已结束。
  verifier首次因框架添加validity_feedback而拒绝；已对照固定mcts.py限定该单一已知注释，其余report字段仍精确匹配。
  另补齐forets_closed_pool_20260911间接依赖，未改实验/主分/提交；细节见FORETS_SMALLPOOL_S14_RESULTS_20260912.md。
- 当前账仍seed14根ACTIVE：284行、结算1.007137235、责任2.407137235USD、未知2；不要再次运行旧activate。
  新seed15 facts已在stage/seed14-parent-facts.json一次生成，ledger SHA d9f9109e4522378d342be117efb2497d39d749a7f13f5f35b144df3d39d82aba。
  forets_context_s15_repeat已完成条件门：两原任务均复验、只seed与顺序改变，最多新增5GPUh/3.50USD且原总10USD不重置。
  本地codex_tmp/forets-context-s15-artifact-20260912已创建，正在收取parent-facts与seed14公开结果（SCP PTY92106待确认）。
  下一步commit含实际结果→artifact→新stage build→实际inspect/全宽度检查→activate→route/catalog→单次submit。
  seed15尚未build/activate/API/GPU，禁止把准备说成开跑。

早先运行现场：2026-09-12 01:33:35 UTC / 香港09:33:35。
恢复顺序：fetch → CURRENT_DIRECTION最新0L171 → 本文件 → 现场。用户要求持续会话工作，不增自动任务。
目标：真实同预算MLE-bench最终收益；不重复G0/模型验收，不把准备或人工测试称效果。

## 活跃作业与不可重复动作

- 13124，forets-repeat-s14，01:33:03 UTC单次提交，01:33:35确认RUNNING/gpu28。
  四run依次Leaf random、Leaf critic、Spaceship critic、Spaceship random，seed14。
  最后观察第一槽running/attempt1，其余pending/attempt0；不是四组完成。
- 根 /research/d7/spc/yzyang4/forets-repeat-20260912-x3pkniqp
  stage /research/d7/spc/yzyang4/forets-smallpool-repair-stage-20260912-wNS7Kw
  controller4394d89ff9d7b31ab5953ac9d4fbc4514beeb84a
  task source f70eb4859c48c61bba37b298fbf8e32e367644ae
  prepared111a28c1c12174c00451c737435028cf8528b386fea1f723392a34e648d6f40e
  inventoryb43020dd30309147d97a9aad24c074a03d193a10b10b05cf547eb7f6a1529154
  releaseb3e0237ce1d32367d9b93e8a444738d7a890ba6ada59e366902d7487cf870b6c
- artifact codex_tmp/forets-smallpool-s14-artifact-20260912-v2；archive SHA35c5897600a06856fc284ef3f987067f3aa8688e435b5f201c9a32b706a59c84。
  已build/activate/catalog/route/submit，均不得再做。新账ACTIVE，旧seed13账SEALED。
- 原SIF/Torch、gpu28单RTX3090、6CPU、max_parallel1、6step/300秒/3540秒、分配280分钟。
  Flash生成不变；Plus完整代码/公开任务/资源正逆排名→固定Borda→原top2/common-priority选1。
  两臂显式skip_redundant_critic=true，n≤2不排名且不改选。禁止改运行规则或Borda平分。
- 真实batch/config两任务×两臂×宽1/2/3/4：16/16通过，倒置旧开关4负对照均复现故障；
  无API/GPU/任务执行的接线检查，不是效果。实际inspect通过STATIC_READY_NOT_SUBMITTED后才提交。
- 01:29:43路由2调用READY/每次1attempt，总0.00015366USD；Plus catalog也通过。
  提交前账216行、结算0.814913905USD、责任2.214913905USD、未知2。
  01:33:35正在生成：new_api_calls3、未知3含在途，不等于新增失败，不能提前释放。
  AUTH d42e129a04210bd56c981c393d2890e0b50b1d98755027893ad3fa6c3127e93a。
  原100人民币/保守10USD累计不重置；本窗口累计上限5.714760245USD，新增≤3.50USD。
  每run共同4USD/100全部API；Flash reserve0.70、Plus2.60，取消未知全额结转。

## 当前会话工作

- 实际session：根/forets_environment_session_20260912.py；status只读，watch会自动closeout不使用。
  observer准备为observe_forets_smallpool_s14_20260912.py（明确新根），不消费结果、不自动重投。
- verify_forets_smallpool_s14_20260912.py绑定job13124/seed14/prepared/source/AUTH/216行/上限。
  共用verify_forets_context_e2e_20260912.py独立核对排序/选择/原submission数值。
  须全4终态后才单次session closeout，再独立验证；当前未读取最终成绩、未closeout。
  原seed13 verifier不可误用。原submission留档在host-only，不读保护集。
- 只读observer已在本会话PTY23406运行；无自动closeout或重投。后继forets_context_s15_repeat已准备，
  尚未facts/build/activate/API/GPU；须13124完整正常闭合及独立核验、至少1可比任务后按公开门运行。
  无论收益正负都重复同两任务，绝不把seed13基础设施失败混入均值。
- rejected构建根forets-repeat-20260912-c36qpa1h从未activate/API/GPU：
  prepared行seed仍12被inspect拒绝；4394d89修复metadata与实际config均14，新根x3通过。
  留存失败构建，不覆盖、不使用。

## 已关闭的失败及探索结果（不重跑）

- 13123 seed13，根forets-context-e2e-20260912-5xz0w6iy，01:17:52整组取消。
  真实配置skip_redundant_critic=false，宽1池进入只接受3/4的rank_pool导致失败。
  我方接入/预检缺陷，不是critic效果负结论；旧typed/import检查未覆盖真实配置全部宽度。
  CANCELLED/1494秒单卡=0.415GPUh；失败/取消/待跑/待跑四槽，不读分、不补槽。
  cancellation-closeout SHA82cc005902f4926f4c48e1eccf5da60e2d56fa8baedaeded000f5a0d1eef0ae4。
  214行/结算0.814760245/责任2.214760245/未知2已完整结转。旧账SEALED，PTY86012结束。
  seed14是修复新实验，不是同版本复验；原FORETS_CONTEXT_REPLICATION_GATE已撤回。
- 13120首池原8代码：Leaf0/4有效，Space1/4有效accuracy0.8069，旧8B top2漏掉它。
  805秒单卡，原submission数值/哈希复验通过；只执行一次，重复代码也保留。
- 未见执行结果的Plus正逆四调用保留Space唯一有效程序：有限池random25%、旧8B0%、Plus两顺序各50%。
  两任务top2仍顺序敏感；仅探索线索，非e2e/跨seed/新颖性。模型和输入信息两因素未分离。
  见FORETS_POOL_AND_CONTEXT_JUDGE_RESULTS_20260912.md；结果已公开，不重问旧池。
- 13118 seed12：Space random0.80805/critic0.61839，-18.966pp；Leaf random缺失/critic0.37782但无改选。
  13115 seed11：Space+5.287pp但所有Space池无实际改选，Leaf双方缺失。没有稳定/可归因收益或clean scaling。
- 人工Borda平分性质分析非实际收益；聚合有NAACL2024/PCFJudge2026先例，不据此改seed14。
  已公开seed13 source capsule v3，284文件/237源码/28controller哈希对应；不是seed14源码包。

## 语料与长期边界

- 0910六包115079888bytes已隔离senior-quarantine-0910-20260912，24配置≠24新完成run；
  两commit065b0fbaa89e0eb663f2834ec768081f5d56394d/61459c0a1248900079dafed7c505afa87e476b40，children2/3不可混。
  未读journal/env/code/outcome、未正式摄取、不重下载。00:19:25两次根metadata与旧50项一致、额外0；
  未见0911/0912，不是所有待上传均不存在证明。LATEST此前759physical/733eligible，非本轮实时核验。
- first-960/Target-300/Target-522封闭；不更新agent底座、不恢复HCE/多保真/Probe/score-channel/K≥1lookahead/旧CPU期限筛查。
- SSH linux5；BASE /research/d7/spc/yzyang4；venvs/aira控制/评分，venvs/exp GPU/gdown。
  source /uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
  gpu28/27可跑原任务镜像，不是projgpu28/39；不升级Torch或退CPU，不索要gres.conf。
- key仅远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY；不得回显/本地/Git，不再次索要。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813。
  只push myfork HEAD:phase1-value-critic，不碰学长分支；最后成功6ab23c32（开跑与预先后继门）。
  每次staged文件名/内容安全扫描，保留用户untracked codex_tmp/output/tmp/旧报告。
- g0-r5 PAUSED，无新automation；held12535不碰。研究盘1TB/2026-09-29到期，续期未知。
