import unittest
from pathlib import Path

import numpy as np

from importance import conditional_mapping, GROUPS


class ConditionalImportanceTests(unittest.TestCase):
    def toy(self):
        x=np.zeros((6,19),np.float32);x[:,0]=1.;x[:,18]=1.
        x[:,2]=[.5,1,.5,1,.5,1];x[:,3]=x[:,2]
        rows={i:dict(split='val' if i<4 else 'test',target_role='logic',driver_type='AND',k=4) for i in range(6)}
        return x,rows

    def test_correlated_column_not_falsely_independent(self):
        x,r=self.toy();new,m,c=conditional_mapping(x,r,np.arange(4),[2],11)
        self.assertFalse(c.any());self.assertTrue(np.array_equal(x,new))

    def test_joint_columns_are_actual_peer_vectors(self):
        x,r=self.toy();new,m,c=conditional_mapping(x,r,np.arange(4),[2,3],11)
        self.assertTrue(np.array_equal(new,x[m]));self.assertTrue(np.array_equal(new[:,2],new[:,3]))
        self.assertTrue(np.array_equal(new[4:],x[4:]))
        self.assertTrue(all(r[int(dst)]['split']==r[int(src)]['split'] for dst,src in enumerate(m)))

    def test_constant_field_is_not_identifiable(self):
        x,r=self.toy();new,m,c=conditional_mapping(x,r,np.arange(4),[7],23)
        self.assertFalse(c.any())

    def test_gate_role_and_k_are_preserved(self):
        x,r=self.toy();r[0]['driver_type']='OR';r[1]['target_role']='DFF';r[2]['k']=3
        new,m,c=conditional_mapping(x,r,np.arange(4),list(range(1,18)),53)
        self.assertFalse(c.any())

    def test_reproducible_and_original_not_mutated(self):
        x,r=self.toy();copy=x.copy()
        a,ma,ca=conditional_mapping(x,r,np.arange(4),[2,3],37)
        b,mb,cb=conditional_mapping(x,r,np.arange(4),[2,3],37)
        self.assertTrue(np.array_equal(ma,mb));self.assertTrue(np.array_equal(a,b));self.assertTrue(np.array_equal(copy,x))


if __name__=='__main__':unittest.main()
