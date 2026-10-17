"""Analytic counterexample, NOT a model, empirical result, or novel theorem.

Two executions have fixed marginal true artifact qualities N(0,1), N(.25,1).
The retained artifact keeps its realized quality; evaluation is noiseless here.
Positive coupling can improve the selected *program's* fresh-run mean yet
decrease the expected best *already produced artifact*. This is not evidence
of generalization or of the effect of the current data-RNG hook.
"""
import json
import math
from statistics import NormalDist

delta=.25
rows=[]
for rho in (0,.5,.9,.99,1):
    sd=math.sqrt(2*(1-rho))
    if sd:
        d=delta/sd
        prob=NormalDist().cdf(d)
        expected_max=delta*prob+sd*math.exp(-d*d/2)/math.sqrt(2*math.pi)
    else:
        prob=1.;expected_max=delta
    rows.append(dict(rho=rho,probability_choose_higher_mean=prob,
        fresh_selected_program_mean=delta*prob,
        expected_retained_artifact_quality=expected_max))
assert all(a['fresh_selected_program_mean']<=b['fresh_selected_program_mean'] for a,b in zip(rows,rows[1:]))
assert all(a['expected_retained_artifact_quality']>=b['expected_retained_artifact_quality'] for a,b in zip(rows,rows[1:]))
print(json.dumps(dict(means=[0,delta],marginal_variance=1,evaluations=2,rows=rows,
    assumptions='Execution randomness changes real, retained artifact quality; no validation measurement error. Gaussian toy only.',
    boundary='An objective-mismatch counterexample, not an MLE effect, new result or permission to change the frozen gate.')))
