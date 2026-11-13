# _run_cd_v2.ps1 -- priority: C/D with v2 features, seeds 42 and 1.
# E is intentionally not started.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $root 'logs\cd_v2.log'
$flag = Join-Path $env:TEMP 'cd_v2.done'
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
            '--extra-node-file', 'satrel_node_feats_sat_p0clean2.npy')

function Run-Gpu([string]$tag, [string[]]$argv) {
  Wait-NoTrain
  Log ("--- {0}" -f $tag)
  $t0 = Get-Date
  & $gpy @argv --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("cdv2_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}

Log '=== CD v2 priority: C42, C1, D42, D1 ==='
foreach ($seed in 42,1) {
  Run-Gpu ("fghtl_CncleanV2R{0}" -f $seed) ($common + @('--seed',"$seed"))
  Run-Gpu ("fghtl_DncleanV2R{0}" -f $seed) ($common + @(
    '--seed',"$seed", '--eq-loss-node','0.1',
    '--node-pair-cap','2048',
    '--node-pairs-file','satrel_node_pairs_labelclean.npz'))
}
'CD_V2_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== CD v2 done ==='
