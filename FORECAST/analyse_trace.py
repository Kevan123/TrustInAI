from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
from scipy.stats import wilcoxon,rankdata
ROOT=Path(__file__).resolve().parent
INPUT=Path('upload/Caribbean_TRACE_40_Pairs_scored.xlsx')
r=pd.read_excel(INPUT,sheet_name='Experiment runs');g=pd.read_excel(INPUT,sheet_name='Gold and review').set_index('Pair Id')
r=r[r['TRACE Scoring Status']=='scored'].copy()
r['truth']=[g.loc[x['Pair Id'],x['Stimulus Id'].rsplit('-',1)[-1]+' Truth Label'] for _,x in r.iterrows()]
r['empty']=r['Retrieved Passage'].fillna('').apply(lambda x:not json.loads(x) if x else True)
assert len(r)==216 and r['Run Id'].nunique()==216
assert all(r.groupby(['Pair Id','Retrieval Condition']).size()==2)
assert r['TRACE Model'].nunique()==1
rng=np.random.default_rng(20260930)
B=10000
rows=[]
def record(name,metric,d):
 d=np.asarray(d,float);means=d[rng.integers(0,len(d),(B,len(d)))].mean(1)
 lo,hi=np.quantile(means,[.025,.975]);p=wilcoxon(d,method='auto').pvalue if np.any(d) else 1.
 rows.append(dict(comparison=name,metric=metric,n=len(d),mean_difference=d.mean(),ci_low=lo,ci_high=hi,p=p))
for truth in ['supported','refuted']:
 for m in ['E Score','V Score','T Score']:
  p=r[r.truth==truth].pivot(index='Pair Id',columns='Retrieval Condition',values=m)
  record(truth+': regional minus ablation',m,p.regional_corpus-p.source_ablation)
for c in ['regional_corpus','source_ablation','oracle_passage']:
 for m in ['E Score','V Score','T Score']:
  p=r[r['Retrieval Condition']==c].pivot(index='Pair Id',columns='truth',values=m)
  record(c+': supported minus refuted',m,p.supported-p.refuted)
# Holm correction across these 15 exploratory paired comparisons.
pvals=np.array([x['p'] for x in rows]);order=np.argsort(pvals);adj=np.maximum.accumulate((len(rows)-np.arange(len(rows)))*pvals[order]);adj=np.minimum(adj,1)
for i,v in zip(order,adj):rows[i]['p_holm']=v
stats=pd.DataFrame(rows);stats.to_csv(ROOT/'paired_effects.csv',index=False)
r.to_csv(ROOT/'analysis_runs.csv',index=False)
summary=r.groupby(['Retrieval Condition','truth'])[['E Score','V Score','T Score']].mean().reset_index();summary.to_csv(ROOT/'condition_means.csv',index=False)
# AUROC: marginal discrimination, bootstrap whole true/false pairs.
aucrows=[]
def auc(a,b):return float(((a[:,None]>b[None,:])+.5*(a[:,None]==b[None,:])).mean())
for c in ['regional_corpus','source_ablation','oracle_passage']:
 for m in ['E Score','V Score','T Score']:
  p=r[r['Retrieval Condition']==c].pivot(index='Pair Id',columns='truth',values=m)
  a=p.supported.to_numpy();b=p.refuted.to_numpy();idx=rng.integers(0,len(a),(B,len(a)))
  boot=np.array([auc(a[i],b[i]) for i in idx]);lo,hi=np.quantile(boot,[.025,.975])
  aucrows.append(dict(condition=c,metric=m,auc=auc(a,b),ci_low=lo,ci_high=hi))
pd.DataFrame(aucrows).to_csv(ROOT/'discrimination.csv',index=False)
print(stats.to_string(index=False));print(pd.DataFrame(aucrows).to_string(index=False))
print('EMPTY',r.groupby(['Retrieval Condition','truth']).empty.sum())
print('EMPTY SCORES',r[r['empty']].groupby('truth')[['E Score','V Score','T Score']].agg(['mean','min','max']))
print('V max discrepancy',abs(r['V Score']-np.round(.5*r['E Score']+np.where(r['E Score']<.15,.2,.5),4)).max())
print('E RANGE',r['E Score'].min(),r['E Score'].max())
print('ALL L',r['L Score'].describe().to_dict())
(ROOT/'analysis_metadata.json').write_text(json.dumps({'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),'seed':20260930,'bootstrap_samples':B,'resampling_unit':'claim pair','model':r['TRACE Model'].iloc[0],'scored_runs':len(r),'note':'One model execution per input; confidence intervals do not quantify evaluator rerun variability.'},indent=2))
