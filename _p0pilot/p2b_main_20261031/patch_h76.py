from pathlib import Path

q = Path(r'_p0pilot/p2b_main_20261031/ablate_dual.py')
t = q.read_text(encoding='utf-8')
if "'single4_h76'" not in t:
    t = t.replace("    if variant == 'single4':\n        return GINNodeClassifier(DIM, 64, 2, 4).cuda()",
                  "    if variant == 'single4':\n        return GINNodeClassifier(DIM, 64, 2, 4).cuda()\n    if variant == 'single4_h76':\n        return GINNodeClassifier(DIM, 76, 2, 4).cuda()")
    t = t.replace("'single2': None,", "'single2': None, 'single4_h76': None,")
q.write_text(t, encoding='utf-8')
print('h76:', 'single4_h76' in t)
