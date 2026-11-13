# _smoke_newfeat.ps1 -- quick 2-epoch validation of the NEW node-pair loss path
#   E (fold) with L_eq+L_pair; then P3 LRO with L_eq+L_pair
#   writes only to %TEMP%\smoke_*.out; does NOT start the full queue
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
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

Write-Host '=== smoke E (fold, eq/pair node losses) ==='
& $gpy @common --fold-mode fold --epochs 2 --seed 42 --tag gpu_probeE_now `
    --extra-feats satrel_node --eq-loss-node 0.1 --pair-loss-node 0.1 --pair-margin 0.5 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'smoke_E_now.out') -Encoding UTF8
Write-Host ("E rc={0}" -f $LASTEXITCODE)

Write-Host '=== smoke P3 LRO (eq/pair node losses) ==='
& $gpy @common --fold-mode lro --circuits s38584t100 --epochs 2 --seed 42 --tag gpu_probeP3_now `
    --extra-feats satrel_node --eq-loss-node 0.1 --pair-loss-node 0.1 --pair-margin 0.5 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'smoke_P3_now.out') -Encoding UTF8
Write-Host ("P3 rc={0}" -f $LASTEXITCODE)
