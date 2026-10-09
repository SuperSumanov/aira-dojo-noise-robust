"""CPU topology and distinct Slurm-step identities; no index-number guessing."""
import os
from pathlib import Path


def cpu_topology():
    rows = []
    for cpu in sorted(os.sched_getaffinity(0)):
        path = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        rows.append(dict(logical_cpu=cpu, socket=int((path/'physical_package_id').read_text()),
                         core=int((path/'core_id').read_text())))
    return rows


def cores(rows):
    if not rows or len({r['logical_cpu'] for r in rows}) != len(rows):
        return set()
    return {(r['socket'], r['core']) for r in rows}


def verify_allocation(execution, service):
    ec, sc = cores(execution.get('cpu_topology', [])), cores(service.get('cpu_topology', []))
    eu, su = execution.get('gpu_uuid'), service.get('gpu_uuids', [])
    el={r['logical_cpu'] for r in execution.get('cpu_topology', [])}
    sl={r['logical_cpu'] for r in service.get('cpu_topology', [])}
    return bool(len(ec) == 6 and len(sc) == 12 and not ec & sc and not el & sl
        and set(execution.get('affinity', [])) == {r['logical_cpu'] for r in execution.get('cpu_topology', [])}
        and len(su) == len(set(su)) == 2 and eu and eu not in su
        and execution.get('job') == service.get('job')
        and execution.get('step') != service.get('step'))


def verify(execution, service, workers):
    return bool(verify_allocation(execution, service) and len(workers) == 4
        and all(w.get('job') == execution.get('job') and w.get('step') == execution.get('step')
                and w.get('gpu_uuids') == [execution.get('gpu_uuid')] for w in workers))
