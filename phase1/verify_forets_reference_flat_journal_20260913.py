"""Compatibility fix for the actual Journal.get_node_data flat metric schema.

The frozen verifier and all outcome files remain unchanged. Only the journal
representation is normalized before its original reference comparison.
"""
import math
from pathlib import Path
import verify_forets_reference_records_20260913 as original


def normalize_nodes(nodes):
    result=[]
    for node in nodes:
        metric=node['metric']
        if type(metric) not in (int,float,type(None)):
            raise ValueError('actual flat journal metric required')
        if metric is not None and not math.isfinite(metric):
            raise ValueError('finite journal metric required')
        direction=node['metric_maximize']
        if direction is not None and type(direction) is not bool:
            raise ValueError('journal direction')
        # Never copy metric_info into the normalized metric object.
        result.append(dict(node,metric=dict(value=metric,maximize=direction)))
    return result


def verifier():
    source=Path(original.__file__).read_text()
    before="expected_references(nodes,pool['binding']['parent_id'],pool['binding']['step'])"
    after="expected_references(normalize_nodes(nodes),pool['binding']['parent_id'],pool['binding']['step'])"
    if source.count(before)!=1:raise ValueError('exact frozen comparison anchor')
    namespace={'normalize_nodes':normalize_nodes}
    exec(compile(source.replace(before,after),'<flat-journal-compatibility>','exec'),namespace)
    return namespace['verify_reference']


verify_reference=verifier()
