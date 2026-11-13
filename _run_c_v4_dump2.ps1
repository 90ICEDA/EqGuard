# _run_c_v4_dump2.ps1 -- core7 baseline + safe seeds 1/2, all with --dump-scores.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v4_dump2.log'
$wait = Join-Path $env:TEMP 'c_v4_dump.done'
$done = Join-Path $env:TEMP 'c_v4_dump2.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(4)
Log 'waiting for c_v4_dump.done'
while (-not (Test-Path $wait)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout'; exit 1 }
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
  '--extra-feats','satrel_node'
)
function Run-One([string]$tag, [string]$file, [string]$seed, [string]$dump) {
  $target = Join-Path $root $dump
  if (Test-Path $target) { Log ("[skip] {0} (npz exists)" -f $tag); return }
  Log ("--- {0} seed={1} ({2})" -f $tag, $seed, $file)
  $argv = $common.Clone()
  $argv += @('--extra-node-file', $file, '--seed', $seed, '--tag', $tag, '--dump-scores', $target)
  $t0 = Get-Date
  & $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("cv4d2_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}
Log '=== pooled-metric queue: core -> verdict -> shuffle6 -> safe seeds 1/2 ==='
Run-One 'fghtl_CncleanV4coreD42'    'satrel_node_feats_sat_p0clean4_core_only.npy'     '42' '_devcfg/gnn_v4coreD_s42.npz'
Run-One 'fghtl_CncleanV4verdictD42' 'satrel_node_feats_sat_p0clean4_verdict_only.npy'  '42' '_devcfg/gnn_v4verdictD_s42.npz'
Run-One 'fghtl_CncleanV4shuf6D42'   'satrel_node_feats_sat_p0clean4_shuffle6.npy'      '42' '_devcfg/gnn_v4shuf6D_s42.npz'
Run-One 'fghtl_CncleanV4safeD1'     'satrel_node_feats_sat_p0clean4_safe.npy'          '1'  '_devcfg/gnn_v4safeD_s1.npz'
Run-One 'fghtl_CncleanV4safeD2'     'satrel_node_feats_sat_p0clean4_safe.npy'          '2'  '_devcfg/gnn_v4safeD_s2.npz'
'C_V4_DUMP2_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== dump2 done ==='
