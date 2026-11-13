from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
orig=R/'generate_trans/folds/hosts_bt31/orig/s15850t100__injzeta_d1_s42.v'
trans=R/'generate_trans/folds/hosts_bt31/trans/s15850t100__injzeta_d1_s42__ys_id.v'
out=R/'tmp_sat_alias'
out.mkdir(exist_ok=True)
for src,name in [(orig,'orig_alias.v'),(trans,'trans_alias.v')]:
 s=src.read_text(encoding='utf-8',errors='replace')
 i=s.rfind('endmodule')
 s=s[:i]+'wire ZZSAT_ALIAS;\nassign ZZSAT_ALIAS = g4193;\n'+s[i:]
 (out/name).write_text(s,encoding='utf-8')
print('ok')
