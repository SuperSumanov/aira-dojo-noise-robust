"""LLM-as-judge: the second method family, and the one every reviewer will ask about.

Why this experiment exists. Our null is currently "our trained value model does not beat the
agent's free self-report". The published form of a null (RecSys 2019's award-winning
reproducibility study) needed breadth across METHODS -- 18 of them -- not breadth across
tasks. We have one method family, so "maybe you just trained a bad model" is unanswered.
An LLM judge is the obvious second family, it has never been tried for MLE node selection
(AIDE and aira-dojo both rely on execution feedback instead), and both outcomes help:
losing gives the reality-check paper its second family, winning is the positive result.

Two arms, because they answer different questions:
  A  code only        -- exactly the information set the trained model had. Fair comparison.
  B  code + self-report -- can a strong LLM improve on the free signal it is shown?

Design choices that matter:
  * position bias is real in pairwise judging, so every pair is asked in BOTH orders and
    scored as order-averaged accuracy; the disagreement rate between orders is reported as
    a reliability diagnostic rather than hidden.
  * the judge never sees the true grade, the tree, or anything from the future.
  * sampling is stratified BY RUN, because run count -- not pair count -- is what bounds
    every CI on this corpus.
  * results append to disk after every call: this session has crashed three times, and a
    half-finished sweep must not have to be repaid.

Usage: python phase1/llm_judge.py OUT.jsonl [--arm code|code_sr] [--pairs N] [--workers 8]
"""
import argparse, collections, json, math, os, random, re, sys, threading, time
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--arm", default="code", choices=["code", "code_sr"])
ap.add_argument("--pairs", type=int, default=500)
ap.add_argument("--workers", type=int, default=8)
ap.add_argument("--max-chars", type=int, default=5000)
ap.add_argument("--max-tokens", type=int, default=1500)
ap.add_argument("--model", default="deepseek-v4-flash")
a = ap.parse_args()

KEY = None
for line in open("/research/d7/spc/yzyang4/aira-dojo/.env"):
    if line.strip().startswith("PRIMARY_KEY_DEEPSEEK_V4_FLASH="):
        KEY = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
assert KEY, "no deepseek key"

ORI = json.load(open("phase1/task_orientation.json"))
RUN = json.load(open("phase1/card_run_map.json"))
cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d


def fin(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---- pair sample: the same held-out side the trained model was scored on -------------
pool = []
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    if p["intask_split"] != "test":
        continue
    b, w = p["better"], p["worse"]
    if b not in cards or w not in cards:
        continue
    if fin(cards[b]["obs"].get("val_at_low")) is None:
        continue
    if fin(cards[w]["obs"].get("val_at_low")) is None:
        continue        # keep only pairs where the self-report baseline is defined,
                        # so every method is scored on an identical pair set
    pool.append(p)

by_run = collections.defaultdict(list)
for p in pool:
    by_run[RUN[p["better"]]].append(p)
rng = random.Random(7)
runs = sorted(by_run)
rng.shuffle(runs)
sample, i = [], 0
while len(sample) < a.pairs and any(by_run.values()):   # round-robin over runs
    r = runs[i % len(runs)]
    if by_run[r]:
        sample.append(by_run[r].pop(rng.randrange(len(by_run[r]))))
    i += 1
    if i > 100000:
        break
print(f"[judge] pool {len(pool)} pairs over {len(runs)} runs; sampled {len(sample)} "
      f"over {len({RUN[p['better']] for p in sample})} runs", flush=True)

done = set()
if os.path.exists(a.out):
    for l in open(a.out):
        try:
            d = json.loads(l)
            done.add((d["better"], d["worse"], d["order"]))
        except Exception:
            pass
    print(f"[judge] resuming: {len(done)} calls already on disk", flush=True)

SYS = ("You are an expert machine-learning engineer reviewing two candidate solution "
       "programs for the same Kaggle competition. Judge which one will score better on "
       "the hidden held-out test set. Consider methodology: validation design, leakage, "
       "model choice, feature handling, and whether the approach will generalise. "
       "Answer with exactly one character: A or B.")


def render(cid):
    d = cards[cid]
    code = (d.get("code") or "")[:a.max_chars]
    out = "```python\n" + code + "\n```"
    if a.arm == "code_sr":
        s = fin(d["obs"].get("val_at_low"))
        out = (f"[the agent reported its own validation score as: "
               f"{'unavailable' if s is None else format(s, '.6g')}]\n" + out)
    return out


def ask(task, first, second):
    body = json.dumps({
        "model": a.model,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content":
             f"Competition: {task}\n"
             f"({'lower' if ORI.get(task, False) else 'higher'} metric score is better)\n\n"
             f"=== SOLUTION A ===\n{render(first)}\n\n"
             f"=== SOLUTION B ===\n{render(second)}\n\n"
             "Which solution scores better on the hidden test set? Answer A or B."}],
        "max_tokens": a.max_tokens, "temperature": 0.0}).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    proxy = urllib.request.ProxyHandler({"https": os.environ.get("https_proxy", "")})
    op = urllib.request.build_opener(proxy)
    for attempt in range(4):
        try:
            r = json.load(op.open(req, timeout=120))
            msg = r["choices"][0]["message"]
            txt = (msg.get("content") or "").strip().upper()
            m = re.search(r"([AB])", txt) or re.search(r"[AB]", txt)
            if not m:
                # answer never emitted (reasoning hit the cap): take the last A/B
                # the trace committed to, and mark it so it can be excluded later
                tr = (msg.get("reasoning_content") or "").upper()
                cands = re.findall(r"SOLUTION ([AB])|ANSWER[: ]+([AB])", tr)
                flat = [x or y for x, y in cands]
                if flat:
                    return ("~" + flat[-1], r.get("usage", {}).get("prompt_tokens", 0),
                            r.get("usage", {}).get("completion_tokens", 0))
            usage = r.get("usage", {})
            return (m.group(0) if m else None,
                    usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        except Exception as e:
            if attempt == 3:
                return ("ERR:" + str(e)[:60], 0, 0)
            time.sleep(3 * (attempt + 1))


lock = threading.Lock()
fh = open(a.out, "a")
stats = {"n": 0, "in": 0, "out": 0}
jobs = []
for p in sample:
    for order in (0, 1):
        if (p["better"], p["worse"], order) in done:
            continue
        jobs.append((p, order))
print(f"[judge] {len(jobs)} calls to make (arm={a.arm})", flush=True)


def work(idx):
    while True:
        with lock:
            if not jobs:
                return
            p, order = jobs.pop()
        # order 0 shows the truly-better program as A; order 1 swaps. The judge sees no
        # cue either way, so a judge with no signal lands at 50% after averaging.
        first, second = ((p["better"], p["worse"]) if order == 0
                         else (p["worse"], p["better"]))
        pick, ti, to = ask(p["task"], first, second)
        correct = None
        if pick and pick.lstrip("~") in ("A", "B"):
            chose_first = (pick.lstrip("~") == "A")
            correct = int(chose_first == (order == 0))
        with lock:
            fh.write(json.dumps({
                "task": p["task"], "better": p["better"], "worse": p["worse"],
                "order": order, "pick": pick, "correct": correct,
                "truncated": bool(pick and pick.startswith("~")),
                "run": RUN[p["better"]]}) + "\n")
            fh.flush()
            stats["n"] += 1
            stats["in"] += ti
            stats["out"] += to
            if stats["n"] % 50 == 0:
                cost = stats["in"] / 1e6 * 1.0 + stats["out"] / 1e6 * 4.0
                print(f"  {stats['n']}/{len(jobs)} calls, ~CNY {cost:.2f}", flush=True)


ths = [threading.Thread(target=work, args=(i,)) for i in range(a.workers)]
for t in ths:
    t.start()
for t in ths:
    t.join()
fh.close()
cost = stats["in"] / 1e6 * 1.0 + stats["out"] / 1e6 * 4.0
print(f"[judge] done: {stats['n']} calls, ~CNY {cost:.2f} "
      f"({stats['in']:,} in / {stats['out']:,} out)", flush=True)
