"""Read the first tensor descriptors only and mmap their ZIP_STORED payloads.
Avoids unpickling the 215MB graph metadata and never imports torch.
"""
import pickle,collections,struct,zipfile
import numpy as np
class HeaderDone(Exception):pass
class Placeholder:pass
def arrays(path):
    tensors=[]
    def rebuild(storage,offset,shape,stride,*args):
        tensors.append(dict(storage=storage,offset=offset,shape=shape,stride=stride))
        if len(tensors)==3:raise HeaderDone()
        return tensors[-1]
    class Header(pickle.Unpickler):
        def find_class(self,module,name):
            if module=='torch._utils' and name=='_rebuild_tensor_v2':return rebuild
            if module=='torch' and name in ['FloatStorage','LongStorage']:return {'FloatStorage':'<f4','LongStorage':'<i8'}[name]
            if module=='collections' and name=='OrderedDict':return collections.OrderedDict
            if module.startswith('torch_geometric.'):return Placeholder
            raise ValueError((module,name))
        def persistent_load(self,pid):
            tag,dtype,key,device,size=pid;assert tag=='storage' and device=='cpu'
            return dict(dtype=dtype,key=key,size=size)
    z=zipfile.ZipFile(path)
    with z.open(next(s for s in z.namelist() if s.endswith('/data.pkl'))) as f:
        try:Header(f).load()
        except HeaderDone:pass
    assert len(tensors)==3
    results={}
    for name,t in zip(['x','edge_index','y'],tensors):
        s=t['storage'];item=next(i for i in z.infolist() if i.filename.endswith('/data/'+s['key']))
        assert item.compress_type==zipfile.ZIP_STORED and item.file_size==np.dtype(s['dtype']).itemsize*s['size']
        with open(path,'rb') as f:
            f.seek(item.header_offset);header=struct.unpack('<4s5H3I2H',f.read(30));assert header[0]==b'PK\x03\x04'
        offset=item.header_offset+30+header[-2]+header[-1]
        raw=np.memmap(path,mode='r',dtype=s['dtype'],offset=offset,shape=(s['size'],))
        results[name]=np.lib.stride_tricks.as_strided(raw[t['offset']:],shape=t['shape'],strides=tuple(v*raw.itemsize for v in t['stride']),writeable=False)
    return results,tensors
