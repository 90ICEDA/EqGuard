"""Same bounded information check, bound to the final supplemented corpus."""
from pathlib import Path
O=Path(__file__).resolve().parent
source=(O/'information_check.py').read_text(encoding='utf-8')
for old,new in {"'pairs.json'":"'final_pairs.json'","'cones.json'":"'final_cones.json'","'INFORMATION_CHECK.json'":"'INFORMATION_CHECK_FINAL.json'","'functional_information.csv'":"'functional_information_final.csv'","'large_nonconstant_witnesses.json'":"'large_nonconstant_witnesses_final.json'"}.items():
 assert old in source
 source=source.replace(old,new)
exec(compile(source,str(O/'information_check.py'),'exec'),{'__file__':str(__file__),'__name__':'__main__'})
