"""Reproduction of the arXiv:2601.05930 protocol on the decisions search actually faces.

Their claim: an LLM primed with a task description and a data analysis report predicts which
of two ML solutions performs better at 61.5%, without executing anything. Their number is
computed on globally-sampled pairs. Ours is the question their evaluation does not ask:
does the signal survive at the DECISION POINT -- same-parent siblings, budget fixed, where
54% of pairs have a true-score gap under 1e-2 and every static predictor we trained sits at
chance against an exact noise ceiling of 0.90?

Faithful to their grader (grade/util/prompt.py, quoted): the system prompt forbids assuming
ground truth or executing; the user prompt is header sections + "Important instructions"
with "Predict which solution will perform best ... WITHOUT running code" + JSON
{"predicted_best_index": 0 or 1}; non-COT variant; indices follow listing order. Two arms:
  desc         header = task description only
  desc_report  header = task description + our regenerated (unverified) data analysis report
Every pair is asked in BOTH orders; order-averaged accuracy is what gets reported, and the
between-order disagreement rate is a published reliability diagnostic.

Sampling: stratified by hard/easy at the pre-registered 1e-2 threshold and by task within
each stratum, from decision_clean_b0.jsonl. Incremental writes after every call.

Usage: python phase1/pbe_judge.py OUT.jsonl --arm desc|desc_report [--pairs 300] [--workers 6]
"""
import argparse, collections, json, math, os, random, threading, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--arm", default="desc_report", choices=["desc", "desc_report"])
ap.add_argument("--pairs", type=int, default=300)
ap.add_argument("--workers", type=int, default=6)
ap.add_argument("--max-code", type=int, default=6000)
ap.add_argument("--max-desc", type=int, default=3500)
ap.add_argument("--model", default="qwen-max")
ap.add_argument("--provider", default="qwen", choices=["deepseek", "qwen"])
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
cards = {}
for l in open("phase1/cards_current_v9.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
REPORTS = {}
if a.arm == "desc_report":
    REPORTS = json.load(open("phase1/pbe_reports.json"))

# ---- stratified sample, deterministic ------------------------------------------
pairs = [json.loads(l) for l in open("phase1/decision_clean_b0.jsonl")]
pairs = [p for p in pairs if p["better"] in cards and p["worse"] in cards]
hard = [p for p in pairs if float(p["gap_raw"]) < 1e-2]
easy = [p for p in pairs if float(p["gap_raw"]) >= 1e-2]
rng = random.Random(7)


def strat(sub, n):
    byt = collections.defaultdict(list)
    for p in sub:
        byt[p["task"]].append(p)
    for t in byt:
        rng.shuffle(byt[t])
    out, i = [], 0
    while len(out) < n and any(byt.values()):
        for t in sorted(byt):
            if byt[t] and len(out) < n:
                out.append(byt[t].pop())
        i += 1
    return out


sample = strat(hard, a.pairs // 2) + strat(easy, a.pairs - a.pairs // 2)
print(f"sampled {len(sample)} pairs "
      f"({sum(1 for p in sample if float(p['gap_raw'])<1e-2)} hard, "
      f"{len(set(p['task'] for p in sample))} tasks)", flush=True)

done = set()
if os.path.exists(a.out):
    for l in open(a.out):
        try:
            d = json.loads(l)
            done.add((d["better"], d["worse"], d["order"]))
        except json.JSONDecodeError:
            pass
print(f"already on disk: {len(done)}", flush=True)

SYS = ("Base your judgment on the task description and the shown code snippets only. "
       "Never assume external ground-truth, never execute code, and do not include any "
       "text beyond the required raw JSON output.")


def desc_of(task):
    p = f"{DATA}/{task}/prepared/public/description.md"
    try:
        return open(p, encoding="utf-8", errors="replace").read()[:a.max_desc]
    except OSError:
        return f"(description unavailable for {task})"


def user_prompt(task, code0, code1):
    hdr = f"## Task description\n{desc_of(task)}\n"
    if a.arm == "desc_report" and task in REPORTS:
        hdr += f"\n## Data analysis report\n{REPORTS[task]['report']}\n"
    return (f"{hdr}\nImportant instructions:\n"
            "- Predict which solution will perform best WITHOUT running code.\n"
            "- Use only the sources above.\n"
            '- Response format: {"predicted_best_index": <0 or 1>, '
            '"confidence": <float between 0 and 1>}\n'
            "- Indices correspond to the order of the listed solutions (0..1).\n"
            "- Output raw JSON only (no extra text, no Markdown fences).\n"
            f"\nProvided solutions:\n### Solution 0\n```python\n{code0}\n```\n"
            f"### Solution 1\n```python\n{code1}\n```\n")


def call(task, c0, c1):
    req = urllib.request.Request(
        _URL,
        data=json.dumps({"model": a.model,
                         "messages": [{"role": "system", "content": SYS},
                                      {"role": "user",
                                       "content": user_prompt(task, c0, c1)}],
                         "max_tokens": 200, "temperature": 0.0}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=240) as r:
        j = json.load(r)
    txt = j["choices"][0]["message"]["content"]
    usage = j.get("usage", {})
    s = txt[txt.find("{"): txt.rfind("}") + 1]
    try:
        idx = int(json.loads(s)["predicted_best_index"])
    except (ValueError, KeyError, json.JSONDecodeError):
        idx = None
    return idx, txt[:300], usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


lock = threading.Lock()
stats = collections.Counter()


def work(chunk):
    for p in chunk:
        code_b = (cards[p["better"]].get("code") or "")[:a.max_code]
        code_w = (cards[p["worse"]].get("code") or "")[:a.max_code]
        for order in (0, 1):
            if (p["better"], p["worse"], order) in done:
                continue
            c0, c1 = (code_b, code_w) if order == 0 else (code_w, code_b)
            try:
                idx, raw, tin, tout = call(p["task"], c0, c1)
            except Exception as e:
                with lock:
                    stats["error"] += 1
                    print(f"  ERR {type(e).__name__} {p['task'][:20]}", flush=True)
                time.sleep(10)
                continue
            correct = None
            if idx in (0, 1):
                picked_better = (idx == 0) if order == 0 else (idx == 1)
                correct = int(picked_better)
            rec = {"task": p["task"], "better": p["better"], "worse": p["worse"],
                   "gap_raw": p["gap_raw"], "parent": p.get("parent"),
                   "order": order, "arm": a.arm, "model": a.model,
                   "pick_index": idx, "correct": correct,
                   "tok_in": tin, "tok_out": tout, "raw": raw}
            with lock:
                with open(a.out, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                stats["ok" if correct is not None else "unparsed"] += 1
                stats["tok_in"] += tin
                stats["tok_out"] += tout
                n = stats["ok"] + stats["unparsed"]
                if n % 50 == 0:
                    print(f"  {n} calls, unparsed {stats['unparsed']}, "
                          f"errors {stats['error']}, "
                          f"tokens {stats['tok_in']/1e6:.2f}M in", flush=True)


chunks = [sample[i::a.workers] for i in range(a.workers)]
threads = [threading.Thread(target=work, args=(c,)) for c in chunks]
t0 = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"done in {time.time()-t0:.0f}s: {dict(stats)}", flush=True)
