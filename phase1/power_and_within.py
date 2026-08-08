"""Two questions the five dead directions raise, and one design that might dodge them.

Q1 POWER. Every direction died the same way: an effect near 0.55 that cannot be resolved
   from 0.50 once the CI is clustered by run. That is not a modelling failure, it is a
   sample-size fact, and it has a number. From each observed CI, back out the run-level
   SE, then compute how many independent runs would be needed to resolve the observed
   effect at 80% power. If the answer is "a few hundred more", the project has a route;
   if it is "tens of thousands", it does not.

Q2 WITHIN-RUN DESIGN. Between-run comparisons pay the full run-level variance. Paired
   comparisons INSIDE one run cancel it -- which is exactly why the decision-point result
   (siblings of one parent) reached p=1.1e-14 on far fewer pairs than the flip set managed.
   So: can the repair question be posed within-run? Count runs holding >=2 scoreless nodes
   whose repairs disagreed. If that count is decent, axis A gets a well-powered form that
   the cross-run pairing threw away.

Usage: python phase1/power_and_within.py
"""
import collections, json, math, statistics

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


print("=" * 78)
print("Q1 -- how many independent runs would each dead direction have needed?")
print("=" * 78)
# (name, observed effect, CI half-width as measured, runs behind that CI)
OBS = [
    ("L1 flip set",        0.5474, (0.6574 - 0.4277) / 2, 23),
    ("SR-wrong pairs",     0.5586, (0.6246 - 0.4713) / 2, 27),
    ("repair, code_len",   0.5527, (0.7112 - 0.4337) / 2, 29),
]
print(f"{'analysis':20s} {'effect':>7} {'half-CI':>8} {'runs':>5} "
      f"{'runs for 80% power':>20} {'x more':>7}")
print("-" * 74)
need_max = 0
for name, eff, hw, nr in OBS:
    se = hw / 1.96
    # SE scales as 1/sqrt(runs); for 80% power at alpha=.05 two-sided need
    # effect >= (1.96 + 0.84) * SE_target
    se_target = abs(eff - 0.5) / 2.80
    if se_target <= 0:
        continue
    need = nr * (se / se_target) ** 2
    need_max = max(need_max, need)
    print(f"{name:20s} {eff:7.4f} {hw:8.4f} {nr:5d} {need:20.0f} {need/nr:7.1f}")
print(f"\nheld-out runs are ~20% of the corpus, so the TOTAL run count implied is ~5x those")
print(f"numbers: roughly {need_max*5:,.0f} runs for the most demanding of them.")
print(f"corpus today: {len(set(RUN.values()))} runs.")

print()
print("=" * 78)
print("Q2 -- does the repair question have a WITHIN-RUN form?")
print("=" * 78)
scoreless = {c for c, d in cards.items()
             if fin(d["obs"].get("val_at_low")) is None}
outcome = {}
for c, d in cards.items():
    p = d["lineage"].get("parent_id")
    if d["lineage"].get("op") == "Debug" and p in scoreless:
        outcome[p] = max(outcome.get(p, 0),
                         int(fin(d["obs"].get("val_at_low")) is not None))
by_run = collections.defaultdict(list)
for c, y in outcome.items():
    if c in RUN:
        by_run[RUN[c]].append((c, y))
mixed = {r: v for r, v in by_run.items() if len({y for _, y in v}) > 1}
print(f"runs containing >=1 labelled repair: {len(by_run)}")
print(f"runs where repairs DISAGREE (>=1 success and >=1 failure): {len(mixed)}")
npairs = sum(sum(1 for _, y in v if y == 1) * sum(1 for _, y in v if y == 0)
             for v in mixed.values())
print(f"within-run discordant pairs available: {npairs}")
sizes = sorted((len(v) for v in mixed.values()), reverse=True)
print(f"labelled repairs per informative run: {sizes[:12]}{' ...' if len(sizes) > 12 else ''}")
byt = collections.Counter(cards[v[0][0]]["task"]["name"] for v in mixed.values())
print(f"informative runs by task: { {t[:24]: n for t, n in byt.most_common()} }")
print(f"\n  the unit here is the RUN ({len(mixed)} of them), and a within-run paired test")
print(f"  cancels run-level variance -- compare with the 30 test runs the cross-run")
print(f"  pairing left us. Still small: a paired sign test over {len(mixed)} runs resolves")
lo_eff = 1.96 * math.sqrt(0.25 / max(len(mixed), 1))
print(f"  effects of about +-{lo_eff:.3f} around 0.5, i.e. {0.5 + lo_eff:.3f} or better.")
print(f"  VERDICT: {'worth building' if len(mixed) >= 60 else 'still underpowered'}")
