# _run_p2_all.ps1 -- P2 full sweep, SEQUENTIAL on the single 8GB GPU
#   Stage 1 (spec A-E, view-level):  C / D / E   x seed {42,1,2}
#   Stage 2 (node-level, SAT-first): Cn / Dn / En x seed {42,1,2}
#   100 ep, steps-per-epoch 1, val-every 5, view-policy all, amp, resume
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI -> CJK literals break)
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy  = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$d15  = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4   = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log  = Join-Path $n4.FullName 'logs\p2_all.log'
$flag = Join-Path $env:TEMP 'p2_all.done'
if (Test-Path $flag) { Remove-Item $flag -Force }

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}
function Wait-Ram {
  while (((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB) -lt 5) {
    Log '    [wait] free RAM < 5GB -> sleep 30s'; Start-Sleep -Seconds 30
  }
}

$fold   = Join-Path $root 'generate_trans\folds\hosts_bt31'
$base   = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--fold-mode', 'fold', '--epochs', '100', '--steps-per-epoch', '1',
            '--val-every', '5', '--view-policy', 'all', '--amp', '--resume',
            '--train-mode', '4', '--label-mask', 'trust')

Log '=== P2 ALL start (stage1 view-level C/D/E -> stage2 node-level Cn/Dn/En) ==='
# ---------- Stage 1: view-level (spec A-E) ----------
foreach ($seed in 42,1,2) {
  foreach ($grp in @(
      @{n='C'; extra=@('--extra-feats','satrel')},
      @{n='D'; extra=@('--extra-feats','satrel','--eq-loss','0.5')},
      @{n='E'; extra=@('--extra-feats','satrel','--eq-loss','0.5','--pair-loss','0.5','--pair-margin','0.5')})) {
    $tag = "fghtl_$($grp.n)s$seed"
    Wait-Ram
    Log ("--- [view] $($grp.n) seed=$seed tag=$tag")
    $ex = @('--seed',"$seed",'--tag',$tag) + $grp.extra
    & $gpy @base @ex 2>&1 | Out-File -FilePath (Join-Path $env:TEMP "$tag.out") -Encoding UTF8
    Log ("    [view] $($grp.n) seed=$seed rc=$LASTEXITCODE")
  }
}
# ---------- Stage 2: node-level (SAT-first) ----------
foreach ($seed in 42,1,2) {
  foreach ($grp in @(
      @{n='Cn'; extra=@('--extra-feats','satrel_node')},
      @{n='Dn'; extra=@('--extra-feats','satrel_node','--eq-loss-node','0.1')},
      @{n='En'; extra=@('--extra-feats','satrel_node','--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5')})) {
    $tag = "fghtl_$($grp.n)s$seed"
    Wait-Ram
    Log ("--- [node] $($grp.n) seed=$seed tag=$tag")
    $ex = @('--seed',"$seed",'--tag',$tag) + $grp.extra
    & $gpy @base @ex 2>&1 | Out-File -FilePath (Join-Path $env:TEMP "$tag.out") -Encoding UTF8
    Log ("    [node] $($grp.n) seed=$seed rc=$LASTEXITCODE")
  }
}

# ---------- Stage 3: sensitivity check (no covered flag; seed 42 only) ----------
Wait-Ram
Log '--- [node] Cnn seed=42 tag=fghtl_Cnns42 (no covered flag)'
& $gpy @base @('--seed','42','--tag','fghtl_Cnns42','--extra-feats','satrel_node','--no-cov-flag') 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'fghtl_Cnns42.out') -Encoding UTF8
Log ("    [node] Cnn seed=42 rc=$LASTEXITCODE")

'P2_ALL_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== P2 ALL done ==='
