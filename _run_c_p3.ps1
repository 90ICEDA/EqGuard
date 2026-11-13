# _run_c_p3.ps1 -- after D variants: C-only P3 (LRO/LOCO/LIO), no SAT.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log = Join-Path $root 'logs\c_p3.log'
$flag = Join-Path $env:TEMP 'c_p3.done'
$prev = Join-Path $env:TEMP 'd_variants.done'
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
$deadline = (Get-Date).AddHours(3)
while (-not (Test-Path $prev)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout waiting d_variants.done'; exit 1 }
  Start-Sleep -Seconds 30
}
Wait-NoTrain

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--steps-per-epoch', '1', '--val-every', '10',
            '--view-policy', 'all', '--amp', '--resume', '--epochs', '100',
            '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt',
            '--circuits', 's38584t100', '--seed', '42',
            '--extra-feats', 'satrel_node',
            '--extra-node-file', 'satrel_node_feats_sat_p0clean2.npy')

function Run-Gpu([string]$tag, [string[]]$argv) {
  Wait-NoTrain
  Log ("--- {0}" -f $tag)
  $t0 = Get-Date
  & $gpy @argv --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("cp3_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}

Log '=== C-only P3: lro, loco, lio ==='
foreach ($fd in @('lro','loco','lio')) {
  Run-Gpu ("fghtl_P3{0}Cv2s42" -f $fd) ($common + @('--fold-mode', $fd))
}
'C_P3_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== C P3 done ==='
