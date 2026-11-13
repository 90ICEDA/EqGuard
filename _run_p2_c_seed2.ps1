# _run_p2_c_seed2.ps1 -- after 56-dim LRO, run P2 C_n (51-dim) seed2 on fold protocol.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\p2_c2.log'
$wait = Join-Path $env:TEMP 'p3_56.done'
$done = Join-Path $env:TEMP 'p2_c2.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(5)
Log 'waiting for p3_56.done'
while (-not (Test-Path $wait)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout waiting p3_56.done'; exit 1 }
  Start-Sleep -Seconds 60
}
while ((Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count -gt 0) {
  Start-Sleep -Seconds 20
}
Log '--- fghtl_CncleanV2R2 (51-dim C_n, fold, seed2)'
$common = @(
  '-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
  '--work-dir', $fold,
  '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'),
  '--fold-mode','fold','--steps-per-epoch','1','--val-every','5',
  '--view-policy','all','--amp','--resume','--epochs','100',
  '--train-mode','4','--label-mask','trust','--save-ckpt',
  '--seed','2','--extra-feats','satrel_node',
  '--extra-node-file','satrel_node_feats_sat_p0clean2.npy'
)
$t0 = Get-Date
& $gpy @common --tag 'fghtl_CncleanV2R2' 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'clean2_fghtl_CncleanV2R2.out') -Encoding UTF8
Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
'P2_C2_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== P2 C seed2 done ==='
