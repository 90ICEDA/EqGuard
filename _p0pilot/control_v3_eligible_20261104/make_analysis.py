"""Reuse frozen offline diagnostics without changing original evidence files."""
from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
source=(R/'_p0pilot/control_fair200_20261104/analyze_results.py').read_text(encoding='utf-8')
old="for p,h in m['inputs'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p"
new="for p,h in read(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json')['files'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p"
assert source.count(old)==1;source=source.replace(old,new)
(O/'analyze_results.py').write_text(source,encoding='utf-8')
fine=(R/'_p0pilot/control_roles_20261104/analyze.py').read_text(encoding='utf-8');old="B=R/'_p0pilot/control_fair200_20261104'";assert fine.count(old)==1;fine=fine.replace(old,"B=R/'_p0pilot/control_v3_eligible_20261104'")
assert fine.count("B/'COMPLETE.json'")==2;fine=fine.replace("B/'COMPLETE.json'","B/'TRAINING_COMPLETE.json'")
(O/'analyze_roles.py').write_text(fine,encoding='utf-8')
plan=dict(time=datetime.datetime.now().astimezone().isoformat(),primary_operation='val_recall80',threshold_source='validation trusted positives only; no test tuning',secondary=['historical_fpr5','val_recall90'],normal_metric='full primary normal regions, equal source aggregation; all frozen sources retained',recall_metric='unchanged trusted Trojan view macro recall; report each seed and mean',engineering_interpretation=dict(recall_mean_drop_tolerance_pp=1,flag_individual_seed_drop_over_pp=2,not_statistical_noninferiority=True),unchanged_AP_and_role_breakdown=True,not_claiming_independent_test=True,code_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [O/'analyze_results.py',O/'analyze_roles.py']})
(O/'EVALUATION_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
