# _run_gpu_final.ps1 -- final GPU queue (EXCLUSIVE): smoke -> view C/D/E x3 -> node C_n/D_n/E_n x3 -> C_nn, C_n_perm
#   waits for sat_phase3.done and for no SAT writer (SAT+GUP concurrency caused OOM/slowdown)
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\gpu_final.log'
$flag = Join-Path $env:TEMP 'gpu_final.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }
function Wait-NoSat {
  while ($true) {
    $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'sat_node_pairs_batch|sat_functional_relations|sat_sweep_pairs' } |
             Measure-Object).Count -gt 0
    if (-not $busy) { return }
    Log '    [wait] SAT writer still running -> sleep 60s (avoid GPU contention/OOM)'
    Start-Sleep -Seconds 60
  }
}

Log '=== GPU final: waiting for sat_phase3.done ==='
$dl = (Get-Date).AddHours(6)
while (-not (Test-Path (Join-Path $env:TEMP 'sat_phase3.done'))) {
  if ((Get-Date) -gt $dl) { Log 'wait timeout 6h -> start anyway'; break }
  Start-Sleep -Seconds 60
}
Wait-NoSat

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$base = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
          '--work-dir', $fold,
          '--fold-json', (Join-Path $fold 'views.json'),
          '--pt-dir', (Join-Path $fold 'data\processed'),
          '--config', (Join-Path $root '_devcfg\dual.yaml'),
          '--fold-mode', 'fold', '--steps-per-epoch', '1', '--val-every', '5',
          '--view-policy', 'all', '--amp', '--resume', '--epochs', '100',
          '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt')

function Run-Gpu([string]$tag, [string[]]$extra) {
  Wait-NoSat
  Log ("--- {0}" -f $tag)
  $t0 = Get-Date
  & $gpy @base @extra --tag $tag 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("gpu_{0}.out" -f $tag)) -Encoding UTF8
  $rc = $LASTEXITCODE
  $dt = [int]((Get-Date) - $t0).TotalMinutes
  Log ("    rc={0} elapsed={1}min" -f $rc, $dt)
}

# ---------- smoke (2 ep) : confirm exclusive-GPU speed & no OOM ----------
Log '=== smoke 2ep (exclusive) ==='
& $gpy @base --epochs 2 --seed 42 --tag gpu_probe3 --extra-feats satrel_node 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'gpu_probe3.out') -Encoding UTF8
Log ("    smoke rc={0}" -f $LASTEXITCODE)
$pr = Join-Path $root 'results\hosts_bt31_seed42mode4_allb1_fold_gpu_probe3\run_config.json'
if (Test-Path $pr) { Log ("    peak_vram_mb={0}" -f (Get-Content $pr -Raw | ConvertFrom-Json).peak_vram_mb) }

# ---------- view-level C/D/E x 3 seeds ----------
foreach ($seed in 42,1,2) {
  Run-Gpu ("fghtl_Cs{0}" -f $seed)  @('--seed',"$seed",'--extra-feats','satrel')
  Run-Gpu ("fghtl_Ds{0}" -f $seed)  @('--seed',"$seed",'--extra-feats','satrel','--eq-loss','0.5')
  Run-Gpu ("fghtl_Es{0}" -f $seed)  @('--seed',"$seed",'--extra-feats','satrel','--eq-loss','0.5','--pair-loss','0.5','--pair-margin','0.5')
}

# ---------- node-level C_n/D_n/E_n x 3 seeds ----------
foreach ($seed in 42,1,2) {
  Run-Gpu ("fghtl_Cns{0}" -f $seed) @('--seed',"$seed",'--extra-feats','satrel_node')
  Run-Gpu ("fghtl_Dns{0}" -f $seed) @('--seed',"$seed",'--extra-feats','satrel_node','--eq-loss-node','0.1')
  Run-Gpu ("fghtl_Ens{0}" -f $seed) @('--seed',"$seed",'--extra-feats','satrel_node','--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5')
}

# ---------- controls ----------
Run-Gpu 'fghtl_Cnns42'    @('--seed','42','--extra-feats','satrel_node','--no-cov-flag')
Run-Gpu 'fghtl_Cnperms42' @('--seed','42','--extra-feats','satrel_node','--extra-node-file','satrel_node_feats_sat_perm.npy')
Run-Gpu 'fghtl_Cndrivers42' @('--seed','42','--extra-feats','satrel_node','--extra-node-file','satrel_node_feats_sat_driver.npy')

Log '--- refresh fg_htl_ablation.csv ---'
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
'GPU_FINAL_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== GPU final done ==='
