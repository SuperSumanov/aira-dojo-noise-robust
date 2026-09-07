"""Independent GLS construction; does not import the spectral producer."""
import math
import numpy as np

def direct_gls(n,pairs,targets,rho):
    b=np.zeros((len(pairs),n));target=np.zeros((len(targets),n))
    for i,pair in enumerate(pairs):b[i,pair[0]]=1.;b[i,pair[1]]=-1.
    for i,pair in enumerate(targets):target[i,pair[0]]=1.;target[i,pair[1]]=-1.
    # Orthonormal basis for sum(theta)=0, constructed without a Laplacian.
    z=np.vstack([np.eye(n-1),-np.ones((1,n-1))]);q,_=np.linalg.qr(z,mode='reduced')
    design=b@q
    covariance=(1-rho)*np.eye(len(pairs))+(rho/2)*(b@b.T)
    inverse_noise=np.linalg.pinv(covariance,rcond=1e-12,hermitian=True)
    fisher=design.T@inverse_noise@design
    estimate_covariance=q@np.linalg.inv(fisher)@q.T
    return np.diag(target@estimate_covariance@target.T)

def verify(value):
    if value.get('classification')!='SYNTHETIC_SHARED_RECORD_GAUSSIAN_VARIANCE_NOT_MODEL_EFFECT':raise ValueError('scope')
    if (value.get('true_execution_noise_estimated') is not False or value.get('binary_preference_or_neural_model_theorem') is not False
        or value.get('real_corpus_reads')!=0):raise ValueError('unsupported_claim')
    if value.get('noise_model')!='edge_covariance=(1-rho)*I+(rho/2)*B*B.T' or value.get('marginal_edge_variance')!=1:raise ValueError('noise_model')
    expected=[(name,rho) for name in ('path','star') for rho in (0,.25,.5,.75,1)]
    rows=value.get('rows',[])
    if [(r.get('synthetic_case'),r.get('rho')) for r in rows]!=expected:raise ValueError('fixed_matrix')
    n=6;full=[(a,b) for a in range(n) for b in range(a+1,n)];max_error=0.;reductions={}
    for r in rows:
        tree=[(i,i+1) for i in range(n-1)] if r['synthetic_case']=='path' else [(0,i) for i in range(1,n)]
        if (r['nodes'],r['tree_edges'],r['full_edges'],r['target_contrasts'])!=(6,5,15,5):raise ValueError('graph_counts')
        for name,pairs in [('tree',tree),('full',full)]:
            actual=np.asarray(r[name+'_variances']);wanted=direct_gls(n,pairs,tree,r['rho'])
            if actual.shape!=(5,) or not np.isfinite(actual).all():raise ValueError('variance_schema')
            error=float(np.max(np.abs(actual-wanted)));max_error=max(max_error,error)
            mean=r[name+'_mean']
            if type(mean) not in (int,float) or not math.isfinite(mean) or abs(mean-float(wanted.mean()))>1e-9 or error>1e-9:raise ValueError('gls_disagrees')
        reduction=1-r['full_mean']/r['tree_mean']
        if not math.isfinite(r['relative_cycle_reduction']) or abs(r['relative_cycle_reduction']-reduction)>1e-9:raise ValueError('reduction')
        reductions.setdefault(r['synthetic_case'],[]).append(reduction)
    for values in reductions.values():
        if values[0]<=0 or abs(values[-1])>1e-9 or any(b>a+1e-9 for a,b in zip(values,values[1:])):raise ValueError('endpoint_or_monotonicity_control')
    return {'classification':'INDEPENDENT_SYNTHETIC_GLS_COUNTEREXAMPLE_VERIFIED_NOT_REAL_GAIN',
        'cases':2,'rho_points':5,'max_absolute_error':max_error,'fully_shared_record_cycle_gain_zero':True,
        'independent_edge_positive_control':True,'real_noise_level_estimated':False,'model_effect_measured':False}
