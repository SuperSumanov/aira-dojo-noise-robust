// Independent event reconstruction. No Python scheduler or receipt audit call.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const file = path.join(__dirname, 'quota-multiprocess-20261017.safe.json');
const hash = x => crypto.createHash('sha256').update(x).digest('hex');
const bytes = fs.readFileSync(file);
assert.equal(hash(bytes), 'a71e3d1ca428dae445528442343a765f7eadfa72a167c4bb78d735ab45dc6757');
const receipt = JSON.parse(bytes);
assert.equal(hash(fs.readFileSync(path.join(__dirname, 'quota_multiprocess_gate_20261017.py'))), receipt.reader_sha256);
assert.equal(hash(fs.readFileSync(path.join(__dirname, 'generation_quota_trial_20261017.py'))), receipt.entry_sha256);
assert.deepEqual(receipt.cases.map(x => x.mode), ['partitioned', 'pooled']);
const results = [];
for (const c of receipt.cases) {
  const requests = new Map(), waiting = new Map(), active = new Map(), completed = new Set();
  let peak = 0, borrowed = 0, lastTime = -Infinity;
  for (const event of c.events) {
    assert.ok(event.time >= lastTime); lastTime = event.time;
    const key = event.key;
    if (event.event === 'queued') {
      const r = event.request;
      assert.equal(r.role, 'analyze');
      assert.ok(c.worker_indices.includes(r.run));
      assert.ok(!requests.has(r.key));
      requests.set(r.key, r); waiting.set(r.key, r);
    } else if (event.event === 'admitted') {
      assert.ok(waiting.has(key));
      assert.ok(active.size < 4);
      const count = task => [...active.values()].filter(r => r.task === task).length;
      const options = [...waiting.values()].filter(r => c.mode === 'pooled' || count(r.task) < 2);
      options.sort((a,b) => a.requested-b.requested || a.run-b.run);
      assert.equal(options[0].key, key);
      const r = waiting.get(key);
      if (count(r.task) >= 2) borrowed++;
      active.set(key, r); waiting.delete(key); peak = Math.max(peak, active.size);
    } else if (event.event === 'released') {
      assert.ok(active.has(key) && !completed.has(key));
      completed.add(key); active.delete(key);
    } else throw new Error('unexpected CPU fixture event');
  }
  assert.equal(requests.size, 8); assert.equal(completed.size, 8);
  assert.equal(active.size, 0); assert.equal(waiting.size, 0);
  assert.equal(peak, 4); assert.equal(borrowed, c.mode === 'pooled' ? 4 : 0);
  const expected = c.mode === 'partitioned' ? [[2,0,2,0],[2,2,2,2],[0,2,0,2]] : [[4,0,0,0],[4,0,0,4],[0,4,0,0]];
  assert.deepEqual(c.snapshots.map(x => [x.active_a,x.active_b,x.waiting_a,x.waiting_b]), expected);
  assert.deepEqual([c.gpu_calls,c.kernel_calls,c.model_calls],[0,0,0]);
  assert.equal(c.passed, true);
  results.push({mode:c.mode,requests:requests.size,released:completed.size,peak_active:peak,borrowed});
}
const result = {passed:true,receipt_sha256:hash(bytes),verifier_sha256:hash(fs.readFileSync(__filename)),results,
  interpretation:'Actual CPU multiprocess installed generation permits only; no live model/GPU/search improvement.'};
fs.writeFileSync(path.join(__dirname,'quota-multiprocess-independent-20261017.json'), JSON.stringify(result,null,2)+'\n', {flag:'wx'});
console.log(JSON.stringify(result));
