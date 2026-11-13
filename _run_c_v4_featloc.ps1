# _run_c_v4_featloc.ps1 -- feature localisation: which SAT columns actually matter.
# Order: verdict_proved -> verdict_partial -> core_p0rel -> core_reach -> core_p1 -> covered_only
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v4_featloc.log'
$wait = Join-Path $env:TEMP 'c_v4_randsupport.done'
$done = Join-Path $env:TEMP 'c_v4_featloc.done'
if (Test-Path $done) { Remove-Item $done -Force }
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(5)
Log 'waiting for c_v4_randsupport.done'
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
  $target = Join-Path $root $dump
  if (Test-Path $target) { Log ("[skip] {0} (npz exists)" -f $tag); return }
  Log ("--- {0} ({1})" -f $tag, $file)
  $argv = $common.Clone()
  $argv += @('--extra-node-file', $file, '--tag', $tag, '--dump-scores', $target)
  $t0 = Get-Date
  & $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("fl_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}
Log '=== feature localisation ==='
Run-One 'fghtl_CncleanV4smuxD42'     'satrel_node_feats_sat_p0clean4_safe_nomux.npy'     '_devcfg/gnn_v4smuxD_s42.npz'
Run-One 'fghtl_CncleanV4muxonlyD42'  'satrel_node_feats_sat_p0clean4_mux_only.npy'       '_devcfg/gnn_v4muxonlyD_s42.npz'
Run-One 'fghtl_CncleanV4vprovedD42'  'satrel_node_feats_sat_p0clean4_verdict_proved.npy'  '_devcfg/gnn_v4vprovedD_s42.npz'
Run-One 'fghtl_CncleanV4vpartialD42' 'satrel_node_feats_sat_p0clean4_verdict_partial.npy' '_devcfg/gnn_v4vpartialD_s42.npz'
Run-One 'fghtl_CncleanV4p0relD42'    'satrel_node_feats_sat_p0clean4_core_p0rel.npy'      '_devcfg/gnn_v4p0relD_s42.npz'
Run-One 'fghtl_CncleanV4reachD42'    'satrel_node_feats_sat_p0clean4_core_reach.npy'      '_devcfg/gnn_v4reachD_s42.npz'
Run-One 'fghtl_CncleanV4p1D42'       'satrel_node_feats_sat_p0clean4_core_p1.npy'         '_devcfg/gnn_v4p1D_s42.npz'
Run-One 'fghtl_CncleanV4covonlyD42'  'satrel_node_feats_sat_p0clean4_covered_only.npy'    '_devcfg/gnn_v4covonlyD_s42.npz'
'C_V4_FEATLOC_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== feature localisation done ==='
