from pathlib import Path
p = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\train_coneonly_aig.py')
s = p.read_text(encoding='utf-8')
s = s.replace('from supervision_loader import FiveGroupLoader', 'from supervision_loader import FiveGroupLoader\nfrom sklearn.metrics import average_precision_score')
s = s.replace("            s=(m(x,e).float()[:,1]-m(x,e).float()[:,0]).cpu().numpy()", "            lg=m(x,e).float(); s=(lg[:,1]-lg[:,0]).cpu().numpy()")
s = s.replace("aps.append(__import__('sklearn.metrics').metrics.average_precision_score(yy[tt],ss[tt]))", "aps.append(average_precision_score(yy[tt],ss[tt]))")
p.write_text(s, encoding='utf-8')
print('patched')
