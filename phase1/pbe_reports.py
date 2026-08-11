"""Per-task data analysis reports, the priming ingredient of arXiv:2601.05930.

Their best number (61.5% pairwise) is conditioned on a "Verified Data Analysis Report" in
the prompt header. Their repo shows the judge prompt but the released grader does not
regenerate reports, so this is a reproduction with one honest deviation, stated everywhere
downstream: our reports are written by the model from the competition's own description.md
(the same document their header carries), WITHOUT the execution-verified pass. If priming
shows no decision-point signal the deviation is immaterial; if it shows signal, a verified
variant becomes worth building before any claim is made.

One call per task, cached to phase1/pbe_reports.json; rerunning skips existing entries.

Usage: python phase1/pbe_reports.py [--provider qwen] [--model qwen-max]
"""
import argparse, json, os, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--provider", default="qwen", choices=["deepseek", "qwen"])
ap.add_argument("--model", default="qwen-max")
ap.add_argument("--max-desc", type=int, default=6000)
a = ap.parse_args()

_WANT = ('PRIMARY_KEY_DEEPSEEK_V4_FLASH=' if a.provider == 'deepseek'
         else 'PRIMARY_KEY_QWEN3_CODER_FLASH=')
_URL = ('https://api.deepseek.com/chat/completions' if a.provider == 'deepseek'
        else 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
KEY = None
for line in open("/research/d7/spc/yzyang4/aira-dojo/.env"):
    if line.strip().startswith(_WANT):
        KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
assert KEY, "no key for provider " + a.provider

DATA = "/research/d7/spc/yzyang4/mle-bench-data"
OUT = "phase1/pbe_reports.json"
reports = json.load(open(OUT)) if os.path.exists(OUT) else {}

tasks = sorted(t for t in os.listdir(DATA)
               if os.path.isfile(f"{DATA}/{t}/prepared/public/description.md"))
print(f"tasks with description.md: {len(tasks)}; cached reports: {len(reports)}")

PROMPT = """You are preparing a data analysis report that will help judge which of two \
candidate solutions to a machine learning competition will score better. Using ONLY the \
competition description below, write a concise structured report with these sections:
1. Task and target variable
2. Data schema and size (as stated or inferable)
3. Evaluation metric and its properties (what the metric rewards/punishes)
4. Key risks (leakage, class imbalance, small-data overfitting, metric quirks)
5. What typically separates strong from weak solutions on this kind of task
Do not invent numbers the description does not support. Keep it under 400 words.

Competition description:
{desc}"""


def call(msgs, max_tokens=900):
    req = urllib.request.Request(
        _URL,
        data=json.dumps({"model": a.model, "messages": msgs,
                         "max_tokens": max_tokens, "temperature": 0.0}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(8 * (attempt + 1))


for t in tasks:
    if t in reports and reports[t].get("report"):
        continue
    desc = open(f"{DATA}/{t}/prepared/public/description.md",
                encoding="utf-8", errors="replace").read()[:a.max_desc]
    try:
        rep = call([{"role": "user", "content": PROMPT.format(desc=desc)}])
    except Exception as e:
        print(f"  {t}: FAILED {e}")
        continue
    reports[t] = {"report": rep, "model": a.model, "desc_chars": len(desc)}
    with open(OUT, "w") as f:
        json.dump(reports, f)
    print(f"  {t}: {len(rep)} chars")
print(f"done: {len(reports)}/{len(tasks)} reports -> {OUT}")
