# Matched 42-dimensional control: two zero columns plus the identical covered flag.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location -LiteralPath $root
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$deadline = (Get-Date).AddMinutes(45)
while (@(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'train_test2[.]3[.]py' }).Count -gt 0) {
    if ((Get-Date) -gt $deadline) { throw 'GPU training queue wait exceeded 45 minutes' }
    Start-Sleep -Seconds 5
}
$start = Get-Date
Write-Output ('START ' + $start.ToString('o'))
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
& $gpy -X utf8 -u train_test2.3.py `
  --work-dir generate_trans/folds/hosts_bt31 `
  --fold-json generate_trans/folds/hosts_bt31/views.json `
  --pt-dir generate_trans/folds/hosts_bt31/data/processed `
  --config _devcfg/dual.yaml --fold-mode fold --steps-per-epoch 1 --val-every 5 `
  --view-policy all --amp --resume --epochs 100 --train-mode 4 --label-mask trust `
  --save-ckpt --extra-feats satrel_node `
  --extra-node-file satrel_node_feats_audit_covered_matched3_20261025.npy `
  --seed 42 --tag fghtl_AuditCovered3D42_20261025 `
  --dump-scores _devcfg/gnn_audit_covered3_s42_20261025.npz
if ($LASTEXITCODE -ne 0) { throw "Training failed: $LASTEXITCODE" }
Write-Output ('END ' + (Get-Date).ToString('o') + ' elapsed_s=' + ((Get-Date) - $start).TotalSeconds)
