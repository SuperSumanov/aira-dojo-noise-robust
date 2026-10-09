"""Frozen 1/2/4-permit neural batch comparison; no resource predictor."""
WIDTHS={'pipeline':1,'share2':2,'share4':4}
ORDERS=(('pipeline','share2','share4'),('share2','share4','pipeline'),('share4','pipeline','share2'))


def schedule():
    rows=[]
    for repeat,arms in enumerate(ORDERS):
        programs=(0,1,0,1) if repeat!=1 else (1,0,1,0)
        for arm in arms:
            block=len(rows)//4
            for position,program in enumerate(programs):
                rows.append(dict(index=len(rows),block=block,position=position,program=program,
                    arm=arm,repeat=repeat,source_seed=42,harness_seed=130701))
    return rows


def may_admit(index, indices, ready, admitted, closed, width):
    """Common all-ready barrier, then deterministic FIFO and work-conserving refill.

    Called under one host file lock. Closed means successful worker exit after
    interpreter close, not a candidate-result callback. Unknown failures abort.
    """
    if width not in (1,2,4) or index not in indices or len(set(indices))!=4:
        raise ValueError('fixed four-slot block')
    allowed=set(indices)
    if not closed <= admitted <= ready <= allowed:
        raise ValueError('impossible lifecycle')
    if len(admitted-closed)>width:
        raise ValueError('over-admission')
    if ready!=allowed or index in admitted or len(admitted-closed)>=width:
        return False
    return index==next(i for i in indices if i not in admitted)
