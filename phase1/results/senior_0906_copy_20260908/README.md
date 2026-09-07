# 0906新上传：安全复制完成，未摄取、未准入训练

香港2026-09-08 05:41。用户要求继续工作并核查新上传。本轮是数据准备进展，不是模型收益。

## 已完成

- 新目录0906有11归档，0子目录/非归档/独立config-v2 sidecar；两次元数据观测一致。
- 在远端固定私有清单后，按已有下载器做有界新复制：118981762压缩字节（113.47MiB），23请求，80.72552082699258秒。
- 每文件完整stream SHA、fsync和重hash、0400；远端目录再次列举一致后原子提升。另一实现的GNU/Python SHA与全部size/mtime/mode核验通过。
- 归档总量343→354。旧343项元数据前后相同，未覆盖旧文件；未对全部旧压缩payload再hash，不能写成旧字节全集复验。
- 1GiB真实分配门通过，随后仅移除本次自身探测文件。复制使用128MiB单文件/1GiB总量/1800秒/100请求上限，未改原科学摄取协议。
- 本地和远端Linux各20项纯合成输入/请求边界检查通过。固定运行source为`cef7ac01b1fa5745a733bc2b3dad3af42bb1c6d6`。

## 尚未发生

未解压、未解析tar成员、未打开保护标签/预测/utility；未写新snapshot或生成新训练数据。
最晚文件mtime+6h为`2026-09-08T03:40:45.566210Z`（香港11:40:45.566210），这只是时龄下界。
之后还要原3次观测、300秒间隔、600秒稳定跨度与逐事务独立delta核验；不能按上传日期倒填mtime。
本轮不启动后台monitor、不延长旧lease。后续会话应先核最新状态，再明确新的有界摄取调用窗口；不要调用已过期0905入口。

当前库存仍737physical/711eligible/19351endpoints/4380pairs/58tasks、closure=false。
LATEST=`6db37288ac0fe2ca1b833ff63c3b10318cd13610c023a9d2412c194a67dfd116`。
snapshot summary SHA=`77572010daa7af2255084e35b41ae76da50f2f213838c047b4d99c052ce980f3`。
新增11个压缩包不代表11个run，也不能据此估算确认cohort何时关闭。

## 同步推进的来源交接

学长branch仍`40d7dea10738f159fc97cad8487ab4ada88022a3`，fetch后无新outcome。
既有config-v2生产补丁在隔离临时index上对该head的`git apply --cached --check`通过；没有应用补丁、修改学长分支或部署producer。
这只证明文本兼容，不是当前head运行验证，更不能认证历史评分环境。
[最小交接](../../SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md)顶部已更新：不再索要已删snapshot，不让学长重复排查已解决GPU；只需实际评分出处或明确独立开发来源的现成记录。

12664及CPU实物验收已完成且hash未变，不重跑。Slurm只见12535的JobHeldUser，本轮不释放它。
ADMITTED_RELEASES仍空，Lbudget对G-reuse→L-full的seeds6/7四fit未启动，GPU/API/model fit新增0。

## 可复核证据

- `metadata.json`：只包含目录级数量和私有清单hash。
- `source_ready.json`：实际Linux检查及运行源码hash。
- `space.json`：自身1GiB探测inode/allocated blocks，不是永久配额保证。
- `copy.json`、`copy_exit.json`：实际下载和退出回执。
- `independent_copy.json`：独立字节/权限/时龄核验，SHA=`b449fa2b6e6998b0fefe9db29d9f29b5a3a4bf70448713c1b8da6ae548bed7ee`。
- `export_manifest.json`：上述六份原始安全回执的精确字节数与SHA；原始归档及带私有名字的清单只留远端。
- `runs.csv`：单次实际复制的成本账，不是跨seed训练结果或吞吐基准。
- `operations/`：本轮通过stdin在远端实际执行的元数据、部署/复制/独立核验、安全导出helper。仅为复现追溯，不允许向已存在输出根重跑；原始包绝不由该目录导出。

原始包位置为`/research/d7/spc/yzyang4/external/senior_data/mle/0906`；这不是给学长交付训练包的公共下载地址。
