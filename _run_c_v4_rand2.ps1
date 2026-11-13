# _run_c_v4_rand2.ps1 -- decisive artefact test: core7 + 2 RANDOM flags (same per-view counts).
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v4_rand2.log'
$wait = Join-Path $env:TEMP 'c_v4_featloc.done'
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(6)
Log 'waiting for c_v4_featloc.done'
while (-not (Test-Path $wait)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout'; exit 1 }
  Start-Sleep -Seconds 60
}
while ((Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count -gt 0) {
  Start-Sleep -Seconds 20
}
$argv = @(
  '-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
  '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'),
  '--fold-mode','fold','--steps-per-epoch','1','--val-every','5',
  '--view-policy','all','--amp','--resume','--epochs','100',
  '--train-mode','4','--label-mask','trust','--save-ckpt',
  '--extra-feats','satrel_node','--seed','42',
  '--extra-node-file','satrel_node_feats_sat_p0clean4_core_rand2.npy',
  '--tag','fghtl_CncleanV4rand2D42',
  '--dump-scores', (Join-Path $root '_devcfg/gnn_v4rand2D_s42.npz')
)
Log '--- fghtl_CncleanV4rand2D42 (core7 + 2 random flags)'
$t0 = Get-Date
& $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP 'rand2D42.out') -Encoding UTF8
Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
'C_V4_RAND2_DONE ' + (Get-Date -Format s) | Out-File -FilePath (Join-Path $env:TEMP 'c_v4_rand2.done') -Encoding UTF8
Log '=== rand2 done ==='
