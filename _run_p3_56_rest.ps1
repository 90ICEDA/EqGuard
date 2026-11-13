# _run_p3_56_rest.ps1 -- if first split >30 min, stop LRO and resume only ys_id + ys_opt.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$decision = Join-Path $env:TEMP 'p3_56_decision.txt'
$log = Join-Path $root 'logs\c_p3_56_rest.log'
$done = Join-Path $env:TEMP 'p3_56.done'
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
$deadline = (Get-Date).AddHours(2)
while (-not (Test-Path $decision)) {
  if ((Get-Date) -gt $deadline) { Log 'timeout waiting decision'; exit 1 }
  Start-Sleep -Seconds 30
}
$d = (Get-Content $decision -Raw).Trim()
Log ("decision=$d")
if ($d -notmatch 'SWITCH_3') { Log 'keep 5 splits -> exit'; exit 0 }

Log 'stopping current 56 LRO (ys_abc done; keep partial rows)'
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'train_test2.3' -and $_.CommandLine -match 'fghtl_P3lroC5S42' }
foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; Log "  stop python $($p.ProcessId)" }
Stop-Process -Id 64044 -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
while ((Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'train_test2.3' } | Measure-Object).Count -gt 0) {
  Start-Sleep -Seconds 10
}

Log 'resume 56 LRO on ys_id + ys_opt (ys_abc kept)'
$common = @(
  '-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
  '--work-dir', $fold,
  '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'),
  '--steps-per-epoch','1','--val-every','10','--view-policy','all',
  '--amp','--resume','--epochs','100',
  '--train-mode','4','--label-mask','trust','--save-ckpt',
  '--circuits','s38584t100','--seed','42',
  '--extra-feats','satrel_node',
  '--extra-node-file','cone5_sat_p0clean2.npy',
  '--extra-dense-prefix','5',
  '--fold-mode','lro','--lro-splits','ys_id,ys_opt',
  '--tag','fghtl_P3lroC5S42'
)
$t0 = Get-Date
& $gpy @common 2>&1 | Out-File -FilePath (Join-Path $env:TEMP 'cp3_56_rest.out') -Encoding UTF8
Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
'P3_56_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== 56 LRO 3-split done ==='
