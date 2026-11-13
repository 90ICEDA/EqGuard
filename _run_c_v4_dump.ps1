# _run_c_v4_dump.ps1 -- re-run safe + counts WITH --dump-scores for pooled AP.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v4_dump.log'
$wait = Join-Path $env:TEMP 'c_v4_core.done'
$done = Join-Path $env:TEMP 'c_v4_dump.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(3)
Log 'waiting for c_v4_core.done'
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
  '--extra-feats','satrel_node','--seed','42'
)
function Run-One([string]$tag, [string]$file, [string]$dump) {
  Log ("--- {0} ({1}) dump={2}" -f $tag, $file, $dump)
  $argv = $common.Clone()
  $argv += @('--extra-node-file', $file, '--tag', $tag, '--dump-scores', (Join-Path $root $dump))
  $t0 = Get-Date
  & $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("cv4d_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}
Log '=== C_n v4 with score dumps: safe -> counts ==='
Run-One 'fghtl_CncleanV4safeD42'   'satrel_node_feats_sat_p0clean4_safe.npy'       '_devcfg/gnn_v4safeD_s42.npz'
Run-One 'fghtl_CncleanV4countsD42' 'satrel_node_feats_sat_p0clean4_counts_only.npy' '_devcfg/gnn_v4countsD_s42.npz'
'C_V4_DUMP_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== v4 dump runs done ==='
