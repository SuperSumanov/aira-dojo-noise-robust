"""Fill in orientation for tasks the file does not cover, and audit the ones it does.

Five v9 tasks are absent from task_orientation.json. The pair builders use
ORI.get(task, False) -- absent means higher-is-better by default -- and two of the five
(denoising RMSE, dog-breed logloss) are lower-is-better, so building pairs without this fix
would invert every label on those tasks.

Derivation is mechanical, not judgement: the gold medal threshold is by definition the best
of the three, so gold < bronze forces lower-is-better. Thresholds are read off the cards.
The same rule is then run over the tasks ALREADY in the file as an audit -- if the recorded
orientation disagrees with the medal geometry anywhere, that is a standing label bug and
gets printed loudly rather than silently overwritten.
"""
import collections, json

ORI = json.load(open("phase1/task_orientation.json"))
th = {}
for l in open("phase1/cards_current_v9.jsonl"):
    d = json.loads(l)
    t = d["task"]["name"]
    if t not in th:
        m = d["task"].get("medal_thresholds") or {}
        if m.get("gold") is not None and m.get("bronze") is not None:
            th[t] = (float(m["gold"]), float(m["bronze"]))

print("audit of tasks already in the file (recorded vs medal geometry):")
bad = 0
for t, lower in sorted(ORI.items()):
    if t not in th:
        print(f"  {t[:46]:48s} recorded={lower!s:5s} thresholds ABSENT -- cannot audit")
        continue
    g, b = th[t]
    if g == b:
        print(f"  {t[:46]:48s} recorded={lower!s:5s} gold==bronze -- cannot audit")
        continue
    derived = g < b
    ok = derived == bool(lower)
    bad += 0 if ok else 1
    print(f"  {t[:46]:48s} recorded={lower!s:5s} derived={derived!s:5s} "
          f"{'OK' if ok else '*** MISMATCH ***'}")

print("\nfilling in the missing tasks:")
added = {}
for t, (g, b) in sorted(th.items()):
    if t in ORI:
        continue
    if g == b:
        print(f"  {t}: gold == bronze, refusing to guess -- leave for manual review")
        continue
    added[t] = g < b
    print(f"  {t[:46]:48s} gold={g} bronze={b} -> lower_is_better={added[t]}")

if bad:
    print(f"\n*** {bad} recorded orientations contradict medal geometry -- NOT writing; "
          f"resolve those first")
elif added:
    ORI.update(added)
    with open("phase1/task_orientation.json", "w") as f:
        json.dump(ORI, f, indent=1, sort_keys=True)
    print(f"\nwrote task_orientation.json: {len(ORI)} tasks ({len(added)} added)")
else:
    print("\nnothing to add")
