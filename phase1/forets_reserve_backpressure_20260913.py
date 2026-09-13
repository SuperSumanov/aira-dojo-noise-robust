"""Bounded pre-dispatch backpressure; never retries an HTTP request or frees debt."""
import logging
import time


def reserve_wait(path, scope, attempt_id, amount, *, connect, authorize, auth,
                 stopped_error, clock=time.monotonic, wall=time.time,
                 sleep=time.sleep, max_wait=90., poll=.1):
    if type(amount) is not int or amount not in (700000000, 2600000000):
        raise stopped_error('unapproved request reservation')
    began = clock()
    waits = 0
    while True:
        # This includes the original minimum remaining search-time margin.
        authorize()
        db = connect(path)
        try:
            cap = db.execute('SELECT cap FROM scopes WHERE scope=?', (scope,)).fetchone()
            rows = db.execute('SELECT scope,held,state,created FROM calls').fetchall()
            total = sum(r[1] for r in rows)
            used = sum(r[1] for r in rows if r[0] == scope)
            count = sum(r[0] == scope for r in rows)
            if not cap or count >= 100:
                raise stopped_error('missing scope or request limit')
            if total + amount <= auth['total'] and used + amount <= cap[0]:
                authorize()  # Check again after acquiring the database lock.
                db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?)',
                           (attempt_id, scope, amount, None, 'unresolved', wall()))
                db.commit()
                if waits:
                    logging.getLogger(__name__).info('reservation_backpressure seconds=%.6f polls=%d', clock()-began, waits)
                return
            # Fresh unresolved charges MAY settle. Old/unknown debt remains held.
            fresh = [r for r in rows if r[2] == 'unresolved' and 0 <= wall()-r[3] <= 135.]
            possible_total = total - sum(r[1] for r in fresh)
            possible_used = used - sum(r[1] for r in fresh if r[0] == scope)
            permanent = (possible_total + amount > auth['total'] or possible_used + amount > cap[0])
            if permanent or clock()-began >= max_wait:
                logging.getLogger(__name__).warning(
                    'reservation_rejected total_nusd=%d scope_nusd=%d amount_nusd=%d fresh=%d waited=%.6f permanent=%s',
                    total, used, amount, len(fresh), clock()-began, permanent)
                raise stopped_error('insufficient pre-request reserve')
        finally:
            # No sleeping while holding a transaction: settlement must proceed.
            db.close()
        waits += 1
        sleep(min(poll, max_wait-(clock()-began)))


def patch_budget(text):
    start = text.index('def reserve(path, scope, attempt_id, amount=None):')
    end = text.index('\n\ndef settle(', start)
    return text[:start] + '''def reserve(path, scope, attempt_id, amount=None):
    from dojo.solvers.fore_ts.wallclock import admit_request
    from dojo.solvers.fore_ts.reserve_backpressure import reserve_wait
    return reserve_wait(path, scope, attempt_id, RESERVE if amount is None else amount,
        connect=connect, authorize=admit_request, auth=AUTH, stopped_error=BudgetStopped)
''' + text[end:]
