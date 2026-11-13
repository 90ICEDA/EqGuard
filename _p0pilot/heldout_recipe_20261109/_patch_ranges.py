from pathlib import Path

p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\heldout_recipe_20261109\run_folds.py')
s = p.read_text(encoding='utf-8')
s = s.replace("        lo, hi = lay['old_start'], lay['old_stop']",
              "        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])")
s = s.replace("        if any(r in allowed_old for r in range(lay['old_start'], lay['old_stop'])):",
              "        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])\n"
              "        if any(r in allowed_old for r in range(lo, hi)):")
p.write_text(s, encoding='utf-8')
print('patched', "lay['start']" in s)
