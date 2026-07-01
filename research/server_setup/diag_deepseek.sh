#!/usr/bin/env bash
# Isolation diagnostic: can DeepSeek v4-pro write a WORKING spaceship-titanic solution given a
# SIMPLE, explicit prompt? If yes -> aira-dojo's elaborate o3-tuned operators are what break it.
source ~/env_setup.sh
AIRA=/research/d7/spc/yzyang4/aira-dojo
set -a; [ -f "$AIRA/.env" ] && source "$AIRA/.env"; set +a
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python

"$PY" - <<'PYEOF'
import os, re, subprocess, sys, pathlib, shutil
from openai import OpenAI
key = os.environ.get("PRIMARY_KEY_DEEPSEEK_V4_PRO") or os.environ.get("PRIMARY_KEY")
assert key, "no DeepSeek key in env"
client = OpenAI(base_url="https://api.deepseek.com", api_key=key)
DATA = "/research/d7/spc/yzyang4/mle-bench-data/spaceship-titanic/prepared/public"
WORK = "/research/d7/spc/yzyang4/aira-dojo-runs/diag_ds"
prompt = (
"You are a Kaggle expert. Write a COMPLETE, SIMPLE, ROBUST Python script for the Spaceship Titanic competition.\n"
"Data is in ./data/: train.csv (target column 'Transported', bool), test.csv, sample_submission.csv.\n"
"Binary classification; metric = accuracy.\n"
"Requirements:\n"
"- Handle ALL non-numeric columns (encode categoricals or drop id/name cols) so the model never gets object dtypes.\n"
"- Train a simple robust model (LightGBM or sklearn HistGradientBoostingClassifier).\n"
"- Print the 5-fold cross-validation accuracy.\n"
"- Save ./submission.csv with columns PassengerId,Transported (True/False) matching sample_submission.csv.\n"
"Keep it under ~60 lines. Output ONE python code block only."
)
print("=== calling deepseek-v4-pro ===", flush=True)
resp = client.chat.completions.create(model="deepseek-v4-pro",
    messages=[{"role":"user","content":prompt}], temperature=0.3)
text = resp.choices[0].message.content
u = resp.usage
print("tokens:", u.prompt_tokens, "+", u.completion_tokens, "=", u.total_tokens)
m = re.search(r"```python\s*(.*?)```", text, re.S) or re.search(r"```\s*(.*?)```", text, re.S)
code = m.group(1) if m else text
p = pathlib.Path(WORK); p.mkdir(parents=True, exist_ok=True)
d = p/"data"
if d.is_symlink() or d.exists():
    d.unlink() if d.is_symlink() else shutil.rmtree(d)
os.symlink(DATA, d)
(p/"solution.py").write_text(code)
print("=== code head (first 35 lines) ==="); print("\n".join(code.splitlines()[:35]))
print("=== running solution.py (timeout 1200s) ===", flush=True)
try:
    r = subprocess.run([sys.executable, "solution.py"], cwd=str(p), capture_output=True, text=True, timeout=1200)
    print("RC:", r.returncode)
    print("STDOUT tail:\n", r.stdout[-1500:])
    print("STDERR tail:\n", (r.stderr or "")[-1500:])
    print("submission.csv exists:", (p/"submission.csv").exists())
except subprocess.TimeoutExpired:
    print("TIMEOUT (>1200s)")
PYEOF
echo "DIAG_DEEPSEEK_DONE"
