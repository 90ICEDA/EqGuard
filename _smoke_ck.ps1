# _smoke_ck.ps1 -- A/B: 2-epoch C_n with GNN_GRAD_CKPT=1 (numerically equivalent, less VRAM)
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--steps-per-epoch', '1', '--val-every', '5',
            '--view-policy', 'all', '--amp', '--resume',
            '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt')
& $gpy @common --fold-mode fold --epochs 2 --seed 42 --tag gpu_probeCK `
    --extra-feats satrel_node 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'smoke_CK.out') -Encoding UTF8
$rc = $LASTEXITCODE
"CK rc=$rc" | Tee-Object -FilePath (Join-Path $env:TEMP 'smoke_CK.out') -Append
