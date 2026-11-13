from pathlib import Path

p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\seed42_nc_ablation_20261109\eval_offline.py')
s = p.read_text(encoding='utf-8')
s = s.replace("def views_of(split):\n    return {v['view']: v for v in BOUND['shared_inputs'][f'trans_{split}']['views']}",
              "def views_of(split, domain='trans'):\n    return {v['view']: v for v in BOUND['shared_inputs'][f'{domain}_{split}']['views']}")
s = s.replace("            v = views_of(split)", "            v = views_of(split, dm)")
s = s.replace("            m['roles'] = role_recall(mg, y, tr, split)",
              "            m['roles'] = role_recall(mg, y, tr, split) if dm == 'trans' else {}")
s = s.replace("                val=normal_view_fpr(mv, yv, tv, views_of('val'), thr95),",
              "                val=normal_view_fpr(mv, yv, tv, views_of('val', dm), thr95),")
s = s.replace("                test=normal_view_fpr(mt, yt, tt, views_of('test'), thr95))",
              "                test=normal_view_fpr(mt, yt, tt, views_of('test', dm), thr95))")
p.write_text(s, encoding='utf-8')
print('patched')
