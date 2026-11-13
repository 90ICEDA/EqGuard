# _run_after_reboot.ps1 -- resume after reboot.
#   Step 1 (required): verdict_permD  -- semantics control (placement kept, verdict values permuted)
#   Step 2 (optional): safeD1 / safeD2 -- 3-seed CI for the main config
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File _run_after_reboot.ps1            # vperm + 2 seeds
#   powershell -NoProfile -ExecutionPolicy Bypass -File _run_after_reboot.ps1 -OnlyVperm # vperm only
param([switch]$OnlyVperm)

$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\after_reboot.log'
$done = Join-Path $env:TEMP 'after_reboot.done'
if (Test-Path $done) { Remove-Item $done -Force }

function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
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
  Log ("--- {0} seed={1} file={2}" -f $tag, $seed, $file)
  $argv = $common.Clone()
  $argv += @('--extra-node-file', $file, '--seed', $seed, '--tag', $tag, '--dump-scores', $target)
  $t0 = Get-Date
  & $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("reboot_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}

Log '=== after reboot: verdict_permD first ==='
Run-One 'fghtl_CncleanV4vpermD42' 'satrel_node_feats_sat_p0clean4_verdict_perm.npy' '42' '_devcfg/gnn_v4vpermD_s42.npz'

if (-not $OnlyVperm) {
  Log '=== then 3-seed CI for safe ==='
  Run-One 'fghtl_CncleanV4safeD1' 'satrel_node_feats_sat_p0clean4_safe.npy' '1' '_devcfg/gnn_v4safeD_s1.npz'
  Run-One 'fghtl_CncleanV4safeD2' 'satrel_node_feats_sat_p0clean4_safe.npy' '2' '_devcfg/gnn_v4safeD_s2.npz'
}

'AFTER_REBOOT_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== after-reboot queue done ==='
