"""One USD10 campaign ledger under the user's CNY100 authorization.

Only identifiers and charges, never credentials/prompts. All unresolved requests
retain their full reservation, including cancellation, HTTP errors and crashes.
Integer nano-USD avoids floating point budget drift. No automatic reinitialize.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from contextlib import closing
from decimal import Decimal, ROUND_CEILING

MODEL = 'qwen/qwen3-coder-flash'
UNIT = 10**9
RESERVE = 700_000_000
PROVIDER = dict(only=['alibaba'], allow_fallbacks=False, require_parameters=True,
                max_price=dict(prompt=0.65, completion=2.6, request=0))
AUTH = dict(version=1, currency='USD', total=10*UNIT, user_cny_cap=100,
            conservative_cny_per_usd=8, fee_multiplier='1.10',
            accounted_cny_ceiling='88.00', model=MODEL, provider=PROVIDER,
            reservation=RESERVE, context_tokens=1000000, output_tokens=8192,
            run_limit=1_100_000_000, route_limit=1_200_000_000,
            serial_transport_per_worker=True)
AUTH_RAW = json.dumps(AUTH, sort_keys=True, separators=(',', ':')).encode()
AUTH_SHA = hashlib.sha256(AUTH_RAW).hexdigest()


class BudgetStopped(RuntimeError):
    pass


def initialize(path, run_ids):
    path = Path(path)
    if len(run_ids) != 8 or len(set(run_ids)) != 8 or 'route' in run_ids:
        raise ValueError('exact eight unique scopes required')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
          CREATE TABLE auth (digest TEXT NOT NULL, body TEXT NOT NULL, stopped INTEGER NOT NULL);
          CREATE TABLE scopes (scope TEXT PRIMARY KEY, cap INTEGER NOT NULL);
          CREATE TABLE calls (id TEXT PRIMARY KEY, scope TEXT NOT NULL, held INTEGER NOT NULL,
            cost INTEGER, state TEXT NOT NULL, created REAL NOT NULL);
        ''')
        db.execute('INSERT INTO auth VALUES (?,?,0)', (AUTH_SHA, AUTH_RAW.decode()))
        db.executemany('INSERT INTO scopes VALUES (?,?)',
                       [('route', AUTH['route_limit'])] + [(x, AUTH['run_limit']) for x in run_ids])


def connect(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise BudgetStopped('existing campaign ledger required')
    db = sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, timeout=15)
    try:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute('SELECT digest,body,stopped FROM auth').fetchall()
        if len(rows) != 1 or rows[0][:2] != (AUTH_SHA, AUTH_RAW.decode()):
            raise BudgetStopped('authorization drift')
        if rows[0][2]:
            raise BudgetStopped('campaign stopped')
        return db
    except BaseException:
        db.close()
        raise


def reserve(path, scope, attempt_id):
    db = connect(path)
    try:
        cap = db.execute('SELECT cap FROM scopes WHERE scope=?', (scope,)).fetchone()
        total = db.execute('SELECT COALESCE(SUM(held),0) FROM calls').fetchone()[0]
        used = db.execute('SELECT COALESCE(SUM(held),0) FROM calls WHERE scope=?', (scope,)).fetchone()[0]
        if not cap or total + RESERVE > AUTH['total'] or used + RESERVE > cap[0]:
            raise BudgetStopped('insufficient pre-request reserve')
        db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?)',
                   (attempt_id, scope, RESERVE, None, 'unresolved', time.time()))
        db.commit()
    finally:
        db.close()


def settle(path, attempt_id, usage):
    """Only explicit valid total account cost frees a reservation; never estimates."""
    value = usage.get('cost') if isinstance(usage, dict) else None
    cost = None
    if type(value) in (int, float, str):
        try:
            parsed = Decimal(str(value))
            if parsed.is_finite() and parsed >= 0:
                cost = int((parsed * UNIT).to_integral_value(rounding=ROUND_CEILING))
        except (ValueError, ArithmeticError):
            pass
    db = connect(path)
    try:
        row = db.execute('SELECT held,state FROM calls WHERE id=?', (attempt_id,)).fetchone()
        if not row or row[1] != 'unresolved':
            raise BudgetStopped('unknown or duplicate settlement')
        if cost is None:
            # Keep full liability and stop, rather than charging unknown as zero.
            db.execute('UPDATE auth SET stopped=1')
        else:
            db.execute('UPDATE calls SET held=?,cost=?,state=? WHERE id=?',
                       (cost, cost, 'settled', attempt_id))
            if cost > RESERVE:
                db.execute('UPDATE auth SET stopped=1')
        db.commit()
    finally:
        db.close()
    if cost is None or cost > RESERVE:
        raise BudgetStopped('missing charge or price bound violation')
    return cost / UNIT


def snapshot(path):
    with closing(sqlite3.connect(Path(path).as_uri()+'?mode=ro', uri=True)) as db:
        digest, body, stopped = db.execute('SELECT digest,body,stopped FROM auth').fetchone()
        if (digest, body) != (AUTH_SHA, AUTH_RAW.decode()):
            raise BudgetStopped('authorization drift')
        rows = db.execute('SELECT scope,COUNT(*),SUM(held),SUM(COALESCE(cost,0)), '
                          'SUM(state="unresolved") FROM calls GROUP BY scope ORDER BY scope').fetchall()
    return dict(authorization_sha256=digest, stopped=bool(stopped),
                accounted_usd=sum(r[2] for r in rows)/UNIT,
                settled_usd=sum(r[3] for r in rows)/UNIT,
                unresolved=sum(r[4] for r in rows), calls=sum(r[1] for r in rows),
                scopes=[dict(scope=r[0], calls=r[1], held_usd=r[2]/UNIT,
                             settled_usd=r[3]/UNIT, unresolved=r[4]) for r in rows])
