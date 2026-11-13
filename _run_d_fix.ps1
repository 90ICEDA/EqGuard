# _run_d_fix.ps1 -- D with label-clean, positive-balanced consistency pairs.
# E is intentionally NOT run: label-conditioned kind1 has only 48 pairs.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $root 'logs\d_fix.log'
$flag = Join-Path $env:TEMP 'd_fix.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) {
  $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
while ($true) {
  $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'train_test2.3' } |
           Measure-Object).Count -gt 0
  if (-not $busy) { break }
  Start-Sleep -Seconds 20
}
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$argv = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
          '--work-dir', $fold,
          '--fold-json', (Join-Path $fold 'views.json'),
          '--pt-dir', (Join-Path $fold 'data\processed'),
          '--config', (Join-Path $root '_devcfg\dual.yaml'),
          '--fold-mode', 'fold', '--steps-per-epoch', '1', '--val-every', '10',
          '--view-policy', 'all', '--amp', '--resume', '--epochs', '100',
          '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt',
          '--extra-feats', 'satrel_node',
          '--extra-node-file', 'satrel_node_feats_sat_p0clean.npy',
          '--seed', '42', '--eq-loss-node', '0.1',
          '--node-pair-cap', '2048',
          '--node-pairs-file', 'satrel_node_pairs_labelclean.npz')
Log '=== D fix: label-clean positive-balanced consistency ==='
$t0 = Get-Date
& $gpy @argv --tag 'fghtl_DncleanLP42' 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'd_fix.out') -Encoding UTF8
Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
'D_FIX_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== D fix done ==='
