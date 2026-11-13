# _run_fghtl_cde.ps1  -- P2 的 C/D/E 三组（需要 B09 的 satrel 特征）
#   C = B(mode4+trust) + --extra-feats satrel
#   D = C + --eq-loss 0.5      (跨实现一致性)
#   E = D + --pair-loss 0.5    (A4 三胞胎结构相似抑制)
# 9 runs = {C,D,E} x seed {42,1,2}, 100 ep, 串行（单进程峰值 ~7.9GB 显存，绝不可并行）
$root = $PSScriptRoot
Set-Location $root
$env:GNN_GRAD_CKPT = '1'
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$gpy  = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$log  = Join-Path $env:TEMP 'fghtl_cde.log'
$flag = Join-Path $env:TEMP 'fghtl_cde.done'
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
            '--val-every', '5', '--view-policy', 'all', '--amp', '--resume',
            '--extra-feats', 'satrel', '--train-mode', '4', '--label-mask', 'trust')

function Wait-Ram {
  while (((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB) -lt 6) {
    Log '    [wait] free RAM < 6GB -> sleep 30s'; Start-Sleep -Seconds 30
  }
}

Log '=== FGHTL C/D/E start ==='
foreach ($seed in 42,1,2) {
  foreach ($grp in @(
      @{n='C'; extra=@()},
      @{n='D'; extra=@('--eq-loss','0.5')},
      @{n='E'; extra=@('--pair-loss','0.5','--pair-margin','0.5')})) {
    $tag = "fghtl_$($grp.n)s$seed"
    Wait-Ram
    Log ("--- $($grp.n) seed=$seed tag=$tag")
    $ex = @('--seed',"$seed",'--tag',$tag) + $grp.extra
    & $gpy @common @ex 2>&1 | Out-File -FilePath (Join-Path $env:TEMP "$tag.out") -Encoding UTF8
    Log ("    $($grp.n) seed=$seed rc=$LASTEXITCODE")
  }
}

git add -A | Out-Null
git commit -q -m 'P2: C/D/E runs (satrel feats + eq-loss + pair-loss) x seeds 42,1,2 @100ep'
Log ("[git] rc={0}" -f $LASTEXITCODE)
'FGHTL_CDE_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== FGHTL C/D/E done ==='
