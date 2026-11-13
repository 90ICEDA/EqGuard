# _run_c_v4_shuffle6.ps1 -- after the 3-way ablation, run the position-prior control.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v4_shuffle6.log'
$wait = Join-Path $env:TEMP 'c_v4.done'
$done = Join-Path $env:TEMP 'c_v4_shuffle6.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(3)
Log 'waiting for c_v4.done'
while (-not (Test-Path $wait)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout waiting c_v4.done'; exit 1 }
  Start-Sleep -Seconds 60
}
while ((Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count -gt 0) {
  Start-Sleep -Seconds 20
}
$common = @(
  '-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
  '--work-dir', $fold,
  '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'),
  '--fold-mode','fold','--steps-per-epoch','1','--val-every','5',
  '--view-policy','all','--amp','--resume','--epochs','100',
  '--train-mode','4','--label-mask','trust','--save-ckpt',
  '--extra-feats','satrel_node',
  '--extra-node-file','satrel_node_feats_sat_p0clean4_shuffle6.npy',
  '--seed','42','--tag','fghtl_CncleanV4shuf6R42'
)
Log '--- fghtl_CncleanV4shuf6R42 (v3 evidence columns shuffled within view)'
$t0 = Get-Date
& $gpy @common 2>&1 | Out-File -FilePath (Join-Path $env:TEMP 'cv4_fghtl_CncleanV4shuf6R42.out') -Encoding UTF8
Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
'C_V4_SHUF6_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== shuffle6 control done ==='
