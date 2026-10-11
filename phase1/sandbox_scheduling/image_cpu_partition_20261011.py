"""Partition four allocated physical cores, not four SMT thread identifiers."""
def partition(rows):
    groups={}
    seen=set()
    for row in rows:
        cpu=row['logical_cpu'];key=(row['socket'],row['core'])
        if cpu in seen:raise ValueError('duplicate logical CPU')
        seen.add(cpu);groups.setdefault(key,[]).append(cpu)
    if len(groups)!=4:raise ValueError('four physical cores required')
    # One visible thread per assigned physical core; siblings never cross runs.
    selected=[min(groups[key]) for key in sorted(groups)]
    return selected[:2],selected[2:]
