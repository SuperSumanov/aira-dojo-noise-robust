"""Closed18770 mechanism screen; no new scoring, raw code or model responses.

Observed workload and resource integrals are descriptive, not counterfactual
performance. A successful GPU lease is not a successful model computation.
"""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

PIN = "a7cc9780c927cdeac3fc1effb214643a387353122e1fa542d3a40116b248d477"
RESULT = "bef23ec17e2fd3e561a690e2aa7328c3df592cb315070fbc293d69c4ce84def5"
TASKS = ("aerial-cactus-identification", "denoising-dirty-documents")

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def events(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s]

def integrate(samples, start, end):
    span = area = nonzero = 0.0
    gaps = []
    for a, b in zip(samples, samples[1:]):
        assert b["time"] > a["time"]
        dt = max(0, min(end, b["time"]) - max(start, a["time"]))
        assert 0 <= a["utilization"] <= 100
        span += dt
        area += dt * a["utilization"]
        nonzero += dt * (a["utilization"] > 0)
        if dt:
            gaps.append(b["time"] - a["time"])
    assert span > 0 and 0 < end-start
    return dict(covered_seconds=span, coverage=span/(end-start),
                utilization_pct=area/span, nonzero_fraction=nonzero/span,
                max_gap=max(gaps), samples=len(samples))

def main(root, out):
    assert root.name == "scheduling-pooling-20261016-v3"
    assert sha(root/"plan.json") == PIN
    rp = root/"readout-20261016-v1"
    assert sha(rp/"summary.json") == RESULT
    summary = read(rp/"summary.json")
    assert summary["complete"] == 32 and summary["structural_gate"]
    plan = read(root/"plan.json")
    primary = {r["index"]: r for r in read(rp/"runs.json")}
    calls = read(rp/"effort.json")
    pools = []
    hashes = {}
    def tracked(p):
        before = sha(p); v = read(p); assert before == sha(p)
        hashes[str(p.relative_to(root))] = before
        return v
    for b in range(4):
        slot = tracked(root/f"block-{b}/budget-slot.json")
        zero, end = slot["start"], slot["start"]+slot["actual_seconds"]
        raw = tracked(root/f"block-{b}/execution-telemetry.json")
        # gpu_sample already records its own time; preserve each actual sample
        # timestamp rather than replacing it with the outer loop timestamp.
        lane_samples = [[dict(x["devices"][i]) for x in raw] for i in range(4)]
        telem = [dict(integrate(s, zero, end),
                      peak_memory_mib=max(x["memory_mib"] for x in s))
                 for s in lane_samples]
        from effort_pressure_diagnostic_20261012 import structural_events, state_changes
        gchanges, gaudit = state_changes(structural_events(root/f"generation-{b}/events.jsonl", True), 4)
        q = read(rp/f"queue-{b}.json")
        waiting, active, leases, cancels = {}, {}, [], []
        held = full = queued = 0.0
        prev = zero
        for e in q:
            t = e["time"]; assert zero <= t <= end and t >= prev
            held += (t-prev)*len(active)
            full += (t-prev)*(len(active)==4)
            queued += (t-prev)*len(waiting)
            k=e["key"]
            if e["event"] == "queued": waiting[k]=t
            elif e["event"] == "admitted":
                active[k]=(t, waiting.pop(k), e["device"])
            elif e["event"] == "released":
                a,w,d=active.pop(k)
                leases.append(dict(index=int(k.split(":")[0]), seq=int(k.split(":")[1]),
                    device=d, queued_at=w-zero, admitted_at=a-zero, released_at=t-zero,
                    wait=a-w, hold=t-a))
            elif e["event"] == "queue_cancelled":
                cancels.append(dict(index=int(k.split(":")[0]), wait=t-waiting.pop(k)))
            else: raise ValueError("unexpected queue event")
            assert len(active)==e["active"] and len(waiting)==e["queued"]
            prev=t
        assert not active and not waiting
        task_rows=[]
        for task in TASKS:
            sign=1 if task==TASKS[0] else -1
            spec=[s for s in plan["schedule"] if s["block"]==b and s["task"]==task]
            rows=[]; all_events=[]
            for s in spec:
                i=s["index"]; ep=root/f"episode-{i}"
                deadline=tracked(ep/"deadline.json")
                offset=datetime.fromisoformat(deadline["started_utc"]).timestamp()-zero
                rs=primary[i]; initial=rs["initial_score"]
                returned=[]; valid=[]
                for p in sorted(ep.glob("candidate-*.json")):
                    if ".private." in p.name: continue
                    c=tracked(p)
                    if c["elapsed_seconds"]>1020: continue
                    returned.append(c)
                    if c["valid"] is True and c["exit_code"]==0 and not c["timed_out"]:
                        assert type(c["score"]) in (int,float) and math.isfinite(c["score"])
                        valid.append(dict(index=i, at=c["elapsed_seconds"]+offset, score=c["score"]))
                assert len(returned)==rs["candidate_returns"] and len(valid)==rs["valid_returns"]
                assert abs(max([initial]+[v["score"] for v in valid],key=lambda x:sign*x)-rs["score"])<1e-12
                own=[x for x in calls if x["index"]==i]
                rows.append(dict(index=i, candidate_returns=len(returned), valid_returns=len(valid),
                    code_calls=len([x for x in own if x["role"]!="analyze"]),
                    returned_code_calls=len([x for x in own if x["role"]!="analyze" and x["success"]]),
                    failed_code_calls=len([x for x in own if x["role"]!="analyze" and not x["success"]]),
                    code_seconds=sum(x["seconds"] for x in own if x["role"]!="analyze"),
                    analyze_seconds=sum(x["seconds"] for x in own if x["role"]=="analyze"),
                    execution_wait=sum(x["wait"] for x in leases+cancels if x["index"]==i),
                    execution_hold=sum(x["hold"] for x in leases if x["index"]==i),
                    score=rs["score"]))
                all_events.extend(valid)
            best=primary[spec[0]["index"]]["initial_score"]; records=[]
            for e in sorted(all_events,key=lambda x:(x["at"],x["index"])):
                if sign*(e["score"]-best)>1e-12:
                    best=e["score"]; records.append(e)
            ref=next(r for r in summary["by_pool"] if r["block"]==b and r["task"]==task)
            assert abs(best-ref["best"])<1e-12
            task_rows.append(dict(task=task, rows=rows, valid_events=all_events, records=records))
        pools.append(dict(block=b, mode=plan["schedule"][b*8]["pool_mode"],
            duration=end-zero, gpu_telemetry=telem, generation_changes=gchanges, generation_audit=gaudit,
            lease_held_gpu_seconds=held,
            lease_full_seconds=full, all_queue_wait_seconds=queued,
            lease_held_fraction=held/(4*(end-zero)), leases=leases,
            cancelled=cancels, tasks=task_rows))
    output=dict(plan_sha256=PIN, primary_summary_sha256=RESULT,
        source_sha256=sha(Path(__file__)), new_gpu_jobs=0, new_scores=0, pools=pools, hashes=hashes,
        limits=["Post-hoc observed histories; no changed-arrival counterfactual or causal mediation.",
                "Sampled GPU utilization is not kernel duration; lease includes startup and cleanup.",
                "Reused two development tasks and shared service; not independent runs or broad generalization.",
                "Fewer record improvements does not prove non-record candidates wasted.",
                "No primary gate or experiment original modified."])
    with out.open("x") as f: json.dump(output,f,indent=2,allow_nan=False)
    print(json.dumps(dict(output=str(out),sha256=sha(out),
        pools=[dict(block=p["block"],mode=p["mode"],
            lease_held_fraction=p["lease_held_fraction"],
            mean_sample_utilization=statistics.mean(s["utilization_pct"] for s in p["gpu_telemetry"]),
            min_coverage=min(s["coverage"] for s in p["gpu_telemetry"]),
            peak_memory_mib=max(s["peak_memory_mib"] for s in p["gpu_telemetry"]),
            generation_audit=p["generation_audit"],
            tasks=[dict(task=t["task"],valid=sum(r["valid_returns"] for r in t["rows"]),
                records=len(t["records"]),code_seconds=sum(r["code_seconds"] for r in t["rows"]),
                analyze_seconds=sum(r["analyze_seconds"] for r in t["rows"]),
                wait=sum(r["execution_wait"] for r in t["rows"]),
                hold=sum(r["execution_hold"] for r in t["rows"])) for t in p["tasks"]]) for p in pools])))

if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("root",type=Path);a.add_argument("out",type=Path)
    opts=a.parse_args();main(opts.root,opts.out)
