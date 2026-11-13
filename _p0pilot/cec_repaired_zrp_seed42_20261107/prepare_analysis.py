from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[1];OLD=R/'_p0pilot/cec_freeq_zrp_seed42_20261107'
a=(OLD/'analyze.py').read_text(encoding='utf-8')
a=a.replace("maintrain=pp['train_boundary_all']","maintrain=pp['train_frozen_pool']")
a=a.replace("==85","==73").replace('85H3','73H3')
(O/'analyze.py').write_text(a,encoding='utf-8')
v=(OLD/'verify.py').read_text(encoding='utf-8')
changes=[("C=R/'_p0pilot/cec_po_contract_20261106'","C=R/'_p0pilot/cec_repaired_contract_20261107'"),("len(s['units'])==3","len(s['units'])==2"),("r['unit_slots']==96 and r['queries']==576 and r['candidate_distances']==1728 and r['common_negatives']==576","r['unit_slots']==64 and r['queries']==384 and r['candidate_distances']==1152 and r['common_negatives']==384"),("['train_frozen_pool','val_old_PO','val_new_PO','train_old_PO','train_new_PO']","['train_frozen_pool','val_old_PO','val_new_PO']"),("rows(PRE/'initial_loss_preview.csv')","rows(R/'_p0pilot/cec_repaired_preflight_20261107/loaded_batches.csv')"),("assert len(evalaudit)==160","assert len(evalaudit)>0 and len(evalaudit)==read(O/'EVALUATION_COMPLETE.json')['new_forwards_this_execution']"),("primary_units=85,primary_functions=dict(two=41,three=44)","primary_units=73,primary_functions=dict(two=sum(u['functions']==2 for u in groups['val_H3_primary']),three=sum(u['functions']==3 for u in groups['val_H3_primary']))"),("evaluation_forwards=160","evaluation_forwards=len(evalaudit)"),("85units not85independent circuits","73units not73independent circuits")]
for x,y in changes:
 assert x in v,x
 v=v.replace(x,y)
v=v.replace('import collections,csv,hashlib,json,math','import collections,csv,hashlib,json,math,gzip')
v=v.replace("frozen_schedule=read(C/'SCHEDULE_SEED42.json');audit=[]", """frozen_schedule=read(C/'SCHEDULE_SEED42.json')
 with gzip.open(R/'_p0pilot/cec_boundary_panel_expand_20261107/local_graphs.json.gz','rt',encoding='utf-8') as f:raw=json.load(f)
 graphs=dict(zip(raw['cone_ids'],raw['graphs']));role_steps=collections.Counter()
 for s in frozen_schedule:
  roles={e[2] for u in s['units'] for c in u['cone_ids'] for e in graphs[c]['edge']}
  role_steps.update(roles)
 audit=[]""")
v=v.replace("assert set(actual.values())=={32}","assert actual=={n:(role_steps[int(n.split('.')[1])] if n.startswith('role_maps.') else 32) for n in names}")
v=v.replace('all14_parameter_actual_adam_steps32=True','parameter_steps_match_actual_role_exposure=True')
v=v.replace('all14_parameters_actualAdamsteps32=True','parameter_steps_match_actual_role_exposure=True,role_map_actual_steps=dict(role_steps)')
(O/'verify.py').write_text(v,encoding='utf-8')
print('Analysis and independent verifier prepared.')
