"""Synthetic Gaussian contrast counterexample, not a neural-critic forecast."""
import math
import numpy as np

RHOS=(0.0,.25,.5,.75,1.0)

def incidence(n,edges):
    if type(n) is not int or n<2:raise ValueError('node_count')
    seen=set();out=np.zeros((len(edges),n),dtype=np.float64)
    for i,(a,b) in enumerate(edges):
        if type(a) is not int or type(b) is not int or not (0<=a<n and 0<=b<n and a!=b):raise ValueError('edge')
        key=tuple(sorted((a,b)))
        if key in seen:raise ValueError('duplicate_edge')
        seen.add(key);out[i,a]=1.;out[i,b]=-1.
    return out

def closed_form(n,edges,targets,rho):
    if type(rho) not in (int,float) or not math.isfinite(rho) or not 0<=rho<=1:raise ValueError('rho')
    b=incidence(n,edges);c=incidence(n,targets);lap=b.T@b
    vals,vecs=np.linalg.eigh(lap)
    if vals.min() < -1e-10 or sum(vals>1e-10)!=n-1:raise ValueError('connected_graph_required')
    positive=vals>1e-10;pinv=(vecs[:,positive]/vals[positive])@vecs[:,positive].T
    resistance=np.einsum('ij,jk,ik->i',c,pinv,c)
    return (1-rho)*resistance+(rho/2)*np.einsum('ij,ij->i',c,c)

def matrix():
    n=6;full=[(a,b) for a in range(n) for b in range(a+1,n)]
    cases={'path':[(i,i+1) for i in range(n-1)],'star':[(0,i) for i in range(1,n)]}
    rows=[]
    for name,tree in cases.items():
        for rho in RHOS:
            a=closed_form(n,tree,tree,rho);b=closed_form(n,full,tree,rho)
            rows.append({'synthetic_case':name,'rho':rho,'nodes':n,'tree_edges':len(tree),'full_edges':len(full),
                'target_contrasts':len(tree),'tree_variances':a.tolist(),'full_variances':b.tolist(),
                'tree_mean':float(a.mean()),'full_mean':float(b.mean()),
                'relative_cycle_reduction':float(1-b.mean()/a.mean())})
    return {'classification':'SYNTHETIC_SHARED_RECORD_GAUSSIAN_VARIANCE_NOT_MODEL_EFFECT',
        'noise_model':'edge_covariance=(1-rho)*I+(rho/2)*B*B.T','marginal_edge_variance':1,
        'true_execution_noise_estimated':False,'binary_preference_or_neural_model_theorem':False,
        'real_corpus_reads':0,'rows':rows}
