# _run_c_v4_randsupport.ps1 -- after vpermD: verdict support moved to random nodes (same size).
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v4_randsupport.log'
$wait = Join-Path $env:TEMP 'after_reboot.done'
$done = Join-Path $env:TEMP 'c_v4_randsupport.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(3)
Log 'waiting for after_reboot.done'
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
  '--work-dir', $fold,
  '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'),
  '--fold-mode','fold','--steps-per-epoch','1','--val-every','5',
  '--view-policy','all','--amp','--resume','--epochs','100',
  '--train-mode','4','--label-mask','trust','--save-ckpt',
  '--extra-feats','satrel_node',
  '--extra-node-file','satrel_node_feats_sat_p0clean4_verdict_randsupport.npy',
  '--seed','42','--tag','fghtl_CncleanV4rsupD42',
  '--dump-scores', (Join-Path $root '_devcfg/gnn_v4rsupD_s42.npz')
)
Log '--- fghtl_CncleanV4rsupD42 (verdict support moved to random nodes, same size)'
$t0 = Get-Date
& $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP 'reboot_rsupD42.out') -Encoding UTF8
Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
'C_V4_RSUP_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== randsupport done ==='
