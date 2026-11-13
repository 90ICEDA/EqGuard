# _run_c_v4_split.ps1 -- counts-only vs verdicts-only (which half of p0clean4 carries the gain).
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_v4_split.log'
$done = Join-Path $env:TEMP 'c_v4_split.done'
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
function Run-One([string]$tag, [string]$file) {
  Log ("--- {0} ({1})" -f $tag, $file)
  $argv = $common.Clone()
  $argv += @('--extra-node-file', $file, '--seed', '42', '--tag', $tag)
  $t0 = Get-Date
  & $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("cv4_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}
Log '=== C_n v4 split: verdict_only -> counts_only ==='
Run-One 'fghtl_CncleanV4verdictR42' 'satrel_node_feats_sat_p0clean4_verdict_only.npy'
Run-One 'fghtl_CncleanV4countsR42'  'satrel_node_feats_sat_p0clean4_counts_only.npy'
'C_V4_SPLIT_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== v4 split done ==='
