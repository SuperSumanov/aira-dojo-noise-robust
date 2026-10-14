// Independently check the safe closed-run export, not its raw code/journal join.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const digest = b => crypto.createHash('sha256').update(b).digest('hex');
const base = __dirname;
const bytes = fs.readFileSync(path.join(base, 'role_origin_20261014_cpu/result.json'));
const r = JSON.parse(bytes);
assert.equal(digest(bytes), 'c5cc1cbedb89acf823158170949260164369766b160967626654b19af10c8bd2');
const primary = JSON.parse(fs.readFileSync(path.join(base, 'weight_effort_18253_closed/runs.json')));
const summary = fs.readFileSync(path.join(base, 'weight_effort_18253_closed/summary.json'));
assert.equal(digest(summary), r.primary_summary_sha256);
assert.equal(digest(fs.readFileSync(path.join(base, 'closed_role_origin_20261014.py'))), r.source_sha256);
assert.equal(r.original_quality_gate, false);
assert.equal(r.rows.length, 101);
assert.equal(r.candidate_returns, r.rows.length);
assert.equal(new Set(r.rows.map(x => `${x.index}:${x.candidate}`)).size, r.rows.length);
assert.equal(r.endpoints.length, 32);
assert.equal(new Set(r.endpoints.map(x => x.index)).size, 32);
assert.equal(primary.length, 32);
const countOrigins = {};
for (const row of r.rows) {
  countOrigins[row.origin] = (countOrigins[row.origin] || 0) + 1;
  assert.equal(row.valid ? Number.isFinite(row.score) : row.score === null, true);
}
assert.deepEqual(countOrigins, r.origin_counts);
for (const p of primary) {
  const rows = r.rows.filter(x => x.index === p.index);
  const e = r.endpoints.find(x => x.index === p.index);
  const sign = p.task === 'aerial-cactus-identification' ? 1 : -1;
  assert.equal(rows.length, p.candidate_returns);
  assert.equal(rows.filter(x => x.valid).length, p.valid_returns);
  assert.equal(e.task, p.task);
  assert.equal(e.arm, p.arm);
  const best = [p.initial_score, ...rows.filter(x => x.valid).map(x => x.score)]
    .sort((a, b) => sign * (b - a))[0];
  assert.equal(best, p.score);
  assert.equal(e.best, p.score);
  const origins = best === p.initial_score ? ['warm'] :
    [...new Set(rows.filter(x => x.valid && x.score === best).map(x => x.origin))].sort();
  assert.deepEqual(e.best_origins, origins);
  for (const row of rows) {
    assert.equal(row.task, p.task);
    assert.equal(row.arm, p.arm);
    assert.equal(row.above_common_warm, row.valid && sign * (row.score - p.initial_score) > 0);
  }
}
assert.equal(r.groups.length, 8);
for (const g of r.groups) {
  const own = r.rows.filter(x => x.arm === g.arm && x.task === g.task);
  const ends = r.endpoints.filter(x => x.arm === g.arm && x.task === g.task);
  assert.equal(ends.length, 4);
  const roles = [...new Set(own.map(x => x.origin))].sort();
  assert.deepEqual(Object.keys(g.origins).sort(), roles);
  for (const role of roles) {
    const rows = own.filter(x => x.origin === role);
    assert.deepEqual(g.origins[role], {returned: rows.length,
      valid: rows.filter(x => x.valid).length, above_warm: rows.filter(x => x.above_common_warm).length});
  }
  const best = (g.task === 'aerial-cactus-identification' ? Math.max : Math.min)(...ends.map(x => x.best));
  assert.equal(g.pool_best, best);
  assert.deepEqual(g.pool_best_origins,
    [...new Set(ends.filter(x => x.best === best).flatMap(x => x.best_origins))].sort());
}
const valid = r.rows.filter(x => x.valid);
const ambiguous = valid.filter(x => ['ambiguous', 'unmatched'].includes(x.origin));
assert.equal(valid.length, 46);
assert.equal(ambiguous.length, 0);
console.log(JSON.stringify({safe_export_sha256: digest(bytes), assigned: primary.length,
  candidate_returns: r.rows.length, valid_returns: valid.length,
  valid_origin_unresolved: ambiguous.length, endpoint_matches: r.endpoints.length,
  task_arm_cells: r.groups.length,
  debug_best_cells: r.groups.filter(x => x.pool_best_origins.includes('debug')).length,
  original_quality_gate: r.original_quality_gate, independent_safe_export_checks: 'pass',
  raw_join_independently_recomputed: false, causal_ablation: false}, null, 2));
