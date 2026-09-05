# 同源、完整隔离训练包：最小解锁交接

## 2026-09-06：已自行找回启动清单，下一步只需生产端不可替代的证据

原676run的配置、journal位置和真实launcher定位均已找回，无需重新手填这些行或重复上传同一语料。
144份srun/local清单对应143个记录实例，A/B及独立核对通过，详细见
[launcher恢复报告](results/historical_pool_lineage_20260906/README.md)。

目前最有帮助的是：

1. **可读的实际代码/环境快照或已有备份**：manifest记录的143个snapshot，在我方机器检查85无权限、58路径不存在。
   若路径属于另一台生产机，只需指出那台机器上的可访问副本。请提供原snapshot中的运行代码以及MLE-bench实际版本/修改记录；
   不要放API key、完整env或重新填写当前Git SHA当作历史事实。
2. **真实experiment边界说明与现成执行记录**：清单的创建/运行信息已在，仍有150条未匹配来源记录、2条仅目录候选、1条Slurm step不一致。
   只需说明现成记录的位置及跨launcher的experiment联系，未知保持未知；不用手工重建整张来源表。

已找到的MLE-bench README pin只能证明安装recipe，不能证明当时实际环境。旧构建命令若无法恢复，不必补造：
资格补齐后由我方从固定输入做一次新Cards/G/L构建，记录实际执行版本、命令和产物SHA。
84run的结构条件较完整不等于已获准训练；未用它们窥视成绩或替代保护评测集。

下面保留9月5日旧交接作为历史记录；“runner清单完全缺失”的旧表述已被本更新覆盖。

## 2026-09-05晚间更新：交接已显著缩小

我们已找到共享盘正确的0811 leaf并补回全部8个缺失run，恢复676/676个历史run配置、记录Git/meta_id及journal位置。
私有逐run账本已经存在；不需学长手填这676行或再次上传同一leaf包。完整结果见
[来源恢复报告](results/historical_source_recovery_20260905/README.md)。

现在只请提供现成记录的位置：

1. 原runner/launch/experiment清单，用来确认真实experiment完整范围，以及是否有归档目录与meta_id未表达的跨目录联系。
2. 当时的可读代码/环境快照、依赖锁或外部评分执行记录，重点MLE-bench实际版本。记录中的9个base_path目前5不存在、4无权。

我们可以在这些事实核定后，自行新建不可变输入范围、保留旧hold并关闭全部关联、重建同一版本Cards/G/L，
把**本次真实**执行命令与哈希写入产物；不用追填不存在的旧构建命令。
没有旧hold关联的138run/38组件只是候选范围，不是已批准训练包；没有绕过first960/Target300/Target522保护。

## 这次已确认的起点

2026-09-05只读核验学长分支`b8d095180415957aa1bab31fa53ead1bba261c03`：下面四个文件的
最近修改均为`5baccb170ce287f9c8eed7b23ccf693a0268515a`。这是同一次**发布提交**，尚非同一实际生产过程的证明。
没有下载或解析这些数据payload，未读任何前瞻标签/预测/候选身份。

|文件（均在data/augmented_mle_critic）|LFS SHA-256|字节|
|---|---|---:|
|augmented_cards_current.json|90ffba2c4768608452256c54580241e68722806ac9f623cb040754054a8b1fa7|979839759|
|value_pairs_hardware_timelimit_gap_filtered_runsplit.jsonl|e610ddabaf7cd1454db65f73a141cc8590edff96310d9465caac1f0f2e2676df|4037649|
|merged_decision_pairs_filtered_runsplit.jsonl|f75a1a0857962e6c3427ede2fd0518af2db7cbba3fb9ebb055919519d756b56e|3724909|
|runsplit_holdruns.json|b10fe68e39e40577d251dfc1d8cb56f3c765c4c7a1fe0b70dbc0cb8300ecaa54|189661|

## 现在缺的不是再上传一份大文件

同一head的`build_runsplit.py`按task内physical run做80/20，输出只有hold/all；
`apply_runsplit.py`仅分train/test并去除跨边界pair，没有独立dev，也没有实际experiment分组输入。
`build_cards.py`以config id加launch日期构造run key；构建过程还读取journal标签并打印medal/gold统计。
因此不能直接在包含前瞻runs的全集上运行该脚本，不能把它的输出当成结果盲的训练包验收。
本轮检查到该data目录没有以provenance/producer/evaluator/receipt命名的文件；这不等于证明回执在其它地方不存在。

源码credential-shape检查均0 hits。三个被核验源码SHA依次为：
`bb5b5c98cbe5ce6b38f350eb72d7e34ba4b9c4b9c633eeab88ea7568b564402b`、
`4c110661b39cb5cb83bd2cd7670420d9a38cb77f0de3f66e2b53a3f10363fc08`、
`5390846d0c686c2b1014130743953d3ae1b6f26c4040fe19787256fbf931c0df`。

## 请学长只补生产端才能确认的三项信息

1. **可用于历史开发的输入范围及原始记录位置**：不可包含first-960、Target-300、Target-522，
   也不可把已有反复查看的test重新命名为untouched frozen。给可访问位置及对应SHA即可，不必重复上传全集。
2. **真实run→experiment/producer-instance映射**：请明确experiment指单次独立agent运行，还是共享一次实验配置/
   批次的多次运行；以生产端事实为准，并给实际归档/journal映射。歧义来源不能由我们按日期或分数猜选。
3. **实际生成和评分出处**：构建Cards/pairs的版本及命令、运行时generator/resource配置来源，以及外部评分实现/
   执行记录的出处。无法追溯的字段请明确“未知”，不要补一个当前Git SHA当作过去实际执行的版本。

可直接把现成的私有生产记录交给我们远端检查；不需要手工编七个JSON，更不要在Git里放环境变量或API key。
如果旧数据无法补齐，明确说明，再提供一个有真实回执的新历史开发包；不能靠声明true解锁。

## 我方随后完成的事

先冻结获准输入和实际experiment单位；在不读取结果的阶段固定train/dev/frozen分组，保留已冻结的旧归属。
由同一版本和同一输入清单生成Cards/G/L，核exact config、pair/Card/run/experiment隔离，训练进程只获得train/dev。
新untouched evaluation必须有独立来源与关闭回执，不能由历史test换名产生。
最后物化七角色包、哈希、匿名任务支持数及重建命令；独立复验通过才进入G-reuse训练预算审批。

G0已获准单次工程重试，但其原历史4,689/551 train/dev只能估算成本，**不替代这里的正式来源包**。
