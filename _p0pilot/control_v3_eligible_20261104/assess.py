"""Apply the recorded engineering interpretation to full, unchanged evaluation scopes."""
from pathlib import Path
import csv,json,collections
import numpy as np
O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def dump(n,a):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
def main():
 assert (O/'ANALYSIS_COMPLETE.json').exists();g=rows(O/'global_metrics.csv');r=rows(O/'region_summary.csv');ss=rows(O/'paired_source_deltas.csv');paired=[]
 for seed in [42,1,2]:
  for sp in ['val','test']:
   for op in ['historical_fpr5','val_recall80','val_recall90']:
    aa={x['arm']:x for x in g if int(x['seed'])==seed and x['split']==sp and x['operation']==op};bb={x['arm']:x for x in r if int(x['seed'])==seed and x['domain']=='trans' and x['split']==sp and x['operation']==op};out=dict(seed=seed,split=sp,operation=op)
    for k in ['ap','auc','r1','r5','recall','control_fpr']:
     h,c=float(aa['H'][k]),float(aa['C'][k]);out['H_'+k]=h;out['C_'+k]=c;out['delta_'+k]=c-h
    for k in ['source_mean_node_fpr','pair_correct_order','pair_joint_success','pair_trojan_recall']:
     h,c=float(bb['H'][k]),float(bb['C'][k]);out['H_'+k]=h;out['C_'+k]=c;out['delta_'+k]=c-h
    paired.append(out)
 dump('paired_seed_metrics.csv',paired)
 source=[]
 for sp in ['val','test']:
  for op in ['historical_fpr5','val_recall80','val_recall90']:
   for src in sorted({x['source'] for x in ss if x['domain']=='trans' and x['split']==sp}):
    aa=[x for x in ss if x['domain']=='trans' and x['split']==sp and x['source']==src and x['operation']==op];assert len(aa)==3
    source.append(dict(split=sp,operation=op,source=src,H_fpr=float(np.mean([float(x['H_fpr']) for x in aa])),C_fpr=float(np.mean([float(x['C_fpr']) for x in aa])),delta_fpr=float(np.mean([float(x['delta_fpr']) for x in aa])),seeds_improved=sum(float(x['delta_fpr'])<0 for x in aa),H_alarm_seed_count=sum(int(x['H_alarm']) for x in aa),C_alarm_seed_count=sum(int(x['C_alarm']) for x in aa)))
 dump('source_average_deltas.csv',source);primary=[x for x in paired if x['split']=='test' and x['operation']=='val_recall80'];plan=read(O/'EVALUATION_PLAN.json');margin=plan['engineering_interpretation']['recall_mean_drop_tolerance_pp']/100;individual=plan['engineering_interpretation']['flag_individual_seed_drop_over_pp']/100;fp=np.array([x['delta_source_mean_node_fpr'] for x in primary]);rec=np.array([x['delta_recall'] for x in primary]);ap=np.array([x['delta_ap'] for x in primary]);good=fp.mean()<0 and rec.mean()>=-margin;stable=good and (fp<0).sum()>=2 and not (rec<-individual).any()
 if stable:verdict='初步支持：平均正常区域误报下降，木马召回在预设工程容忍内，且未出现超过2个百分点的单种子召回下降；不是统计非劣效证明。'
 elif good:verdict='总体均值方向满足工程门槛，但逐种子存在不稳定或明显召回退化，不能认定稳定保持。'
 elif fp.mean()<0:verdict='正常区域误报平均下降，但木马召回损失超过预设1个百分点门槛，不能判为召回保持。'
 else:verdict='未观察到正常区域误报的平均下降，当前等权预算不能证明定向正常监督获得所需增益。'
 result=dict(primary_operation='val_recall80',mean_FPR_delta=float(fp.mean()),FPR_delta_sd=float(fp.std(ddof=1)),FPR_improved_seeds=int((fp<0).sum()),mean_recall_delta=float(rec.mean()),recall_delta_sd=float(rec.std(ddof=1)),recall_engineering_margin=margin,large_recall_drop_seeds=[x['seed'] for x in primary if x['delta_recall']<-individual],mean_AP_delta=float(ap.mean()),AP_delta_sd=float(ap.std(ddof=1)),mean_directions_pass=bool(good),engineering_stability_pass=bool(stable),verdict=verdict,not_statistical_noninferiority=True,SAT=0,original_evaluation_labels_unchanged=True)
 (O/'ASSESSMENT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(result)
if __name__=='__main__':main()
