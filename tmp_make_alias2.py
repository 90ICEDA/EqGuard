from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); F=R/'generate_trans/folds/hosts_bt31'; O=R/'tmp_sat_s35932'; O.mkdir(exist_ok=True)
for src,name,net in [(F/'orig/s35932t200__injzeta_d1_s42.v','orig_alias.v','DATA_9_29'),(F/'trans/s35932t200__injzeta_d1_s42__ys_id.v','trans_alias.v','n__TrojanFP1_IN2__g2129')]:
 s=src.read_text(encoding='utf-8',errors='replace'); i=s.rfind('endmodule'); s=s[:i]+f'wire ZZSAT_ALIAS;\nassign ZZSAT_ALIAS = {net};\n'+s[i:]; (O/name).write_text(s,encoding='utf-8')
print('ok')
