from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\cone_coverage_pilot.py')
s = p.read_text(encoding='utf-8')
s = s.replace("out['full']['pos_hit']=len(full_pos_hit); out['full']['pos_hit_cov']=round(len(full_pos_hit)/len(pos_total),4)",
"out['full']['pos_hit']=len(full_pos_hit); out['full']['pos_hit_cov']=round(len(full_pos_hit)/len(pos_total),4)\nout['full']['total_cones']=len(full); out['full']['label_counts']={str(k):sum(1 for l,_,_ in full if l==k) for k in (-1,0,1)}\nout['current']['total_cones']=len(cur); out['current']['label_counts']={str(k):sum(1 for l,_,_ in cur if l==k) for k in (-1,0,1)}")
p.write_text(s, encoding='utf-8')
print('patched')
