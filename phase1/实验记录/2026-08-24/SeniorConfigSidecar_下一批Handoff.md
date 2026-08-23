# Senior config-provenance sidecar：下一批 archive handoff

日期：2026-08-24
状态：`HANDOFF_READY_NOT_DEPLOYED`
协议：`senior-experiment-config-manifest-v1`

## 1. 交付结论与边界

这份 handoff 供学长从**下一批新产生的 archive**开始，在 outcome/label 被任何分析读取前，由 producer
直接导出 run→public config sidecar。它解决的是 future clean capability×generator 分析所需的配置可识别性，
不是科学效果，也不授权训练或 GPU 实验。

本次明确没有做以下事情：

- 不给当前 33-run cohort 事后回填配置；
- 不改变 first-960 主 cohort 的时间序、accrual closure 或 truth-vault 规则；
- 不读取 archive payload、Cards、pairs、stdout、submission、outcome、grade、prediction 或 orientation；
- 不访问 API，不使用 GPU，不训练模型，不更新 agent 底座；
- 不部署到学长生产，不修改 `phase1/CURRENT_DIRECTION.md`。

示例文件
`phase1/examples/senior_experiment_config_manifest_v1.example.jsonl` 是**纯 synthetic、静态 schema-valid 的字段示意**。
其中的 run、task、release、hardware 和日期都不是实际实验身份，禁止复制后原样提交。它没有真实 expected-run manifest、
source manifest 和 verified source receipt，因此绝不声称 `CONFIG_PROVENANCE_VERIFIED`。

## 2. Producer 端何时生成

sidecar 必须在同一批 run 的 producer config 已锁定、但 outcome/label 尚未用于分析时生成。推荐顺序：

1. 冻结本批 run identity 和 task；
2. 从**启动这些 run 的同一份 producer config**读取公开配置字段，不从结果、Cards archive 或机器日志回推；
3. 在 archive 发布前生成并封存 JSONL 与文件 SHA-256；
4. 同时交付对应 expected-run manifest、source-provenance manifest 及其 SHA；
5. consumer 先独立取得 `PROVENANCE_VERIFIED` source receipt，再组合验证 config sidecar；
6. 只有真实输入上的 config receipt 成为 `CONFIG_PROVENANCE_VERIFIED`，且另一个 outcome-blind support gate
   通过后，才可冻结 capability×generator 交互矩阵。

若 producer 无法在结果前知道 server-side release，`generator_release` 必须诚实写成字面量 `unknown`，不得事后猜测。
这仍可保存 provenance，但正式 receipt 会令 `interaction_metadata_complete=false`，该批不能支撑 release interaction。

## 3. 一行一个 physical run 的精确字段

每行必须恰好包含以下 8 个字段，不多不少：

| 字段 | Producer 来源与约束 |
|---|---|
| `run_id` | 冻结的真实 physical-run ID；格式为 `<source-run>__YYYY-MM-DD`，且 `<source-run>` 匹配 `..._seed_<整数>_id_<小写hex>`。不得造 ID。 |
| `task` | 与 frozen expected-run manifest 中该 `run_id` 的 task 逐字相同。 |
| `client` | 启动 run 时 `solver.operators.draft.llm.client.model_id` 的公开 model ID；不得由结果反推，不得含 endpoint、query 或凭据。 |
| `generator_release` | Producer 在 outcome 前声明的公开 release/deployment 标签；确实不可知才写 `unknown`。 |
| `hardware` | 同一 producer config 中用于该 run 的公开 hardware 字符串，不做事后归一化。 |
| `time_limit` | 同一 producer config 的原始正有限 JSON number；保留原类型和值。 |
| `execution_timeout` | 同一 producer config 的原始正有限 JSON number；保留原类型和值。 |
| `experiment_stratum_sha256` | 对 `[task,client,hardware,time_limit,execution_timeout]` 的 UTF-8 compact JSON 计算 SHA-256。 |

数值的 JSON 表示属于 hash 输入：例如整数与浮点表示不可相互强制转换。`client`、`generator_release`、`hardware`
只能使用 validator 允许的窄公开字符集，前后不得有空白；不得写私有 URL、访问令牌、环境变量内容或任意 outcome 字段。

## 4. 可直接移植的最小导出逻辑

下面逻辑应接在 producer 已经拥有 `run_id/task/config` 的位置；它只是 handoff 参考，当前仓库没有替学长部署：

```python
import hashlib
import json
from pathlib import Path


def make_row(*, run_id, task, client, generator_release, hardware,
             time_limit, execution_timeout):
    row = {
        "client": client,
        "execution_timeout": execution_timeout,
        "experiment_stratum_sha256": "",
        "generator_release": generator_release,
        "hardware": hardware,
        "run_id": run_id,
        "task": task,
        "time_limit": time_limit,
    }
    stratum = [task, client, hardware, time_limit, execution_timeout]
    encoded = json.dumps(
        stratum,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    row["experiment_stratum_sha256"] = hashlib.sha256(encoded).hexdigest()
    return row


def render_jsonl(rows):
    ordered = sorted(rows, key=lambda row: row["run_id"])
    if len({row["run_id"] for row in ordered}) != len(ordered):
        raise ValueError("duplicate run_id")
    return "".join(
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ) + "\n"
        for row in ordered
    )


# Write to a fresh path, then publish it immutably beside the new archive.
# Do not overwrite an already published sidecar.
Path("producer-config-provenance.jsonl").write_text(
    render_jsonl(rows), encoding="utf-8", newline="\n"
)
```

正式 producer 应使用 fresh/atomic publish，且失败时保留失败状态；上面最后两行只说明规范字节格式，不是部署脚本。
文件必须 UTF-8、LF 结尾、无空行，并按 `run_id` 字节序排列。对当前允许的 run ID 字符，Python 的上述排序与
UTF-8 字节序一致。

## 5. 学长交给 consumer 的最小包

每个待验证 frozen-run 集合需要同时提供：

1. `producer-config-provenance.jsonl` 及其 SHA-256；
2. 覆盖完全同一 run 集的 frozen expected-run manifest 及其 SHA-256；
3. source-provenance manifest 及其 SHA-256；
4. 由独立 source validator 产生的、绑定上述 expected/source 输入的 `PROVENANCE_VERIFIED` receipt 及其 SHA-256；
5. producer commit 已由 source manifest 的逐 run `producer_commit` 绑定，不在 config sidecar 重复。

若按 archive 分批输出 sidecar，则每个文件只覆盖该批真实 physical runs，保持 append-only、不可变。做跨批 cohort
正式验证时，consumer 必须先把被纳入 frozen expected-run 集的所有行合并、按 `run_id` 重排并计算一个新的 manifest
SHA；不得只拿某个方便的子集通过门。

## 6. Fail-closed 验收清单

- config/source 两个 manifest 必须与 expected-run manifest 精确覆盖同一 run 集：无缺失、无额外、无重复；
- config/source 行都按 `run_id` 排序，`task` 与 expected row 精确一致；
- `time_limit`、`execution_timeout` 是正有限 JSON number，不能是布尔值、字符串、0、NaN 或无穷；
- stratum hash 由 validator 独立重算，任一字段或数值类型变化都必须导致旧 hash 被拒绝；
- config JSONL 只能有规定的 8 个字段，严禁 grade、prediction、stdout、submission、runtime 等结果字段；
- 所有输入在 JSON parse 前由 validator 做凭据形状扫描；命中即整批拒绝，不做逐行 salvage；
- `unknown` client/hardware/release 会使 `interaction_metadata_complete=false`；不得将 provenance pass 写成交互支持 pass；
- source receipt 必须是同一 expected/source SHA 与 mapping 的 verified v1 receipt；不能拼接另一批 receipt；
- input/output symlink、已有 output receipt、篡改 SHA、乱序或不完整覆盖均 fail closed；
- 任何失败都不得通过删行、换 cohort 或结果后补字段来“修复”。应修 producer 并对下一批重新冻结。

## 7. 验证命令

### 7.1 仓库现有攻击测试

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python -m pytest -q phase1/tests/test_senior_experiment_config_manifest.py
```

该测试验证确定性 join、unknown 降级、hash 篡改、漏 run、task 错配、source receipt 篡改、凭据形状、非法公开值、
非正 timeout、额外字段、乱序、不可覆盖 output 以及 symlink fail-closed。

### 7.2 synthetic 示例的静态 schema/hash 检查

```bash
python -c 'import hashlib; from pathlib import Path; import phase1.validate_senior_experiment_config_manifest as v; p=Path("phase1/examples/senior_experiment_config_manifest_v1.example.jsonl"); raw=p.read_bytes(); v.checked_bytes(p,hashlib.sha256(raw).hexdigest()); rows=v.load_jsonl(p,v.CONFIG_FIELDS); expected=v.validate_expected_runs([{"run_id":r["run_id"],"task":r["task"]} for r in rows]); v.validate_config_rows(rows,expected); print("STATIC_EXAMPLE_SCHEMA_PASS")'
```

这个命令只证明 example 的字节安全、精确字段、run ID 形状、公开值、正数与 stratum hash 自洽。由于 expected rows
由 synthetic 示例本身构造，它**不验证真实 run coverage、task join 或 source receipt**，输出也不是 formal status。

### 7.3 下一批真实输入的正式组合验证

先记录不可变输入 SHA，再调用现有 validator：

```bash
sha256sum \
  <frozen-run-manifest.jsonl> \
  <producer-source-provenance.jsonl> \
  <verified-source-receipt.json> \
  <producer-config-provenance.jsonl>

python phase1/validate_senior_experiment_config_manifest.py \
  --expected-runs <frozen-run-manifest.jsonl> \
  --expect-runs-sha256 <sha256> \
  --source-provenance <producer-source-provenance.jsonl> \
  --expect-source-provenance-sha256 <sha256> \
  --source-receipt <verified-source-receipt.json> \
  --expect-source-receipt-sha256 <sha256> \
  --config-provenance <producer-config-provenance.jsonl> \
  --expect-config-provenance-sha256 <sha256> \
  --output <fresh-config-receipt.json>
```

正式接受必须同时看到进程返回 0、stdout 的 `CONFIG_PROVENANCE_CONTRACT_PASS`，以及 fresh receipt 中
`formal_status=CONFIG_PROVENANCE_VERIFIED`。这仍然只证明 identity/config join；它不证明支持矩阵平衡、模型效果或
search utility，也不自动授权训练。

## 8. 当前 handoff 的诚实状态

- contract/validator/tests：已存在且未被本次修改；
- synthetic example：已通过现有 validator 的静态 schema/hash 路径；
- 下一批真实 sidecar：尚未生成；
- 正式真实 receipt：尚不存在；
- 学长生产部署：未执行；
- 当前 33-run cohort 回填：未执行且禁止。

因此本次最终状态只能是 `HANDOFF_READY_NOT_DEPLOYED`，不能升级为
`CONFIG_PROVENANCE_VERIFIED` 或 `INTERACTION_SUPPORTED`。

## 9. 2026-08-24 本地验证记录

在当前 Windows 工作树、HEAD `25f46c69ff7e28685a37b6924d36c3483b671555` 上执行：

- 7.2 的静态命令返回 0，并打印 `STATIC_EXAMPLE_SCHEMA_PASS`；
- `python -m pytest -q -rs phase1/tests/test_senior_experiment_config_manifest.py` 返回 0：
  `10 passed, 1 skipped in 0.16s`；唯一 skip 是 Windows 当前用户没有创建 symlink 的权限，因此本轮不声称
  symlink case 在本机通过；仓库既有远端 Linux receipt 已记录该攻击测试通过；
- example 为 1 行 canonical compact JSONL，UTF-8/LF，CR byte=0；文件 SHA-256 为
  `e18f0ad48f85a13da862d6fdb5d68519e7ff77b5ad7a3223180a2bdc9c6c4e17`；
- 对 example 与本 handoff 做现有高置信凭据形状扫描，命中数分别为 0/0；
- 没有运行 7.3 的 formal validator，因为真实 next-batch expected/source/config 输入尚不存在。此处不以 synthetic
  fixture 冒充真实 `CONFIG_PROVENANCE_VERIFIED`。
