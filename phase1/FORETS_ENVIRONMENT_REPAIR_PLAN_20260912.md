# ForeTS 共同生成环境修复：四 run 开发验证

日期：2026-09-12 香港。继承用户继续推进、合理修改和 API 合计100元授权。
前一版本8run已封闭，0/8有效最终解；原失败、费用与最终评分缺失完整保留。

## 问题和修改范围

原镜像核实了LightGBM4.6.0等版本，40次执行中的14次为LightGBM参数错误。
原draft/improve已有一条early_stopping_rounds提醒，但没有完整版本信息或verbose_eval/
sklearn fit接口提示。因此不是“以前完全没有API提示”，也不能保证增加提示必然修复。

在draft、improve、debug的system模板中加入完全相同的版本/API事实和原300秒总执行时限。
经现有模板渲染和请求记录入口，不在运输层偷偷追加提示；analyze提示及实际评估代码不改。
保留5-fold要求、候选生成数、原SIF/Torch、8B/16K critic、评分方向、top2择1、生成器和路由。
不手改旧候选，不挑旧中途submission补分，不延长失败程序的执行时间，不更新agent底座。

## 固定新开发矩阵和费用

- 任务：leaf-classification、spaceship-titanic，不按这次结果换任务。
- 新seed：10；每任务uniform_random与critic_topk_random各1run，共4run。
- 顺序：leaf random→critic；spaceship critic→random。整块结束前不读最终成绩。
- step_limit=6，num_children=4，critic_top_k=2，choose=1，common_priority_v1。
- Qwen3-Coder-Flash / OpenRouter Alibaba only；每run最多100传输尝试，输出8192tokens。
- gpu28双RTX3090/12CPU，4run串行、一卡critic/一卡原镜像执行；单块280分钟。
  含退出余量，新增GPU预算上限10GPUh；加旧实耗3.2583333333333333，总上限13.258333333333333。
- 新版API新增总上限1.50USD（含route、失败、重试）；旧账124call/0.318775548USD/0未结。
  后继账本显式预扣旧0.318775548USD，并将旧账停止派发；累积上限1.818775548USD，
  仍低于原10USD/100人民币总上限。不得重新给新版另一笔10USD，不重置旧账、不复用旧run scope。
- 先核新包的真实prompt/配置，再执行两个既有有界路由检查（其成功不是MLE可运行性证明），
  最后一次提交完整四run块。不因某一臂先失败而重跑/改参数；异常保留并结束其槽位。

## 读数与后续判断

主读数是有效最终解数/4、逐任务两臂可比性和真实执行错误数，不是worker退出码。
只有四run闭合才一起读最终分数；缺分保留missing，不能填零或宣布打平。
完整四run都保留，单seed只可探索、不宣称跨seed稳定收益或干净scaling。
若仍无法产出有效解，基于实际程序失败定位，不扩大效果矩阵；若可运行，才准备新seed同预算收益检查。
提示版本修订不是新算法，不把新旧可运行率变化单独归因critic；确认需另行冻结新对照。

## 预检对应

真实配置校验三处提示、两臂除selector/机械身份外一致；预算、模型和镜像与产物绑定。
变更函数本地/远端测试，错误超时与重复注入会拒绝；后继账本保留预留/未知费用停机机制。
无训练、无模型存储、无新数据抽样/划分，因此训练去重、模型保存、功效训练侧不适用。
历史开发任务明确不是untouched test；first-960/Target-300/Target-522不读、不变。
总资源含critic闲时，记录命令、commit、种子、失败与费用；提交/发布前扫描凭据。
