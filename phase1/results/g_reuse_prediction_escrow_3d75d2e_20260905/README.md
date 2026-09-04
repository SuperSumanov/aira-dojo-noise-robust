# G-reuse label-blind prediction escrow验收器回执

结果前commit=`3d75d2eb8f7b955cfae12a2a77e068bb658be19e`。本地首轮测试发现合法协议的角色顺序与
validator误要求的字母顺序不一致，合法fixture被拒绝；该开发失败发生在提交与任何真实预测前，修复后本地为
12 passed/1 skipped（Windows symlink不可用）。

exact commit archive SHA-256=`ac35506413bf2c9553cc4f6a60970f7f13633ff3d586e90a08d854dbdba2382f`；
Linux正式根`/research/d7/spc/yzyang4/g-reuse-prediction-escrow/formal-3d75d2e-v1`为13 passed、stderr 0。
协议/validator SHA-256分别为
`5384ceae001952d7aee225cebf09c277f7d92e404ec330a4ec436098b29fc55f`和
`8ee28337074e87b0f66c5899c00df1c0419eeebaa6b12a0b1d3d9772d46b7aaa`。

验收器要求五臂×三seed恰好15个final checkpoint及训练/config SHA；prediction JSONL只能含四种匿名cluster SHA、
15个seeded margins与一个TF-IDF margin，拒绝truth/raw identity、缺臂、NaN、重复pair、hash漂移、symlink/hardlink、
凭据形状与JSON重复key。`false == 0`的Python陷阱有专门攻击测试，访问次数必须为真正integer 0。

通过状态故意是`PREDICTION_ESCROW_HASH_BOUND_NOT_EFFECT_READOUT_ELIGIBLE`：access receipt仍只是hash-bound自证，
不证明OS级文件访问，也不证明checkpoint或来源合法；更不连接truth。实际label-blind scorer尚未实现，必须在同producer
包和G0通过后绑定真实checkpoint格式。本轮GPU/API/model fit/protected read均为0，不是效果或scaling结果。
