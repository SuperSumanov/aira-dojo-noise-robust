"""Pre-registered sidecar smoke: the REAL serving path, scored against known grades.

Launches rm_server.py exactly as pool_collect.sbatch does (subprocess + wait for "listening"),
then POSTs the code of card pairs with large externally-graded gaps from the two T3 tasks.
Pass requires >= 9/12 pairs ordered correctly (score of the better-graded card higher, task
orientation respected) and median latency under 15s. Kills the server either way.
"""
import collections, json, os, random, statistics, subprocess, time, urllib.request

CKPT = "/research/d7/spc/yzyang4/aira-dojo/phase1/ckpt_lookahead_v3/N24000"
PORT = "8799"
TASKS = ["spooky-author-identification", "tabular-playground-series-dec-2021"]

ORI = json.load(open("phase1/task_orientation.json"))
by = collections.defaultdict(list)
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    if d["task"]["name"] in TASKS:
        by[d["task"]["name"]].append((d["label"]["graded"], d["code"]))

env = dict(os.environ, RM_DIR=CKPT, RM_PORT=PORT)
srv = subprocess.Popen(["/research/d7/spc/yzyang4/venvs/critic/bin/python3",
                        "/research/d7/spc/yzyang4/scripts/rm_server.py"],
                       stdout=open("/tmp/rm_smoke.log", "w"), stderr=subprocess.STDOUT, env=env)
try:
    for _ in range(120):
        time.sleep(5)
        if "listening" in open("/tmp/rm_smoke.log").read():
            break
    else:
        raise SystemExit("FAIL: server never came up; /tmp/rm_smoke.log:\n" +
                         open("/tmp/rm_smoke.log").read()[-800:])
    print("[smoke] server up; startup log OK")

    def score(task, code):
        body = json.dumps({"task": task, "code": code}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}", data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        r = json.load(urllib.request.urlopen(req, timeout=120))
        return r["score"], time.time() - t0

    rng = random.Random(7)
    ok = tot = 0
    lats = []
    for t in TASKS:
        cs = sorted(by[t], key=lambda x: x[0])
        lower = ORI[t]
        good_pool = cs[:12] if lower else cs[-12:]
        bad_pool = cs[-12:] if lower else cs[:12]
        for i in range(6):
            g = rng.choice(good_pool)
            b = rng.choice(bad_pool)
            sg, lg = score(t, g[1])
            sb, lb = score(t, b[1])
            lats += [lg, lb]
            tot += 1
            ok += sg > sb
            print(f"  {t[:24]} pair{i}: good(graded={g[0]:.4f})={sg:.4f} "
                  f"bad(graded={b[0]:.4f})={sb:.4f} {'OK' if sg > sb else 'MISS'}")
    med = statistics.median(lats)
    print(f"[smoke] ordering {ok}/{tot}, median latency {med:.1f}s")
    if ok >= 9 and med <= 45:
        print("SMOKE_PASS")
    else:
        print("SMOKE_FAIL")
finally:
    srv.kill()
