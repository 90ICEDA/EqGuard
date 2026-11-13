# _run_d_variants.ps1 -- after cd_v2: D_Pos and D_Weighted, one seed each.
# D_Pos:      positive-positive only
# D_Weighted: positive x4, negative x0.25
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $root 'logs\d_variants.log'
$flag = Join-Path $env:TEMP 'd_variants.done'
$cdflag = Join-Path $env:TEMP 'cd_v2.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) {
  $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
function Wait-NoTrain {
  while ($true) {
    $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'train_test2.3' } |
             Measure-Object).Count -gt 0
    if (-not $busy) { return }
    Start-Sleep -Seconds 20
  }
}
$deadline = (Get-Date).AddHours(2)
while (-not (Test-Path $cdflag)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout waiting cd_v2.done'; exit 1 }
  Start-Sleep -Seconds 30
}
Wait-NoTrain

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--fold-mode', 'fold', '--steps-per-epoch', '1', '--val-every', '10',
            '--view-policy', 'all', '--amp', '--resume', '--epochs', '100',
            '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt',
            '--extra-feats', 'satrel_node',
            '--extra-node-file', 'satrel_node_feats_sat_p0clean2.npy',
            '--seed', '42', '--eq-loss-node', '0.1',
            '--node-pair-cap', '2048',
            '--node-pairs-file', 'satrel_node_pairs_labelclean.npz')

function Run-Gpu([string]$tag, [string[]]$argv) {
  Wait-NoTrain
  Log ("--- {0}" -f $tag)
  $t0 = Get-Date
  & $gpy @argv --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("dv_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}

Log '=== D variants: D_Pos, D_Weighted (seed42) ==='
Run-Gpu 'fghtl_DncleanV2Pos42' ($common + @('--eq-pos-scale','1.0','--eq-neg-scale','0.0'))
Run-Gpu 'fghtl_DncleanV2W42'   ($common + @('--eq-pos-scale','4.0','--eq-neg-scale','0.25'))

'D_VARIANTS_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== D variants done ==='
