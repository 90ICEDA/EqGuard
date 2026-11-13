from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); F=R/'generate_trans/folds/hosts_bt31'; O=R/'tmp_sat_last'; O.mkdir(exist_ok=True)
for src,name in [(F/'orig/s35932t200__injzeta_d1_s42.v','orig_alias.v'),(F/'trans/s35932t200__injzeta_d1_s42__ys_nand.v','trans_alias.v')]:
 s=src.read_text(encoding='utf-8',errors='replace'); i=s.rfind('endmodule'); s=s[:i]+'wire ZZSAT_ALIAS;\nassign ZZSAT_ALIAS = TrojanF_p5;\n'+s[i:]; (O/name).write_text(s,encoding='utf-8')
print('ok')
