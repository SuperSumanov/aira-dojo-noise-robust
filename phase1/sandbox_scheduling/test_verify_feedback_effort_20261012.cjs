const assert=require('node:assert/strict');
const {csvCellMatches,csvParse,verify}=require('./verify_feedback_effort_20261012.cjs');
for(const [v,s] of [[1,'1.0'],[1,'1'],[3.9e-8,'3.9e-08'],[0,'0.0'],[-0,'-0.0'],[true,'True'],[false,'False'],[null,''],['medium','medium']]) assert(csvCellMatches(v,s));
for(const [v,s] of [[0,''],[0,' '],[1,'1.001'],[Infinity,'Infinity'],[NaN,'NaN'],[true,'1'],[null,'0'],[0,'-0.0']]) assert(!csvCellMatches(v,s));
assert.deepEqual(csvParse('a,b\r\n"x,y",1.0\r\n'),[['a','b'],['x,y','1.0']]);
const closed=verify(require('node:path').join(__dirname,'feedback_effort_v1_closed'));
assert.equal(closed.complete,0);assert.equal(closed.assigned,48);assert.equal(closed.original_gate,false);
console.log(JSON.stringify({scalar_cases:17,quoted_csv:true,old_failure_denominator:48,no_result_change:true}));
