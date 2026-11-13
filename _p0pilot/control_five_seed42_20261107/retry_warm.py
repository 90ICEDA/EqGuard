"""Warm tiny CUDA reduction kernels before full-graph memory use;no optimizer."""
from pathlib import Path
import json,time,traceback
import run as task
O=Path(__file__).resolve().parent
try:
 torch=task.torch
 p=torch.nn.Parameter(torch.ones(32,device='cuda'));p.grad=torch.ones_like(p)
 assert torch.isfinite(p.grad).all()
 norm=torch.nn.utils.clip_grad_norm_([p],1.)
 assert torch.isfinite(norm);torch.cuda.synchronize();del p,norm;torch.cuda.empty_cache()
 (O/'RETRY_WARMUP.json').write_text(json.dumps(dict(reason='first attempt failed before first optimizer commit at CUDA reduction compilation/allocation;cause not yet proven',dummy_gradient_reduction_only=True,model_updates=0,optimizer_objects=0,original_runner_unchanged=True)),encoding='utf-8')
 print('TINY_REDUCTION_WARMUP_PASSED',flush=True)
 task.main()
except Exception:
 (O/f'retry_failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
