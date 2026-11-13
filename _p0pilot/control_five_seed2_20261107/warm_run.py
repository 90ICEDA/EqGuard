from pathlib import Path
import json,time,traceback
import run as task
O=Path(__file__).resolve().parent
try:
 torch=task.torch;p=torch.nn.Parameter(torch.ones(32,device='cuda'));p.grad=torch.ones_like(p)
 norm=torch.nn.utils.clip_grad_norm_([p],1.);assert torch.isfinite(norm);torch.cuda.synchronize();del p,norm;torch.cuda.empty_cache()
 (O/'CUDA_WARMUP.json').write_text(json.dumps(dict(dummy_reduction_only=True,model_updates=0,optimizer_objects=0)),encoding='utf-8')
 print('TINY_REDUCTION_WARMUP_PASSED',flush=True);task.main()
except Exception:
 (O/f'failure_wrapper_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
