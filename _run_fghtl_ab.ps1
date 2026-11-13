# _run_fghtl_ab.ps1  (ASCII only)  P2 的 A/B 两组基线（不需要 SAT 结果）
# A = 现有结构 GNN (train_mode 2, 无 trust, 无 cone5)
# B = 现有双分支   (train_mode 4, trust)
# 6 runs = {A,B} x seed {42,1,2}, 100 ep, fold 模式, 顺序跑（不并行，防 OOM）
$root = $PSScriptRoot
Set-Location $root
# ---- 关键：不加这两条会 OOM（3.22M 节点必须梯度检查点 ✓）----
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy  = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log  = Join-Path $env:TEMP 'fghtl_ab.log'
$flag = Join-Path $env:TEMP 'fghtl_ab.done'
if (Test-Path $flag) { Remove-Item $flag -Force }

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold, '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--fold-mode', 'fold', '--epochs', '100', '--steps-per-epoch', '1',
            '--val-every', '5', '--view-policy', 'all', '--amp', '--resume')

Log '=== FGHTL A/B start ==='
foreach ($seed in 42,1,2) {
  Log ("--- A (mode2) seed=$seed")
  $ex = @('--train-mode','2','--seed',"$seed",'--tag',"fghtl_As$seed")
  while (((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB) -lt 6) {
    Log '    [wait] free RAM < 6GB → sleep 30s'; Start-Sleep -Seconds 30
  }
  Log ('    GPU ' + ((& nvidia-smi --query-gpu=memory.used --format=csv,noheader) -join ','))
  & $gpy @common @ex 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP "fghtl_As$seed.out") -Encoding UTF8
  Log ("    A seed=$seed rc=$LASTEXITCODE")

  Log ("--- B (mode4+trust) seed=$seed")
  $ex = @('--train-mode','4','--label-mask','trust','--seed',"$seed",'--tag',"fghtl_Bs$seed")
  & $gpy @common @ex 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP "fghtl_Bs$seed.out") -Encoding UTF8
  Log ("    B seed=$seed rc=$LASTEXITCODE")
}

git add -A | Out-Null
git commit -q -m 'queue(P2): A/B baselines (mode2 / mode4+trust) x seeds 42,1,2 @100ep'
Log ("[git] rc={0}" -f $LASTEXITCODE)
'FGHTL_AB_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== FGHTL A/B done ==='
