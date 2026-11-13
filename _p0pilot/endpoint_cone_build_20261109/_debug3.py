import sys
sys.path.insert(0, r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\endpoint_cone_build_20261109')
import cone_builder as B
p = r'C:\Users\91344\Desktop\GraphSAINT\GIN_train\_p0pilot\endpoint_cone_build_20261109\tests\alias_vector.v'
text = open(p, encoding='utf-8').read()
print('declared', B.declared_ports(text))
b = B.build(p)
print('pi', b['pi'], 'po', b['po'])
for c in b['cones']:
    print(c['cone_id'], c['flag'], [m['cell'] for m in c['members']], c['unknown'], c['boundary'])
