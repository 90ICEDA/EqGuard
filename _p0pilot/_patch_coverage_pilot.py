from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\cone_coverage_pilot.py')
s = p.read_text(encoding='utf-8')
s = s.replace("out=dict(selected_views=sel,current=summ('current_cache_subset',cur_neg,cur_pos,cur_nc,cur_pc),full=summ('all_endpoints',full_neg,full_pos,full_nc,full_pc))",
"out=dict(selected_views=sel,current=summ('current_cache_subset',cur_neg,cur_pos,cur_nc,cur_pc),full=summ('all_endpoints',full_neg,full_pos,full_nc,full_pc))\ncur_any=set().union(*[m for _,_,m in cur]) if cur else set(); full_any=set().union(*[m for _,_,m in full]) if full else set()\nout['current']['neg_any_cov']=round(len(cur_any & neg_total)/len(neg_total),4)\nout['full']['neg_any_cov']=round(len(full_any & neg_total)/len(neg_total),4)\ncur_pos_hit=set().union(*[m for l,_,m in cur if l==1]) & pos_total if cur else set(); full_pos_hit=set().union(*[m for l,_,m in full if l==1]) & pos_total if full else set()\nout['current']['pos_hit']=len(cur_pos_hit); out['current']['pos_hit_cov']=round(len(cur_pos_hit)/len(pos_total),4)\nout['full']['pos_hit']=len(full_pos_hit); out['full']['pos_hit_cov']=round(len(full_pos_hit)/len(pos_total),4)")
p.write_text(s, encoding='utf-8')
print('patched')
